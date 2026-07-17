"""Agent A — Analyst. Phase 1 stub: retrieves via Project 2, returns as-is.

`run()` is deliberately CrewAI-`Task`-shaped (one question in, one typed
result out) so that when Agent B (compliance) joins in a later phase, this
class's body becomes a `Crew`-orchestrated `Agent`/`Task` pair instead of
a rewrite — the call site (`services/orchestrator/api/app.py`) does not
need to change.
"""

from dataclasses import dataclass, field

from services.shared.auth.models import UserContext

from ..config import OrchestratorConfig
from ..tools.rag_client import RagClient


@dataclass
class AgentResult:
    answer: str
    sources: list[dict]
    agent: str = "analyst"
    # Forward-compat: later phases append entries here as Agent B/C act on
    # this result, building the audit transcript described in the README.
    trace: list[str] = field(default_factory=list)


class AnalystAgent:
    def __init__(self, config: OrchestratorConfig, rag_client: RagClient | None = None):
        self.config = config
        self.rag_client = rag_client or RagClient(config)

    async def run(self, question: str, user: UserContext) -> AgentResult:
        result = await self.rag_client.query(question, user)
        return AgentResult(
            answer=result.answer,
            sources=result.sources,
            trace=["analyst: retrieved via Project 2 /query"],
        )
