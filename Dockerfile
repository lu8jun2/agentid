FROM python:3.10-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy all source needed for pip install -e .
COPY agentid/ ./agentid/
COPY sdk/ ./sdk/
COPY integrations/ ./integrations/
COPY contracts/ ./contracts/
COPY pyproject.toml README.md ./
COPY alembic.ini ./

# Install Python deps
RUN pip install --no-cache-dir -e "."

EXPOSE 8000

# API server
CMD ["uvicorn", "agentid.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
