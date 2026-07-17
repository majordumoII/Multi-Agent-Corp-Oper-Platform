"""Client for the orchestrator's POST /run-task, OIDC-authenticated on Cloud Run."""

from dataclasses import dataclass

import httpx

from services.shared.auth.models import UserContext
from services.shared.auth_session import authenticated_post

from ..config import GatewayConfig


@dataclass
class AgentResultPayload:
    answer: str
    sources: list[dict]
    agent: str
    trace: list[str]


class OrchestratorClient:
    def __init__(self, config: GatewayConfig):
        self.config = config

    async def run_task(self, question: str, user: UserContext) -> AgentResultPayload:
        payload = {
            "question": question,
            "user_id": user.user_id,
            "clearance": user.clearance.name.lower(),
            "roles": user.roles,
        }
        async with httpx.AsyncClient() as client:
            response = await authenticated_post(
                client,
                f"{self.config.orchestrator_url}/run-task",
                json=payload,
                audience=self.config.orchestrator_audience,
                local_dev=self.config.local_dev,
                timeout=self.config.request_timeout_seconds,
            )
        response.raise_for_status()
        body = response.json()
        return AgentResultPayload(
            answer=body["answer"],
            sources=body["sources"],
            agent=body["agent"],
            trace=body["trace"],
        )
