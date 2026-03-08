# Production image for Royal Horizon Document AI
FROM python:3.11-slim

WORKDIR /app

# System deps for pdf2image (PDF -> image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

COPY src ./src

ENV PORT=8000
EXPOSE ${PORT}
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
