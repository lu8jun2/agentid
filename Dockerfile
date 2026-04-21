FROM python:3.10-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy source first (needed for editable install)
COPY agentid/ ./agentid/
COPY sdk/ ./sdk/
COPY integrations/ ./integrations/
COPY contracts/ ./contracts/

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "."

EXPOSE 8000

# API server
CMD ["uvicorn", "agentid.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
