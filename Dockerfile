FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy source code
COPY src/ ./src/
COPY dbt/ ./dbt/

# Default command
CMD ["uv", "run", "python", "-m", "src.producers.binance_ws"]