from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.api_gateway.api.app import create_app
from services.api_gateway.clients.orchestrator_client import AgentResultPayload


@pytest.fixture
def client(gateway_config, mocker):
    mock_client_cls = mocker.patch("services.api_gateway.api.app.OrchestratorClient")
    mock_client = mock_client_cls.return_value
    mock_client.run_task = AsyncMock(
        return_value=AgentResultPayload(
            answer="the answer",
            sources=[{"filename": "doc.pdf", "chunk_index": 0, "content": "hi", "similarity": 0.9}],
            agent="analyst",
            trace=["analyst: retrieved via Project 2 /query"],
        )
    )

    app = create_app(gateway_config)
    with TestClient(app) as c:
        c.mock_orchestrator = mock_client
        yield c


class TestHealth:
    def test_health_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCreateTask:
    def test_create_task_returns_done_with_answer(self, client: TestClient):
        response = client.post(
            "/tasks",
            json={"question": "what is the policy?", "user_id": "bob", "clearance": "internal", "roles": ["engineering"]},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "done"
        assert body["answer"] == "the answer"
        assert "task_id" in body

    def test_create_task_rejects_unknown_clearance(self, client: TestClient):
        response = client.post(
            "/tasks", json={"question": "q", "user_id": "bob", "clearance": "nonsense"}
        )
        assert response.status_code == 400


class TestGetTask:
    def test_get_task_returns_cached_result(self, client: TestClient):
        created = client.post(
            "/tasks", json={"question": "q", "user_id": "bob", "clearance": "public"}
        ).json()

        response = client.get(f"/tasks/{created['task_id']}")

        assert response.status_code == 200
        assert response.json()["answer"] == "the answer"

    def test_get_task_404_for_unknown_id(self, client: TestClient):
        response = client.get("/tasks/does-not-exist")
        assert response.status_code == 404
