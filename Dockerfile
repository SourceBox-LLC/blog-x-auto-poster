FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY main.py ./
COPY helpers ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Ensure Python prints unbuffered so logs appear immediately
ENV PYTHONUNBUFFERED=1

# Default location for the SQLite DB inside the container
ENV SOURCEBOX_DB_PATH=/app/sourcebox_blog.db

# Run the pipeline in an infinite loop every hour
CMD ["sh", "-c", \
     "uv run main.py; \
      while true; do \
        echo '--- Sleeping for 3600 seconds before next run ---'; \
        sleep 3600; \
        uv run main.py; \
      done"]
