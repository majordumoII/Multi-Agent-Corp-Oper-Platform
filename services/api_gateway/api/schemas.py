from enum import Enum

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    question: str
    user_id: str
    clearance: str = Field(
        default="public", description="public | internal | confidential | restricted"
    )
    roles: list[str] = Field(default_factory=list)


class TaskStatus(str, Enum):
    # Phase 1 calls the orchestrator synchronously, so every task that
    # reaches a response is already DONE or FAILED. QUEUED/RUNNING are
    # reserved for Phase 2, when POST /tasks publishes to Pub/Sub and
    # returns immediately instead of waiting on the agent run.
    DONE = "done"
    FAILED = "failed"


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    answer: str | None = None
    sources: list[dict] | None = None
    agent: str | None = None
    trace: list[str] | None = None
