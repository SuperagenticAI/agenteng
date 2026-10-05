# Model-free public server. Install the rlm extra only in an operator deployment.
# Keep this at the repository root: COPY paths use the root build context.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_CACHE=1 \
    AGENTENG_ENABLE_STANDARD=0 AGENTENG_ENABLE_RLM=0 AGENTENG_ENABLE_INTAKE=0 \
    AGENTENG_PUBLIC_URL=https://a2a.agentengineering.world PORT=8080
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY src ./src
# Install locked server dependencies; omit development tools and the RLM extra.
RUN uv sync --frozen --no-dev --extra server --no-editable --python /usr/local/bin/python
RUN useradd --system --uid 10001 agenteng
USER agenteng
EXPOSE 8080
# Cloud Run injects PORT; the service must listen on all container interfaces.
CMD ["/bin/sh", "-c", "exec /app/.venv/bin/agenteng serve --host 0.0.0.0 --port \"${PORT}\""]
