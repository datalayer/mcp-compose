.PHONY: help install agent clean serve

# Default target
help:
	@echo "OpenTelemetry Instrumentation Example - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install mcp-compose with otel dependencies"
	@echo "  install-agent  - Install pydantic-ai for agent support"
	@echo "  serve          - Run mcp-compose server with OpenTelemetry tracing"
	@echo "  agent          - Run the AI agent with OpenTelemetry tracing"
	@echo "  otel-example   - Run a simple OpenTelemetry tracing example"
	@echo "  clean          - Clean up temporary files"
	@echo ""
	@echo "Required environment variables:"
	@echo "  DATALAYER_LOGFIRE_TOKEN   - Logfire write token"
	@echo "  DATALAYER_LOGFIRE_PROJECT - Logfire project name (default: starter-project)"
	@echo "  DATALAYER_LOGFIRE_URL     - Logfire URL (default: https://logfire-us.pydantic.dev)"
	@echo ""

# Install dependencies
install:
	@echo "Installing mcp-compose with OpenTelemetry support..."
	pip install -e ../..[otel]
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

# Install pydantic-ai for the agent
install-agent:
	@echo "Installing pydantic-ai with MCP support..."
	pip install 'pydantic-ai[mcp]'
	@echo ""
	@echo "✓ pydantic-ai installed!"

# Run mcp-compose server with OpenTelemetry tracing
serve:
	@echo "Starting mcp-compose server with OpenTelemetry instrumentation..."
	@echo ""
	@if [ -z "$$DATALAYER_LOGFIRE_TOKEN" ]; then \
		echo "⚠️  Warning: DATALAYER_LOGFIRE_TOKEN not set"; \
		echo "   Traces will not be sent to Logfire"; \
		echo ""; \
	fi
	mcp-compose serve -f mcp_compose.toml --transport streamable-http --port 8000

# Run the agent with OpenTelemetry tracing
agent:
	@echo "Starting AI Agent with OpenTelemetry instrumentation..."
	@echo ""
	@if [ -z "$$DATALAYER_LOGFIRE_TOKEN" ]; then \
		echo "⚠️  Warning: DATALAYER_LOGFIRE_TOKEN not set"; \
		echo "   Traces will not be sent to Logfire"; \
		echo ""; \
	fi
	python agent.py

# Run simple OpenTelemetry example
otel-example:
	@echo "Running OpenTelemetry example..."
	@echo ""
	@if [ -z "$$DATALAYER_LOGFIRE_TOKEN" ]; then \
		echo "❌ Error: DATALAYER_LOGFIRE_TOKEN not set"; \
		echo "   Set it with: export DATALAYER_LOGFIRE_TOKEN='your-token'"; \
		exit 1; \
	fi
	python example_otel.py

# Clean up
clean:
	@echo "Cleaning up..."
	rm -rf __pycache__
	rm -rf .logfire
	@echo "✓ Cleanup complete!"
