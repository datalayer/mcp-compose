"""
MCP Authentication Example

Run the server with:
    python -m mcp_auth_example server

Run the client with:
    python -m mcp_auth_example client

Run the pydantic-ai agent with:
    python -m mcp_auth_example agent

Or use the installed scripts:
    mcp-auth-server
    mcp-auth-client
    mcp-auth-agent
"""

import sys


def main():
    """Main entry point for the package"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python -m mcp_auth_example server    # Run the MCP server")
        print("  python -m mcp_auth_example client    # Run the MCP client demo")
        print("  python -m mcp_auth_example agent     # Run the pydantic-ai agent CLI")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "server":
        from mcp_auth_example.server import main as server_main
        server_main()
    elif command == "client":
        from mcp_auth_example.client import main as client_main
        client_main()
    elif command == "agent":
        from mcp_auth_example.agent import main as agent_main
        agent_main()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
