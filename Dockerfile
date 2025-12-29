FROM ghcr.io/astral-sh/uv:0.9.18 AS uv
FROM python:3.14-slim-bookworm
WORKDIR /app
RUN --mount=from=uv,source=/uv,target=./uv ./uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv --mount=from=uv,source=/uv,target=./uv ./uv pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["gunicorn", "--logfile=-", "--bind=0.0.0.0:8080", "app:create_app()"]
