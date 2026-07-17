from fastapi import Request

from ..clients.orchestrator_client import OrchestratorClient


def get_orchestrator_client(request: Request) -> OrchestratorClient:
    return request.app.state.orchestrator_client
