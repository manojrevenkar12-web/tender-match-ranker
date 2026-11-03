# The ranking API with the console. Models and the platform's state come from a training run (runs/, data/logs).
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml ./
COPY tmr/ tmr/
RUN pip install --no-cache-dir .
COPY config/ config/
COPY migrations/ migrations/
COPY prompts/ prompts/
COPY --from=web /web/dist web/dist
ENV TMR_LLM=off
EXPOSE 8097
CMD ["uvicorn", "tmr.serving.app:app", "--host", "0.0.0.0", "--port", "8097"]
