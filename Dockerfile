# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32

# A stage rather than a bare COPY --from, so Dependabot sees a FROM line to bump.
FROM ghcr.io/astral-sh/uv:0.12.22@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc AS uv

FROM python:3.14-slim@sha256:83ff1d245a3d57d04152252d3ef9cb361494d0b3395abd65a5ebe91c401c8e83 AS build
COPY --from=uv /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
RUN uv sync --frozen --no-dev

FROM python:3.14-slim@sha256:83ff1d245a3d57d04152252d3ef9cb361494d0b3395abd65a5ebe91c401c8e83

RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --create-home appuser

WORKDIR /app
COPY --from=build --chown=appuser:appgroup /app /app

USER appuser
ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

ENTRYPOINT ["uvicorn", "app.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
