"""FastAPI service exposing the orchestrator's agent crew over HTTP.

Phase 1 has exactly one agent (the Analyst). `POST /run-task` is the
contract the api_gateway calls synchronously; its shape stays stable as
Agent B/C join in later phases — only what happens inside `AnalystAgent`
(soon: `Crew.kickoff()`) changes.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from services.shared.auth.models import ClearanceLevel, UserContext

from ..agents.analyst import AnalystAgent
from ..config import OrchestratorConfig
from .dependencies import get_analyst_agent
from .schemas import RunTaskRequest, RunTaskResponse


def create_app(config: OrchestratorConfig | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.analyst_agent = AnalystAgent(config or OrchestratorConfig.from_env())
        yield

    app = FastAPI(title="Multi-Agent Corp Ops — Orchestrator", lifespan=lifespan)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/run-task", response_model=RunTaskResponse)
    async def run_task(
        body: RunTaskRequest, agent: AnalystAgent = Depends(get_analyst_agent)
    ) -> RunTaskResponse:
        user = UserContext(
            user_id=body.user_id,
            clearance=ClearanceLevel.from_str(body.clearance),
            roles=body.roles,
        )
        result = await agent.run(body.question, user)
        return RunTaskResponse(
            answer=result.answer,
            sources=result.sources,
            agent=result.agent,
            trace=result.trace,
        )

    return app


app = create_app()
