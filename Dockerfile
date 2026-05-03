# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

# Multi-stage build for MCP Compose

# Stage 1: Build UI
FROM node:18-alpine AS ui-builder

WORKDIR /ui

# Copy UI package files
COPY ui/package.json ./

# Install dependencies
RUN npm install

# Copy UI source
COPY ui/ ./

# Build UI
RUN npm run build

# Stage 2: Build Python wheel
FROM python:3.10-slim AS python-builder

WORKDIR /build

# Copy Python package files
COPY pyproject.toml README.md LICENSE hatch_build.py ./
COPY mcp_compose/ ./mcp_compose/

# Build the wheel
RUN pip install --upgrade build \
    && python -m build --wheel --outdir dist

# Stage 3: Runtime
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install the wheel from the builder stage
COPY --from=python-builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Copy UI build from ui-builder
COPY --from=ui-builder /ui/dist /app/ui/dist

# Copy example configuration
COPY examples/ui/mcp_compose.toml /app/config.toml

# Create directories
RUN mkdir -p /var/log/mcp-compose /data /etc/mcp-compose

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app /var/log/mcp-compose /data /etc/mcp-compose

# Switch to non-root user
USER mcp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Set environment variables
ENV MCP_COMPOSER_HOST=0.0.0.0 \
    MCP_COMPOSER_PORT=8000 \
    MCP_COMPOSER_LOG_LEVEL=INFO

# Run the application
CMD ["mcp-compose", "serve", "--config", "/app/config.toml", "--host", "0.0.0.0", "--port", "8000"]
