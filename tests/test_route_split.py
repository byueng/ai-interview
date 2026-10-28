from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.cli import create_app
from runtime import Runtime


class RouteSplitTests(TestCase):
    def setUp(self):
        self.graph = Mock()
        self.app = create_app(Runtime(graph=self.graph))
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_existing_paths_are_registered_once_with_responsibility_tags(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        expected = {
            "/interview/begin",
            "/interview/personal_information_config",
            "/interview/stream",
            "/interview/read_preset",
            "/interview/load_preset",
            "/interview/del_preset",
        }

        self.assertTrue(expected.issubset(paths))
        self.assertNotIn("/presets", paths)
        self.assertNotIn("/interview/sessions/{session_id}/resume", paths)
        self.assertEqual(paths["/interview/begin"]["get"]["tags"], ["interview"])
        self.assertEqual(paths["/interview/read_preset"]["get"]["tags"], ["preset"])
        self.assertEqual(paths["/interview/load_preset"]["post"]["tags"], ["preset"])
        self.assertEqual(paths["/interview/del_preset"]["post"]["tags"], ["preset"])
        registered_routes = [
            (route.path, route.methods)
            for included in self.app.routes
            if hasattr(included, "original_router")
            for route in included.original_router.routes
        ]
        for path, method in (
            ("/interview/begin", "GET"),
            ("/interview/read_preset", "GET"),
            ("/interview/load_preset", "POST"),
            ("/interview/del_preset", "POST"),
        ):
            registrations = [
                methods
                for registered_path, methods in registered_routes
                if registered_path == path and method in methods
            ]
            self.assertEqual(len(registrations), 1, f"{method} {path} must register exactly once")

    def test_preset_routes_delegate_file_actions_without_touching_session_graph(self):
        with patch("backend.preset_routes.preset_service.list_presets", return_value=["后端.json"]) as list_presets:
            response = self.client.get("/interview/read_preset")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"files": ["后端.json"]})
        list_presets.assert_called_once_with()

        with patch("backend.preset_routes.preset_service.delete_preset") as delete_preset:
            response = self.client.post("/interview/del_preset?filename=后端.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 200)
        delete_preset.assert_called_once_with("后端.json")
        self.graph.assert_not_called()

    def test_loading_a_preset_uses_the_interview_service_as_session_coordinator(self):
        session_id = uuid4()
        preset = {
            "candidate_config": {"language": "zh-CN", "education": "本科", "position": "后端", "resume": None},
            "interviewer_config": {"role_identity": "技术面试官", "role_responsibilities": "提问"},
        }
        with patch(
            "backend.preset_routes.interview_service.load_preset_into_session",
            new_callable=AsyncMock,
            return_value=preset,
        ) as load_preset:
            response = self.client.post(
                "/interview/load_preset?filename=后端.json",
                json=str(session_id),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"preset_config": preset})
        load_preset.assert_awaited_once_with(self.graph, session_id, "后端.json")
