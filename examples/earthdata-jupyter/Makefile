# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

.PHONY: help install install-agent start agent clean

help:
	@echo "Earthdata + Jupyter composition"
	@echo ""
	@echo "  install        - Install mcp-compose, earthdata-mcp-server and jupyter-mcp-server"
	@echo "  install-agent  - Install pydantic-ai with MCP support"
	@echo "  start          - Start the composition (Streamable HTTP on :8888/mcp)"
	@echo "  agent          - Run the agent: discover, manifest, script, execute"
	@echo ""
	@echo "Environment: EARTHDATA_USERNAME, EARTHDATA_PASSWORD,"
	@echo "             DOCUMENT_URL, DOCUMENT_TOKEN, DOCUMENT_ID, RUNTIME_URL, RUNTIME_TOKEN"

install:
	pip install -e ../..
	pip install earthdata-mcp-server jupyter-mcp-server

install-agent:
	pip install 'pydantic-ai[mcp]'

start:
	mcp-compose -v serve --config mcp_compose.toml --transport streamable-http

agent:
	python agent.py

clean:
	@rm -f *.log nohup.out
	@rm -rf __pycache__
