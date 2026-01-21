# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

.PHONY: help install install-agent install-ui build-ui start agent clean

# Default target
help:
	@echo "UI Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose and MCP servers"
	@echo "  install-ui     - Install UI dependencies"
	@echo "  build-ui       - Build UI artifacts"
	@echo "  install-agent  - Install pydantic-ai for agent support"
	@echo "  start          - Start MCP Compose with UI on port 9456"
	@echo "  agent          - Run the AI agent (spawns composer automatically)"
	@echo "  clean          - Clean up temporary files"
	@echo ""
	@echo "Quick Start:"
	@echo "  make install install-ui build-ui"
	@echo "  make start"
	@echo "  # Then open http://localhost:9456/ui (login: admin/demo123)"
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

# Install UI dependencies
install-ui:
	@echo "Installing UI dependencies..."
	cd ../../ui && npm install
	@echo "✓ UI dependencies installed!"

# Build UI
build-ui:
	@echo "Building UI..."
	cd ../../ui && npm run build
	@echo "✓ UI built successfully!"
	@echo ""
	@echo "UI artifacts are in ../../ui/dist/"

# Install pydantic-ai for agent support
install-agent:
	@echo "Installing pydantic-ai with MCP support..."
	pip install 'pydantic-ai[mcp]'
	@echo ""
	@echo "✓ Agent dependencies installed!"

# Start MCP Compose with UI
start:
	@echo "Starting MCP Compose with UI on port 9456..."
	@echo ""
	@echo "🌐 Web UI: http://localhost:9456/ui"
	@echo "📚 API Docs: http://localhost:9456/docs"
	@echo "🔐 Login credentials:"
	@echo "   Username: admin"
	@echo "   Password: demo123"
	@echo ""
	mcp-compose serve --config mcp_compose.toml --port 9456

# Run the AI agent (spawns composer as subprocess)
agent:
	@echo "Starting AI Agent with STDIO Transport..."
	@echo ""
	@echo "📋 STDIO Transport Mode:"
	@echo "   The agent will spawn mcp-compose as a subprocess"
	@echo "   No need to start the composer separately!"
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

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f *.log nohup.out
	@rm -f .composer.pid composer.log
	@rm -rf __pycache__
	@echo "✓ Cleanup complete"
