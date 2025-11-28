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
    mcp-auth-server
    
    # Run the test client
    mcp-auth-client
    
    # Run the AI agent
    mcp-auth-agent

Or use the Python module:
    python -m mcp_auth_example server
    python -m mcp_auth_example client
    python -m mcp_auth_example agent
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
