FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir /app/data && chown app:app /app/data
COPY --from=build /app/.venv /app/.venv
COPY src/*.py ./src/
COPY src/backend ./src/backend
COPY src/agent_system ./src/agent_system
USER app
EXPOSE 7022
# InMemorySaver requires one worker. Do not enable reload in the runtime image.
CMD ["uvicorn", "runtime:run_time", "--factory", "--host", "0.0.0.0", "--port", "7022", "--workers", "1"]
