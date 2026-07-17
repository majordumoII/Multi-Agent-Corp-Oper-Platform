"""Entry point: run the api_gateway's FastAPI service."""

import os

from dotenv import load_dotenv

load_dotenv()

from services.shared.logging import configure_logging

from .config import GatewayConfig


def main() -> None:
    configure_logging()
    import uvicorn

    from .api.app import app

    config = GatewayConfig.from_env()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", config.port)))


if __name__ == "__main__":
    main()
