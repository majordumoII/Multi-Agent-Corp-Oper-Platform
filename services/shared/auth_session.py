"""OIDC-authenticated HTTP calls between Cloud Run services.

On Cloud Run, service-to-service calls are authenticated with a
Google-signed OIDC ID token scoped to the *audience* (the callee's URL),
which the callee's IAM invoker check validates automatically — no shared
API key. Locally there is no metadata server to mint that token from, so
`LOCAL_DEV=true` (the .env.example default) skips it and calls go out
unauthenticated, the same local/Cloud-Run duality Project 1's VectorStore
uses for Cloud SQL Auth Proxy vs. the Cloud SQL Python Connector.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


def fetch_id_token(audience: str) -> str | None:
    """Returns a Google-signed OIDC ID token for `audience`, or None if
    Application Default Credentials aren't available (local dev)."""
    try:
        import google.auth.transport.requests
        from google.oauth2.id_token import fetch_id_token as _fetch_id_token

        request = google.auth.transport.requests.Request()
        return _fetch_id_token(request, audience)
    except Exception:
        logger.debug("No ADC available for audience %s; calling unauthenticated", audience)
        return None


async def authenticated_post(
    client: httpx.AsyncClient,
    url: str,
    *,
    json: dict,
    audience: str,
    local_dev: bool,
    timeout: float,
) -> httpx.Response:
    """POST `json` to `url`, attaching an OIDC bearer token unless local_dev."""
    headers = {}
    if not local_dev:
        token = fetch_id_token(audience)
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return await client.post(url, json=json, headers=headers, timeout=timeout)
