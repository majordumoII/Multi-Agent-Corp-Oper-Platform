"""Typed client for Project 2's POST /query — Agent A's only tool in Phase 1.

Request/response shape matches `rag_guardrails.api.schemas.QueryRequest` /
`QueryResponse` exactly, since Project 3 does not re-implement retrieval or
guardrails — it calls Project 2's service and trusts its permission
filtering and NeMo Guardrails checks.
"""

from dataclasses import dataclass

import httpx

from services.shared.auth.models import UserContext
from services.shared.auth_session import authenticated_post

from ..config import OrchestratorConfig


@dataclass
class RagQueryResult:
    answer: str
    sources: list[dict]


class RagClient:
    def __init__(self, config: OrchestratorConfig):
        self.config = config

    async def query(
        self, question: str, user: UserContext, top_k: int | None = None
    ) -> RagQueryResult:
        payload = {
            "question": question,
            "user_id": user.user_id,
            "clearance": user.clearance.name.lower(),
            "roles": user.roles,
            "top_k": top_k,
        }
        async with httpx.AsyncClient() as client:
            response = await authenticated_post(
                client,
                f"{self.config.rag_service_url}/query",
                json=payload,
                audience=self.config.rag_service_audience,
                local_dev=self.config.local_dev,
                timeout=self.config.request_timeout_seconds,
            )
        response.raise_for_status()
        body = response.json()
        return RagQueryResult(answer=body["answer"], sources=body["sources"])
