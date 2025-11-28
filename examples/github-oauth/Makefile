.PHONY: help install install-agent setup-auth start agent stop clean oauth-test

# Default target
help:
	@echo "GitHub OAuth MCP Compose Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose and dependencies"
	@echo "  setup-auth     - Check GitHub OAuth configuration"
	@echo "  install-agent              - Install pydantic-ai for agent support"
	@echo "  start-echo-streamable-http - Start the echo MCP server in HTTP streaming mode (port 8082)"
	@echo "  start-echo-sse             - Start the echo MCP server in SSE mode (port 8081)"
	@echo "  start                      - Start the MCP Compose with authentication"
	@echo "  agent          - Run the AI agent (requires composer running)"
	@echo "  oauth-test     - Test the OAuth client (get a token)"
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
	@echo "Installing requests for OAuth client..."
	pip install requests
	@echo ""
	@echo "✓ Installation complete!"
	@echo ""
	@echo "This example demonstrates GitHub OAuth authentication at the composer level."
	@echo ""
	@echo "Backend servers:"
	@echo "  • mcp1.py      - Calculator tools (add, subtract, multiply, divide)"
	@echo "  • mcp2_http.py - Echo tools with HTTP streaming (JSON Lines)"
	@echo "  • mcp2_sse.py  - Echo tools with SSE (alternative)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Configure config.json with GitHub OAuth credentials"
	@echo "  2. Start echo server:     make start-echo-streamable-http"
	@echo "  3. Start the composer:    make start (in another terminal)"
	@echo "  4. Use the AI agent:      make install-agent && make agent"

# Check authentication setup
setup-auth:
	@echo "Checking GitHub OAuth configuration..."
	@echo ""
	@if [ ! -f config.json ]; then \
		echo "❌ config.json not found"; \
		echo ""; \
		echo "Please create config.json with your GitHub OAuth credentials:"; \
		echo "  1. Go to https://github.com/settings/developers"; \
		echo "  2. Create a new OAuth App"; \
		echo "  3. Set callback URL to: http://localhost:8080/callback"; \
		echo "  4. Copy client_id and client_secret to config.json"; \
		echo ""; \
		exit 1; \
	else \
		echo "✓ config.json exists"; \
		echo ""; \
		echo "To test your configuration:"; \
		echo "  make oauth-test"; \
	fi

# Test the OAuth client
oauth-test:
	@echo "Testing GitHub OAuth client..."
	python oauth_client.py

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
	@echo "   2. Anaconda account credentials (will use login() if needed)"
	@echo ""
	@echo "The agent will authenticate using anaconda_auth.login() if needed."
	@echo "This will open your browser for authentication."
	@echo ""
	@echo "Usage: python agent.py [model]"
	@echo "  Default: anthropic:claude-sonnet-4-0"
	@echo "  Examples:"
	@echo "    python agent.py openai:gpt-4o"
	@echo "    python agent.py anthropic:claude-sonnet-4-0"
	@echo "    python agent.py azure-openai:gpt-4o-mini"
	@echo ""
	@echo "Note: For Azure OpenAI, set these environment variables:"
	@echo "  - AZURE_OPENAI_API_KEY"
	@echo "  - AZURE_OPENAI_ENDPOINT"
	@echo "  - AZURE_OPENAI_API_VERSION (optional)"
	@echo ""
	python agent.py azure-openai:gpt-4o-mini

# Stop the composer (use Ctrl+C in the terminal where it's running)
stop:
	@echo "To stop the composer, press Ctrl+C in the terminal where it's running"

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f *.log nohup.out
	@rm -f .composer.pid composer.log
	@echo "✓ Cleanup complete"
