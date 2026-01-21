# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Authentication Example

Run the server with:
    python -m mcp_oauth_example server

Run the client with:
    python -m mcp_oauth_example client

Run the pydantic-ai agent with:
    python -m mcp_oauth_example agent

Or use the installed scripts:
    mcp-oauth-server
    mcp-oauth-client
    mcp-oauth-agent
"""

import sys


def main():
    """Main entry point for the package"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python -m mcp_oauth_example server    # Run the MCP server")
        print("  python -m mcp_oauth_example client    # Run the MCP client demo")
        print("  python -m mcp_oauth_example agent     # Run the pydantic-ai agent CLI")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "server":
        from mcp_oauth_example.server import main as server_main
        server_main()
    elif command == "client":
        from mcp_oauth_example.client import main as client_main
        client_main()
    elif command == "agent":
        from mcp_oauth_example.agent import main as agent_main
        agent_main()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
