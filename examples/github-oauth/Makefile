# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

.PHONY: help install install-agent setup-auth start agent stop clean oauth-test

# Default target
help:
	@echo "GitHub OAuth MCP Compose Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose and dependencies"
	@echo "  setup-auth     - Check GitHub OAuth configuration"
	@echo "  install-agent  - Install pydantic-ai for agent support"
	@echo "  start          - Start the MCP Compose with GitHub OAuth authentication"
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
	@echo "Backend servers (both use STDIO, managed by composer):"
	@echo "  • mcp1.py - Calculator tools (add, subtract, multiply, divide)"
	@echo "  • mcp2.py - Echo tools (ping, echo, reverse, uppercase, lowercase, count_words)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Configure config.json with GitHub OAuth credentials"
	@echo "  2. Start the composer:    make start"
	@echo "  3. Use the AI agent:      make install-agent && make agent"

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

# Start the MCP Compose with GitHub OAuth authentication
start:
	@echo "Starting MCP Compose with GitHub OAuth..."
	@echo ""
	@echo "Configuration:"
	@echo "  • Authentication: GitHub OAuth2 (validates bearer tokens via GitHub API)"
	@echo "  • Backend servers: calculator (STDIO), echo (STDIO)"
	@echo "  • Port: 8080"
	@echo "  • MCP Endpoint: http://localhost:8080/mcp"
	@echo ""
	@echo "Note: Server validates incoming bearer tokens against GitHub's API."
	@echo "      Clients must provide valid GitHub OAuth tokens."
	@echo ""
	mcp-compose serve --config mcp_compose.toml

# Run the AI agent
agent:
	@echo "Starting AI Agent with GitHub OAuth authentication..."
	@echo ""
	@echo "⚠️  Prerequisites:"
	@echo "   1. MCP Compose must be running (make start)"
	@echo "   2. GitHub OAuth credentials in config.json"
	@echo ""
	@echo "The agent will authenticate using GitHub OAuth."
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
	python agent.py

# Stop the composer (use Ctrl+C in the terminal where it's running)
stop:
	@echo "To stop the composer, press Ctrl+C in the terminal where it's running"

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f *.log nohup.out
	@rm -f .composer.pid composer.log
	@echo "✓ Cleanup complete"
