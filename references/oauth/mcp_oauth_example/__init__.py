# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Authentication Example

A demonstration of using Pydantic AI Agent with an authenticated MCP server.

Features:
- OAuth2 authentication with GitHub
- MCP server with Bearer token authentication
- Interactive CLI agent powered by pydantic-ai
- Access to calculator and greeter tools via MCP

Usage:
    # Install the package
    pip install -e .
    
    # Run the MCP server
    mcp-oauth-server
    
    # Run the test client
    mcp-oauth-client
    
    # Run the AI agent
    mcp-oauth-agent

Or use the Python module:
    python -m mcp_oauth_example server
    python -m mcp_oauth_example client
    python -m mcp_oauth_example agent
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
