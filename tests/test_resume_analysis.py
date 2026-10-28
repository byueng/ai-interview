import base64
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END

from agent_system.InterviewAgent.interviewagent import InterviewAgent
from backend.cli import create_app
from runtime import Runtime
from schemas import CandidateConfig, Interviewer, TaskState

PDF = b'%PDF-1.7\nsynthetic test fixture\n%%EOF'


class ResumeAnalysisTests(IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        env = patch.dict('os.environ', {'DATA_DIR': str(self.root), 'LANGSMITH_TRACING': 'false'})
        env.start()
        self.addCleanup(env.stop)
        self.session = uuid4()
        self.pdf = self.root / 'swap' / str(self.session) / '简历.pdf'
        self.pdf.parent.mkdir(parents=True)
        self.pdf.write_bytes(PDF)
        self.state = TaskState(
            session_id=self.session,
            candidate_config=CandidateConfig(language='中文', education='本科', position='后端', resume=str(self.pdf)).model_dump(),
            interviewer_config=Interviewer(role_identity='面试官', role_responsibilities='技术面试').model_dump(),
            messages=[HumanMessage(content='你好')],
        )
        self.llm = AsyncMock(spec=BaseChatModel)
        self.agent = InterviewAgent(llm=self.llm)

    async def test_pdf_is_attached_as_bytes_and_analysis_is_used_in_current_reply(self):
        self.llm.ainvoke.side_effect = [AIMessage(content='具备 Python 项目经历'), AIMessage(content='请介绍项目')]
        update = await self.agent(self.state)
        analysis_messages = self.llm.ainvoke.call_args_list[0].args[0]
        self.assertIsInstance(analysis_messages[0], SystemMessage)
        self.assertNotIn('{resume_text}', analysis_messages[0].content)
        attachment = analysis_messages[1].content[0]['file']
        self.assertEqual(attachment['filename'], '简历.pdf')
        self.assertEqual(base64.b64decode(attachment['file_data'].split(',', 1)[1]), PDF)
        self.assertEqual(update['resume_evalute'], '具备 Python 项目经历')
        interview_prompt = self.llm.ainvoke.call_args_list[1].args[0][0].content
        self.assertIn('具备 Python 项目经历', interview_prompt)
        self.assertNotIn(str(self.pdf), interview_prompt)
        self.assertIsNone(self.state.resume_evalute)
        self.assertEqual(self.state.chat_round, 0)
        self.assertEqual(update['chat_round'], 1)
        self.assertEqual(set(vars(self.agent)), {'llm'})

    async def test_checkpoint_reuses_analysis_in_later_turns(self):
        self.llm.ainvoke.side_effect = [AIMessage(content='分析摘要'), AIMessage(content='第一轮'), AIMessage(content='第二轮')]
        builder = StateGraph(TaskState)
        builder.add_node('InterviewAgent', self.agent)
        builder.add_edge(START, 'InterviewAgent')
        builder.add_edge('InterviewAgent', END)
        graph = builder.compile(checkpointer=InMemorySaver())
        config = {'configurable': {'thread_id': str(self.session)}}
        first = await graph.ainvoke(self.state, config)
        self.assertEqual(first['resume_evalute'], '分析摘要')
        await graph.ainvoke({'messages': [HumanMessage(content='继续')]}, config)
        self.assertEqual(self.llm.ainvoke.await_count, 3)
        self.assertIn('分析摘要', self.llm.ainvoke.call_args.args[0][0].content)

    async def test_model_and_dict_config_are_both_supported(self):
        self.state.candidate_config = CandidateConfig.model_validate(self.state.candidate_config)
        self.llm.ainvoke.return_value = AIMessage(content=[{'type': 'text', 'text': '简历摘要'}])
        self.assertEqual(await self.agent.sync_resume(self.state), {'resume_evalute': '简历摘要'})

    async def test_missing_wrong_session_and_invalid_pdf_fail_before_llm(self):
        self.pdf.unlink()
        with self.assertRaisesRegex(ValueError, '重新上传'):
            await self.agent.sync_resume(self.state)
        self.pdf.write_bytes(b'not a PDF')
        with self.assertRaisesRegex(ValueError, 'PDF'):
            await self.agent.sync_resume(self.state)
        self.state.candidate_config['resume'] = str(self.root / 'other.pdf')
        with self.assertRaisesRegex(ValueError, '当前会话'):
            await self.agent.sync_resume(self.state)
        self.llm.ainvoke.assert_not_awaited()

    async def test_empty_analysis_and_provider_failure_do_not_advance_state(self):
        self.llm.ainvoke.return_value = AIMessage(content=' ')
        with self.assertRaisesRegex(ValueError, '未返回'):
            await self.agent(self.state)
        self.assertEqual(self.llm.ainvoke.await_count, 1)
        self.llm.ainvoke.side_effect = RuntimeError('provider rejected file')
        with self.assertRaisesRegex(RuntimeError, 'provider rejected'):
            await self.agent(self.state)
        self.assertIsNone(self.state.resume_evalute)
        self.assertEqual(self.state.chat_round, 0)

    async def test_chatopenai_sends_file_using_chat_completions_wire_format(self):
        captured = []
        async def respond(request):
            captured.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={
                'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'qwen3.8-max-0902',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '模拟分析'}, 'finish_reason': 'stop'}],
            })
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            model = ChatOpenAI(model='qwen3.8-max-0902', api_key='test', base_url='https://example.invalid/v1', http_async_client=client)
            self.assertEqual(await InterviewAgent(llm=model).sync_resume(self.state), {'resume_evalute': '模拟分析'})
        path, body = captured[0]
        self.assertEqual(path, '/v1/chat/completions')
        file = body['messages'][1]['content'][0]['file']
        self.assertEqual(base64.b64decode(file['file_data'].split(',', 1)[1]), PDF)

    async def test_http_upload_to_stream_analyzes_once_and_saves_checkpoint(self):
        self.llm.ainvoke.side_effect = [AIMessage(content='附件分析结果'), AIMessage(content='欢迎开始'), AIMessage(content='继续提问')]
        builder = StateGraph(TaskState)
        builder.add_node('InterviewAgent', self.agent)
        builder.add_edge(START, 'InterviewAgent')
        builder.add_edge('InterviewAgent', END)
        graph = builder.compile(checkpointer=InMemorySaver())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(Runtime(graph))), base_url='http://test') as client:
            sid = (await client.get('/interview/begin')).json()['session_id']
            config = {'candidate_config': {**self.state.candidate_config, 'resume': None}, 'interviewer_config': self.state.interviewer_config}
            saved = await client.post('/interview/personal_information_config', data={
                'session_id': sid, 'config': json.dumps(config),
            }, files={'file': ('resume.pdf', PDF, 'application/pdf')})
            self.assertEqual(saved.status_code, 200, saved.text)
            self.llm.ainvoke.assert_not_awaited()
            for round_ in range(2):
                response = await client.post('/interview/stream', json={'session_id': sid, 'message': '你好', 'chat_round': round_})
                self.assertIn('event: done', response.text)
                self.assertNotIn('event: error', response.text)
                progress = [json.loads(block.split('data: ', 1)[1])['stage']
                            for block in response.text.split('\n\n') if block.startswith('event: progress')]
                self.assertEqual(progress, ['parsing_resume', 'generating_reply'] if round_ == 0 else ['generating_reply'])
                self.assertLess(response.text.index('event: progress'), response.text.index('event: message'))
            snapshot = await graph.aget_state({'configurable': {'thread_id': sid}})
            self.assertEqual(snapshot.values['resume_evalute'], '附件分析结果')
            self.assertEqual(snapshot.values['chat_round'], 2)
            self.assertEqual(self.llm.ainvoke.await_count, 3)
            self.assertNotIn('file_data', json.dumps([m.model_dump() for m in snapshot.values['messages']]))


    async def test_parsing_progress_arrives_while_analysis_model_is_still_waiting(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def respond(messages):
            if isinstance(messages[-1], HumanMessage) and isinstance(messages[-1].content, list):
                started.set()
                await release.wait()
                return AIMessage(content='分析完成')
            return AIMessage(content='面试回复')
        self.llm.ainvoke.side_effect = respond
        builder = StateGraph(TaskState)
        builder.add_node('InterviewAgent', self.agent)
        builder.add_edge(START, 'InterviewAgent')
        builder.add_edge('InterviewAgent', END)
        graph = builder.compile()
        stream = graph.astream(self.state, stream_mode=['custom', 'updates'])
        try:
            first = await asyncio.wait_for(anext(stream), 2)
            self.assertEqual(first, ('custom', {'stage': 'parsing_resume'}))
            await asyncio.wait_for(started.wait(), 2)
            self.assertFalse(release.is_set())
            release.set()
            remaining = [item async for item in stream]
            self.assertEqual(remaining[0], ('custom', {'stage': 'generating_reply'}))
            self.assertEqual(remaining[-1][0], 'updates')
        finally:
            release.set()
            await stream.aclose()
