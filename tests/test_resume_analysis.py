import asyncio
from dataclasses import replace
from io import BytesIO
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
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, TextStringObject

from agent_system.InterviewAgent.interviewagent import InterviewAgent
from backend.cli import create_app
from backend.resume_service import read_session_resume, MAX_RESUME_BYTES
from runtime import Runtime
from schemas import CandidateConfig, Interviewer, TaskState


def make_pdf(*pages, password=None):
    """Generate real, synthetic PDFs without another runtime dependency."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject({
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/Helvetica'),
        })
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): font}),
        })
        content = DecodedStreamObject()
        content.set_data(b'BT /F1 12 Tf 50 750 Td <' + text.encode().hex().encode() + b'> Tj ET')
        page.replace_contents(content)
    if password is not None:
        writer.encrypt(password)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


RESUME_TEXT = 'Python backend engineer\n\nBuilt APIs with FastAPI'
PDF = make_pdf('Python backend engineer', '', 'Built APIs with FastAPI')


class ResumeAnalysisTests(IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        env = patch.dict('os.environ', {
            'DATA_DIR': str(self.root), 'LANGSMITH_TRACING': 'false',
            'API_KEY': 'test', 'BASE_URL': 'https://example.invalid/v1', 'MODEL_NAME': 'test',
        })
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
        with patch('agent_system.agent.ChatOpenAI', return_value=self.llm):
            self.agent = InterviewAgent()

    async def test_extracts_pages_in_order_and_skips_blank_pages(self):
        self.assertEqual(read_session_resume(str(self.pdf), self.session), RESUME_TEXT)
        self.assertEqual(self.pdf.read_bytes(), PDF)

    async def test_chinese_cid_font_without_tounicode(self):
        # Adobe-GB1 CIDs for 中文简历; these are not Unicode code points.
        writer = PdfWriter()
        page = writer.add_blank_page(width=595, height=842)
        descendant = DictionaryObject({
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/CIDFontType0'),
            NameObject('/BaseFont'): NameObject('/STSong-Light'),
            NameObject('/CIDSystemInfo'): DictionaryObject({
                NameObject('/Registry'): TextStringObject('Adobe'),
                NameObject('/Ordering'): TextStringObject('GB1'),
                NameObject('/Supplement'): NumberObject(5),
            }),
        })
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject(),
        })
        page['/Resources']['/Font'][NameObject('/F1')] = DictionaryObject({
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type0'),
            NameObject('/BaseFont'): NameObject('/STSong-Light'),
            NameObject('/Encoding'): NameObject('/Identity-H'),
            NameObject('/DescendantFonts'): ArrayObject([descendant]),
        })
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 50 750 Td <11cf0ed3086509e5> Tj ET')
        page.replace_contents(stream)
        output = BytesIO()
        writer.write(output)
        original = output.getvalue()
        self.pdf.write_bytes(original)
        self.llm.ainvoke.return_value = AIMessage(content='中文简历分析')
        await self.agent.sync_resume(self.state)
        self.assertEqual(read_session_resume(str(self.pdf), self.session), '中文简历')
        self.assertTrue(self.llm.ainvoke.call_args.args[0][1].content.endswith('中文简历'))
        self.assertEqual(self.pdf.read_bytes(), original)

    async def test_pdf_text_is_sent_to_analysis_model(self):
        self.llm.ainvoke.return_value = AIMessage(content='具备 Python 项目经历')
        self.assertEqual(await self.agent.sync_resume(self.state), {'resume_evalute': '具备 Python 项目经历'})
        messages = self.llm.ainvoke.call_args.args[0]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertIsInstance(messages[1].content, str)
        self.assertTrue(messages[1].content.endswith(RESUME_TEXT))
        self.assertNotIn(str(self.pdf), messages[1].content)
        self.assertNotIn('base64', messages[1].content)
        self.assertIsNone(self.state.resume_evalute)
        self.assertEqual(self.state.chat_round, 0)

    async def test_model_and_dict_config_are_both_supported(self):
        self.state.candidate_config = CandidateConfig.model_validate(self.state.candidate_config)
        self.llm.ainvoke.return_value = AIMessage(content=[{'type': 'text', 'text': '简历摘要'}])
        self.assertEqual(await self.agent.sync_resume(self.state), {'resume_evalute': '简历摘要'})

    async def test_unreadable_pdf_fails_before_llm(self):
        for content, message in (
            (b'not a PDF', 'PDF'),
            (b'%PDF-1.7\nbroken\n%%EOF', '无法解析'),
            (make_pdf(''), '没有可提取的文字'),
            (make_pdf(), '没有可提取的文字'),
            (make_pdf('secret', password='test'), '已加密'),
            (b'%PDF-' + b'x' * MAX_RESUME_BYTES, '10 MiB'),
        ):
            with self.subTest(message=message, size=len(content)):
                self.pdf.write_bytes(content)
                with self.assertRaisesRegex(ValueError, message):
                    await self.agent.sync_resume(self.state)
        self.llm.ainvoke.assert_not_awaited()

    async def test_missing_wrong_session_and_symlink_fail_before_llm(self):
        self.pdf.unlink()
        with self.assertRaisesRegex(ValueError, '重新上传'):
            await self.agent.sync_resume(self.state)
        self.pdf.write_bytes(PDF)
        with self.assertRaisesRegex(ValueError, '当前会话'):
            await self.agent.sync_resume(replace(self.state, session_id=uuid4()))
        target = self.root / 'other.pdf'
        target.write_bytes(PDF)
        self.pdf.unlink()
        self.pdf.symlink_to(target)
        with self.assertRaisesRegex(ValueError, '当前会话'):
            await self.agent.sync_resume(self.state)
        self.llm.ainvoke.assert_not_awaited()

    async def test_empty_analysis_and_provider_failure_do_not_advance_state(self):
        self.llm.ainvoke.return_value = AIMessage(content=' ')
        with self.assertRaisesRegex(ValueError, '未返回'):
            await self.agent.sync_resume(self.state)
        self.llm.ainvoke.side_effect = RuntimeError('provider rejected request')
        with self.assertRaisesRegex(RuntimeError, 'provider rejected'):
            await self.agent.sync_resume(self.state)
        self.assertIsNone(self.state.resume_evalute)
        self.assertEqual(self.state.chat_round, 0)

    async def test_chatopenai_sends_plain_text_on_the_wire(self):
        captured = []

        async def respond(request):
            captured.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={
                'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '模拟分析'}, 'finish_reason': 'stop'}],
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            self.agent.llm = ChatOpenAI(model='test', api_key='test', base_url='https://example.invalid/v1', http_async_client=client)
            self.assertEqual(await self.agent.sync_resume(self.state), {'resume_evalute': '模拟分析'})
        path, body = captured[0]
        self.assertEqual(path, '/v1/chat/completions')
        self.assertIsInstance(body['messages'][1]['content'], str)
        self.assertTrue(body['messages'][1]['content'].endswith(RESUME_TEXT))
        self.assertNotIn('file_data', json.dumps(body))

    async def test_http_upload_to_stream_analyzes_once_and_saves_checkpoint(self):
        async def respond(messages=None, *, input=None):
            messages = messages if messages is not None else input
            if '# 简历分析 Agent' in messages[0].content:
                return AIMessage(content='简历分析结果')
            return AIMessage(content='面试回复')

        self.llm.ainvoke.side_effect = respond
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
            for round_ in range(3):
                response = await client.post('/interview/stream', json={'session_id': sid, 'message': '你好', 'chat_round': round_})
                self.assertIn('event: done', response.text)
                self.assertNotIn('event: error', response.text)
            snapshot = await graph.aget_state({'configurable': {'thread_id': sid}})
            self.assertEqual(snapshot.values['resume_evalute'], '简历分析结果')
            self.assertEqual(snapshot.values['chat_round'], 3)
            self.assertEqual(self.llm.ainvoke.await_count, 4)
            self.assertIn('简历分析结果', self.llm.ainvoke.call_args.args[0][0].content)
            history = json.dumps([m.model_dump() for m in snapshot.values['messages']])
            self.assertNotIn('Python backend engineer', history)
            self.assertNotIn('file_data', history)

    async def test_first_round_runs_during_analysis_and_next_round_reports_progress(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def respond(messages=None, *, input=None):
            messages = messages if messages is not None else input
            if '# 简历分析 Agent' in messages[0].content:
                started.set()
                await release.wait()
                return AIMessage(content='分析完成')
            return AIMessage(content='面试回复')

        self.llm.ainvoke.side_effect = respond
        first = await asyncio.wait_for(self.agent(self.state), 2)
        self.assertEqual(first['chat_round'], 1)
        self.assertNotIn('resume_evalute', first)
        progress = asyncio.Event()
        second = asyncio.create_task(self.agent(
            replace(self.state, chat_round=1),
            writer=lambda event: progress.set() if event['stage'] == 'parsing_resume' else None,
        ))
        try:
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.wait_for(progress.wait(), 2)
            self.assertFalse(second.done())
        finally:
            release.set()
            update = await asyncio.wait_for(second, 2)
        self.assertEqual(update['resume_evalute'], '分析完成')
        self.assertEqual(self.llm.ainvoke.await_count, 3)
