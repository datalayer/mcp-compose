# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

.PHONY: help install install-agent agent clean

# Default target
help:
	@echo "STDIO Transport Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose and MCP servers"
	@echo "  install-agent  - Install pydantic-ai for agent support"
	@echo "  agent          - Run the AI agent (spawns composer automatically)"
	@echo "  clean          - Clean up temporary files"
	@echo ""
	@echo "Note: With STDIO transport, you don't need to start the composer"
	@echo "      separately. The agent spawns it as a subprocess."
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
	@echo "To use the AI agent (spawns composer automatically):"
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
	@echo "  make agent"
	@echo ""
	@echo "Note: With STDIO transport, the agent spawns the composer"
	@echo "      automatically - no need to start it separately!"

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
	AWS_ACCESS_KEY_ID=${DATALAYER_BEDROCK_AWS_ACCESS_KEY_ID} \
	AWS_SECRET_ACCESS_KEY=${DATALAYER_BEDROCK_AWS_SECRET_ACCESS_KEY} \
	AWS_DEFAULT_REGION=${DATALAYER_BEDROCK_AWS_DEFAULT_REGION} \
	  python agent.py "bedrock:us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f *.log nohup.out
	@rm -f .composer.pid composer.log
	@rm -rf __pycache__
	@echo "✓ Cleanup complete"
