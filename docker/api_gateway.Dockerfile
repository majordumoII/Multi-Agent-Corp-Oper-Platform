FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY services/ services/

# Cloud Run injects $PORT; main.py reads it and falls back to GatewayConfig.port
EXPOSE 8080
CMD ["python", "-m", "services.api_gateway.main"]
