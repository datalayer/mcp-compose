.PHONY: help install dev-install server client agent test clean

# Default target
help:
	@echo "MCP Authentication Example - Available targets:"
	@echo ""
	@echo "  make install        - Install package in editable mode"
	@echo "  make dev-install    - Install package with dev dependencies"
	@echo "  make server         - Start the MCP server (port 8080)"
	@echo "  make client         - Run the MCP client demo"
	@echo "  make agent          - Run the pydantic-ai agent CLI"
	@echo "  make test           - Run tests"
	@echo "  make clean          - Remove Python cache files"
	@echo ""
	@echo "Quick start:"
	@echo "  1. Configure config.json with GitHub OAuth credentials"
	@echo "  2. make install"
	@echo "  3. make server    (in one terminal)"
	@echo "  4. make client    (in another terminal)"
	@echo "  5. make agent     (for interactive AI agent)"

# Install package in editable mode
install:
	@echo "📦 Installing mcp-oauth..."
	pip install -e .
	@echo "✅ Package installed"

# Install with dev dependencies
dev-install:
	@echo "📦 Installing mcp-oauth with dev dependencies..."
	pip install -e ".[dev]"
	@echo "✅ Package installed with dev dependencies"

# Run the MCP server
server:
	@echo "🚀 Starting MCP server on http://localhost:8080..."
	mcp-oauth-server

# Run the MCP client
client:
	@echo "🔐 Starting MCP client..."
	mcp-oauth-client

# Run the pydantic-ai agent
agent:
	@echo "🤖 Starting pydantic-ai agent..."
	@echo ""
	@echo "Usage: mcp-oauth-agent [model]"
	@echo "  Default: anthropic:claude-sonnet-4-0"
	@echo "  Examples:"
	@echo "    mcp-oauth-agent openai:gpt-4o"
	@echo "    mcp-oauth-agent anthropic:claude-sonnet-4-0"
	@echo "    mcp-oauth-agent azure-openai:gpt-4o-mini"
	@echo ""
	@echo "Note: For Azure OpenAI, set these environment variables:"
	@echo "  - AZURE_OPENAI_API_KEY"
	@echo "  - AZURE_OPENAI_ENDPOINT (base URL, e.g., https://your-resource.openai.azure.com)"
	@echo "  - AZURE_OPENAI_API_VERSION (optional)"
	@echo ""
	mcp-oauth-agent azure-openai:gpt-4o-mini


# Run MCP Inspector
inspector:
	@echo "🔍 Starting Model Context Protocol Inspector..."
	npx @modelcontextprotocol/inspector

# Test Dynamic Client Registration
test-dcr:
	@echo "🧪 Testing Dynamic Client Registration (DCR)..."
	@echo "Make sure the server is running in another terminal: make server"
	@echo ""
	python test_dcr.py

# Run tests
test:
	@echo "🧪 Running tests..."
	pytest tests/ -v

# Clean Python cache files
clean:
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"
