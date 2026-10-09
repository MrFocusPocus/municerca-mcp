FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    MUNICERCA_TRANSPORT=http \
    MUNICERCA_DB=/tmp/municerca.db
USER 65534
CMD ["municerca-mcp"]
