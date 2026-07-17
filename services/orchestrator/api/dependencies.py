from fastapi import Request

from ..agents.analyst import AnalystAgent


def get_analyst_agent(request: Request) -> AnalystAgent:
    return request.app.state.analyst_agent
