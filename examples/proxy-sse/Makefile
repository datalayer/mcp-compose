.PHONY: help install install-agent start agent stop clean

# Default target
help:
	@echo "SSE Transport Example - Makefile"
	@echo ""
	@echo "⚠️  Note: SSE transport is deprecated. Consider using:"
	@echo "   - proxy-streamable-http for HTTP-based transport"
	@echo "   - proxy-stdio for subprocess-based transport"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose and MCP servers"
	@echo "  install-agent  - Install pydantic-ai for agent support"
	@echo "  start          - Start the MCP Compose server"
	@echo "  agent          - Run the AI agent (requires composer running)"
	@echo "  stop           - Stop the MCP Compose server"
	@echo "  clean          - Clean up temporary files"
	@echo ""
	@echo "Usage:"
	@echo "  1. make install"
	@echo "  2. make install-agent"
	@echo "  3. make start          (in one terminal)"
	@echo "  4. make agent          (in another terminal)"
	@echo ""

# Install dependencies
install:
	@echo "Installing mcp-compose..."
	pip install -e ../..
	@echo ""
	@echo "Installing FastMCP for demo servers..."
	pip install fastmcp
	@echo ""
	@echo "✓ Installation complete!"
	@echo ""
	@echo "This example uses two simple Python MCP servers:"
	@echo "  • mcp1.py - Calculator tools (add, subtract, multiply, divide)"
	@echo "  • mcp2.py - Echo tools (ping, echo, reverse, uppercase, etc.)"
	@echo ""
	@echo "To start the server:"
	@echo "  make start"
	@echo ""
	@echo "To use the AI agent (in another terminal):"
	@echo "  make install-agent"
	@echo "  make agent"

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

# Start the MCP Compose server with SSE transport
start:
	@echo "Starting MCP Compose with SSE transport..."
	@echo ""
	@echo "⚠️  Note: SSE transport is deprecated."
	@echo "   Consider using proxy-streamable-http instead."
	@echo ""
	@echo "📡 Server will be available at: http://localhost:8080/sse"
	@echo ""
	mcp-compose serve --config mcp_compose.toml --transport sse

# Run the AI agent
agent:
	@echo "Starting AI Agent with SSE Transport..."
	@echo ""
	@echo "⚠️  Make sure the MCP Compose is running!"
	@echo "   (Run 'make start' in another terminal)"
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
	@echo "  - AZURE_OPENAI_ENDPOINT (base URL, e.g., https://your-resource.openai.azure.com)"
	@echo "  - AZURE_OPENAI_API_VERSION (optional)"
	@echo ""
	python agent.py $(MODEL)

# Stop the composer (use Ctrl+C in the terminal where it's running)
stop:
	@echo "To stop the composer, press Ctrl+C in the terminal where it's running"

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f *.log nohup.out
	@rm -f .composer.pid composer.log
	@rm -rf __pycache__
	@echo "✓ Cleanup complete"
