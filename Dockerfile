# Multi-stage build for MCP Compose

# Stage 1: Build UI
FROM node:18-alpine AS ui-builder

WORKDIR /ui

# Copy UI package files
COPY ui/package*.json ./

# Install dependencies
RUN npm ci

# Copy UI source
COPY ui/ .

# Build UI
RUN npm run build

# Stage 2: Python dependencies
FROM python:3.10-slim AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy Python package files
COPY pyproject.toml README.md ./
COPY mcp_compose/ ./mcp_compose/

# Install Python dependencies
RUN pip install --user --no-cache-dir -e .

# Stage 3: Runtime
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python installation from builder
COPY --from=python-builder /root/.local /root/.local

# Copy UI build from ui-builder
COPY --from=ui-builder /ui/dist /app/ui/dist

# Copy application code
COPY mcp_compose/ /app/mcp_compose/
COPY pyproject.toml README.md /app/

# Copy example configuration
COPY examples/mcp_compose.toml /app/config.toml

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Create directories
RUN mkdir -p /var/log/mcp-composer /data /etc/mcp-composer

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app /var/log/mcp-composer /data /etc/mcp-composer

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
CMD ["mcp-composer", "serve", "--config", "/app/config.toml", "--host", "0.0.0.0", "--port", "8000"]
