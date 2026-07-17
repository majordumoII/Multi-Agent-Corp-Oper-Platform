from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.orchestrator.agents.analyst import AgentResult
from services.orchestrator.api.app import create_app


@pytest.fixture
def client(orchestrator_config, mocker):
    mock_agent_cls = mocker.patch("services.orchestrator.api.app.AnalystAgent")
    mock_agent = mock_agent_cls.return_value
    mock_agent.run = AsyncMock(
        return_value=AgentResult(
            answer="the answer",
            sources=[{"filename": "doc.pdf", "chunk_index": 0, "content": "hi", "similarity": 0.9}],
            trace=["analyst: retrieved via Project 2 /query"],
        )
    )

    app = create_app(orchestrator_config)
    with TestClient(app) as c:
        c.mock_agent = mock_agent
        yield c


class TestHealth:
    def test_health_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRunTask:
    def test_run_task_returns_agent_result(self, client: TestClient):
        response = client.post(
            "/run-task",
            json={"question": "what is the policy?", "user_id": "bob", "clearance": "internal", "roles": ["engineering"]},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "the answer"
        assert body["agent"] == "analyst"
        assert body["sources"][0]["filename"] == "doc.pdf"

    def test_run_task_builds_user_context_from_body(self, client: TestClient):
        client.post(
            "/run-task",
            json={"question": "q", "user_id": "bob", "clearance": "confidential", "roles": ["finance"]},
        )

        args, _ = client.mock_agent.run.call_args
        assert args[0] == "q"
        user = args[1]
        assert user.user_id == "bob"
        assert user.roles == ["finance"]

    def test_run_task_rejects_unknown_clearance(self, client: TestClient):
        response = client.post(
            "/run-task", json={"question": "q", "user_id": "bob", "clearance": "nonsense"}
        )
        assert response.status_code == 400
