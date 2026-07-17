"""FastAPI service exposing the task API over HTTP.

Phase 1 has no Pub/Sub or Firestore yet: `POST /tasks` calls the
orchestrator synchronously and caches the result in-process so
`GET /tasks/{id}` has something to return. Both the route signatures and
the `TaskResponse` schema are written as the stable task-resource contract
so that Phase 2 only needs to change what happens *inside* these handlers
(publish to Pub/Sub + return 202, read from Firestore) — not the contract
callers depend on.

`user_id`/`clearance`/`roles` are accepted directly on the request body,
the same demo-level auth stand-in Project 2 uses — replacing this with
real SSO/JWT-derived identity is inherited debt tracked in the platform
README's Phase 5.
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from services.shared.auth.models import ClearanceLevel, UserContext

from ..clients.orchestrator_client import OrchestratorClient
from ..config import GatewayConfig
from .dependencies import get_orchestrator_client
from .schemas import TaskRequest, TaskResponse, TaskStatus


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.orchestrator_client = OrchestratorClient(config or GatewayConfig.from_env())
        # Phase 1 placeholder for Firestore task state — see module docstring.
        app.state.task_cache = {}
        yield

    app = FastAPI(title="Multi-Agent Corp Ops — API Gateway", lifespan=lifespan)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/tasks", response_model=TaskResponse)
    async def create_task(
        body: TaskRequest,
        request: Request,
        orchestrator: OrchestratorClient = Depends(get_orchestrator_client),
    ) -> TaskResponse:
        task_id = str(uuid.uuid4())
        user = UserContext(
            user_id=body.user_id,
            clearance=ClearanceLevel.from_str(body.clearance),
            roles=body.roles,
        )
        result = await orchestrator.run_task(body.question, user)
        task = TaskResponse(
            task_id=task_id,
            status=TaskStatus.DONE,
            answer=result.answer,
            sources=result.sources,
            agent=result.agent,
            trace=result.trace,
        )
        request.app.state.task_cache[task_id] = task
        return task

    @app.get("/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(task_id: str, request: Request) -> TaskResponse:
        task = request.app.state.task_cache.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    return app


app = create_app()
