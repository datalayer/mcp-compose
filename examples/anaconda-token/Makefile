# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

.PHONY: help install install-agent setup-auth start agent stop clean

# Default target
help:
	@echo "Anaconda Authentication MCP Compose Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose and dependencies"
	@echo "  setup-auth     - Check Anaconda authentication setup"
	@echo "  install-agent              - Install pydantic-ai for agent support"
	@echo "  start-echo-streamable-http - Start the echo MCP server in HTTP streaming mode (port 8082)"
	@echo "  start-echo-sse             - Start the echo MCP server in SSE mode (port 8081)"
	@echo "  start                      - Start the MCP Compose with authentication"
	@echo "  agent          - Run the AI agent (requires composer running)"
	@echo "  stop           - Stop the MCP Compose"
	@echo "  clean          - Clean up temporary files"
	@echo ""

# Install dependencies
install:
	@echo "Installing mcp-compose..."
	pip install -e ../..
	@echo ""
	@echo "Installing FastMCP for demo servers..."
	pip install fastmcp
	@echo ""
	@echo "Installing anaconda-auth for authentication..."
	pip install anaconda-auth
	@echo ""
	@echo "✓ Installation complete!"
	@echo ""
	@echo "This example demonstrates Anaconda authentication at the composer level."
	@echo ""
	@echo "Backend servers:"
	@echo "  • mcp1.py      - Calculator tools (add, subtract, multiply, divide)"
	@echo "  • mcp2_http.py - Echo tools with HTTP streaming (JSON Lines)"
	@echo "  • mcp2_sse.py  - Echo tools with SSE (alternative)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Start echo server:     make start-echo-streamable-http"
	@echo "  2. Start the composer:    make start (in another terminal)"
	@echo "  3. Use the AI agent:      make install-agent && make agent"

# Check authentication setup
setup-auth:
	@echo "Checking Anaconda authentication setup..."
	@echo ""
	@if [ -z "$$ANACONDA_API_KEY" ]; then \
		echo "❌ ANACONDA_API_KEY environment variable not set"; \
		echo ""; \
		echo "Please set your Anaconda API key:"; \
		echo "  export ANACONDA_API_KEY='your-api-key-here'"; \
		echo ""; \
		echo "To get an API key:"; \
		echo "  1. Go to https://anaconda.com/app"; \
		echo "  2. Navigate to Settings → Access"; \
		echo "  3. Create a new API key"; \
		echo ""; \
		exit 1; \
	else \
		echo "✓ ANACONDA_API_KEY is set"; \
		echo ""; \
		echo "Testing authentication..."; \
		anaconda auth whoami 2>/dev/null && echo "✓ Authentication successful!" || echo "⚠️  Could not verify authentication"; \
	fi

# Install pydantic-ai for agent support
install-agent:
	@echo "Installing pydantic-ai with MCP support..."
	pip install 'pydantic-ai[mcp]'
	@echo ""
	@echo "✓ Agent dependencies installed!"
	@echo ""
	@echo "Usage:"
	@echo "  1. Start composer: make start"
	@echo "  2. In another terminal: make agent"

# Start the echo MCP server in HTTP streaming mode
start-echo-streamable-http:
	@echo "Starting Echo MCP Server in HTTP Streaming mode..."
	@echo ""
	@echo "Configuration:"
	@echo "  • Transport: HTTP Streaming (JSON Lines)"
	@echo "  • Port: 8082"
	@echo "  • Endpoint: http://localhost:8082/stream"
	@echo "  • Protocol: JSON Lines (newline-delimited JSON)"
	@echo ""
	@echo "Available endpoints:"
	@echo "  • GET  /stream - Stream MCP messages"
	@echo "  • POST /stream - Send MCP messages"
	@echo "  • GET  /health - Health check"
	@echo ""
	@echo "Note: Keep this running in a separate terminal"
	@echo "      Then run 'make start' to start the composer"
	@echo ""
	python mcp2_http.py

# Start the echo MCP server in SSE mode
start-echo-sse:
	@echo "Starting Echo MCP Server in SSE mode..."
	@echo ""
	@echo "Configuration:"
	@echo "  • Transport: SSE"
	@echo "  • Port: 8081"
	@echo "  • Endpoint: http://localhost:8081/sse"
	@echo ""
	@echo "Note: Keep this running in a separate terminal"
	@echo "      Then run 'make start' to start the composer"
	@echo ""
	python mcp2_sse.py

# Start the MCP Compose (no auth key required to start)
start:
	@echo "Starting MCP Compose..."
	@echo ""
	@echo "Configuration:"
	@echo "  • Authentication: Anaconda bearer token validation"
	@echo "  • Backend servers: calculator (STDIO), echo (SSE)"
	@echo "  • Port: 8080"
	@echo ""
	@echo "Prerequisites:"
	@echo "  1. Echo HTTP server must be running: make start-echo-streamable-http"
	@echo "     (or use SSE: make start-echo-sse - requires config change)"
	@echo ""
	@echo "Note: Server starts without requiring ANACONDA_API_KEY."
	@echo "      Clients must provide valid Anaconda bearer tokens."
	@echo ""
	mcp-compose serve --config mcp_compose.toml

# Run the AI agent
agent:
	@echo "Starting AI Agent with Anaconda authentication..."
	@echo ""
	@echo "⚠️  Prerequisites:"
	@echo "   1. MCP Compose must be running (make start)"
	@echo "   2. Anaconda account credentials (run 'make login' first if needed)"
	@echo ""
	@echo "Usage: python agent.py [model] [--auto-login]"
	@echo "  Default: anthropic:claude-sonnet-4-0"
	@echo "  Examples:"
	@echo "    python agent.py openai:gpt-4o"
	@echo "    python agent.py anthropic:claude-sonnet-4-0"
	@echo "    python agent.py azure-openai:gpt-4o-mini"
	@echo "    python agent.py azure-openai:gpt-4o-mini --auto-login"
	@echo ""
	@echo "Note: For Azure OpenAI, set these environment variables:"
	@echo "  - AZURE_OPENAI_API_KEY"
	@echo "  - AZURE_OPENAI_ENDPOINT"
	@echo "  - AZURE_OPENAI_API_VERSION (optional)"
	@echo ""
	python agent.py azure-openai:gpt-4o-mini

# Run the AI agent with auto-login (opens browser for authentication if needed)
agent-auto-login:
	@echo "Starting AI Agent with Anaconda authentication (auto-login enabled)..."
	@echo ""
	@echo "⚠️  Prerequisites:"
	@echo "   1. MCP Compose must be running (make start)"
	@echo ""
	@echo "If not authenticated, a browser window will open for Anaconda login."
	@echo ""
	python agent.py azure-openai:gpt-4o-mini --auto-login

# Stop the composer (use Ctrl+C in the terminal where it's running)
stop:
	@echo "To stop the composer, press Ctrl+C in the terminal where it's running"

login:
	@echo "Logging in to Anaconda..."
	@echo ""
	@anaconda auth login
	@echo ""
	@echo "✓ Logged in to Anaconda"

logout:
	@echo "Logging out of Anaconda..."
	@echo ""
	@anaconda auth logout
	@echo ""
	@echo "✓ Logged out of Anaconda"

jupyterlab:
	@echo "Starting JupyterLab..."
	@echo ""
	jupyter lab --port 8888 --IdentityProvider.token="" --ip 0.0.0.0 --no-browser

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f *.log nohup.out
	@rm -f .composer.pid composer.log
	@echo "✓ Cleanup complete"
