import os
from dataclasses import dataclass, field


@dataclass
class GatewayConfig:
    project_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "")
    )
    local_dev: bool = field(
        default_factory=lambda: os.getenv("LOCAL_DEV", "true").lower() == "true"
    )

    orchestrator_url: str = field(
        default_factory=lambda: os.getenv("ORCHESTRATOR_URL", "http://localhost:8081")
    )
    orchestrator_audience: str = field(
        default_factory=lambda: os.getenv("ORCHESTRATOR_AUDIENCE", "")
    )

    request_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
    )
    port: int = field(default_factory=lambda: int(os.getenv("GATEWAY_PORT", "8080")))

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        return cls()

    def __post_init__(self) -> None:
        if not self.orchestrator_audience:
            self.orchestrator_audience = self.orchestrator_url
