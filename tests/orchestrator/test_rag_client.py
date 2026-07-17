from unittest.mock import AsyncMock, MagicMock

import pytest

from services.orchestrator.tools.rag_client import RagClient


@pytest.fixture
def mock_response():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "answer": "the answer",
        "sources": [{"filename": "doc.pdf", "chunk_index": 0, "content": "hi", "similarity": 0.9}],
    }
    return response


class TestRagClientLocalDev:
    async def test_query_calls_rag_service_without_token(
        self, orchestrator_config, user, mock_response, mocker
    ):
        mock_post = mocker.patch(
            "httpx.AsyncClient.post", AsyncMock(return_value=mock_response)
        )
        fetch_token = mocker.patch(
            "services.shared.auth_session.fetch_id_token"
        )

        client = RagClient(orchestrator_config)
        result = await client.query("what is the policy?", user)

        assert result.answer == "the answer"
        assert result.sources[0]["filename"] == "doc.pdf"
        fetch_token.assert_not_called()
        _, kwargs = mock_post.call_args
        assert "Authorization" not in kwargs["headers"]

    async def test_query_sends_project2_shaped_payload(
        self, orchestrator_config, user, mock_response, mocker
    ):
        mock_post = mocker.patch(
            "httpx.AsyncClient.post", AsyncMock(return_value=mock_response)
        )
        mocker.patch("services.shared.auth_session.fetch_id_token")

        client = RagClient(orchestrator_config)
        await client.query("q", user, top_k=3)

        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {
            "question": "q",
            "user_id": "bob",
            "clearance": "internal",
            "roles": ["engineering"],
            "top_k": 3,
        }


class TestRagClientProduction:
    async def test_query_attaches_oidc_token_when_not_local_dev(
        self, orchestrator_config, user, mock_response, mocker
    ):
        orchestrator_config.local_dev = False
        mock_post = mocker.patch(
            "httpx.AsyncClient.post", AsyncMock(return_value=mock_response)
        )
        mocker.patch(
            "services.shared.auth_session.fetch_id_token", return_value="fake-id-token"
        )

        client = RagClient(orchestrator_config)
        await client.query("q", user)

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer fake-id-token"
