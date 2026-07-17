import os
from dataclasses import dataclass, field


@dataclass
class OrchestratorConfig:
    project_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "")
    )
    local_dev: bool = field(
        default_factory=lambda: os.getenv("LOCAL_DEV", "true").lower() == "true"
    )

    # Project 2's Enterprise RAG Security Guardrails service
    rag_service_url: str = field(
        default_factory=lambda: os.getenv("RAG_SERVICE_URL", "http://localhost:8000")
    )
    rag_service_audience: str = field(
        default_factory=lambda: os.getenv("RAG_SERVICE_AUDIENCE", "")
    )

    # Vertex AI (Gemini) — unused by Phase 1's stub Agent A, reserved for
    # when Agent A starts reasoning over retrieved chunks instead of
    # passing them straight through.
    vertex_project_id: str = field(
        default_factory=lambda: os.getenv("VERTEX_PROJECT_ID", "")
    )
    vertex_location: str = field(
        default_factory=lambda: os.getenv("VERTEX_LOCATION", "us-east1")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    )

    request_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
    )
    port: int = field(default_factory=lambda: int(os.getenv("ORCHESTRATOR_PORT", "8081")))

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        return cls()

    def __post_init__(self) -> None:
        if not self.rag_service_audience:
            self.rag_service_audience = self.rag_service_url
