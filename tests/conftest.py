import pytest

from services.api_gateway.config import GatewayConfig
from services.orchestrator.config import OrchestratorConfig
from services.shared.auth.models import ClearanceLevel, UserContext


@pytest.fixture
def gateway_config() -> GatewayConfig:
    return GatewayConfig(
        project_id="test-project",
        local_dev=True,
        orchestrator_url="http://orchestrator.test",
    )


@pytest.fixture
def orchestrator_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        project_id="test-project",
        local_dev=True,
        rag_service_url="http://rag.test",
    )


@pytest.fixture
def user() -> UserContext:
    return UserContext(user_id="bob", clearance=ClearanceLevel.INTERNAL, roles=["engineering"])
