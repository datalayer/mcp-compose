.PHONY: help install install-agent start agent stop clean

# Default target
help:
	@echo "Git-File MCP Server Composer Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose and MCP servers"
	@echo "  install-agent  - Install pydantic-ai for agent support"
	@echo "  start          - Start the MCP Server Composer (manages both servers)"
	@echo "  agent          - Run the AI agent (requires composer to be running)"
	@echo "  stop           - Stop the MCP Server Composer"
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
	@echo "✓ Installation complete!"
	@echo ""
	@echo "This example uses two simple Python MCP servers:"
	@echo "  • mcp1.py - Calculator tools (add, subtract, multiply, divide)"
	@echo "  • mcp2.py - Echo tools (ping, echo, reverse, uppercase, etc.)"
	@echo ""
	@echo "To start:"
	@echo "  make start"
	@echo ""
	@echo "To use the AI agent:"
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

# Start the MCP Server Composer
start:
	@echo "Starting MCP Server Composer..."
	@echo ""
	mcp-compose serve --config mcp_compose.toml

# Run the AI agent
agent:
	@echo "Starting AI Agent..."
	@echo ""
	@echo "⚠️  Make sure the MCP Server Composer is running!"
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
