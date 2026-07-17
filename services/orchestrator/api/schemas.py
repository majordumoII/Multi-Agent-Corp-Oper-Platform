from pydantic import BaseModel, Field


class RunTaskRequest(BaseModel):
    question: str
    user_id: str
    clearance: str = Field(
        default="public", description="public | internal | confidential | restricted"
    )
    roles: list[str] = Field(default_factory=list)


class RunTaskResponse(BaseModel):
    answer: str
    sources: list[dict]
    agent: str
    trace: list[str]
