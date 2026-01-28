# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

.PHONY: help install install-agent agent clean

# Default target
help:
	@echo "STDIO Transport Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  agent          - Run the AI agent (spawns composer automatically)"
	@echo "  clean          - Clean up temporary files"
	@echo ""
	@echo "Note: With STDIO transport, you don't need to start the composer"
	@echo "      separately. The agent spawns it as a subprocess."
	@echo ""

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
	  python agent.py $(MODEL)

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f *.log nohup.out
	@rm -f .composer.pid composer.log
	@rm -rf __pycache__
	@echo "✓ Cleanup complete"
