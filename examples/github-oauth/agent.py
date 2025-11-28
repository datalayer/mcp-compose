#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic AI Agent with MCP Compose - GitHub OAuth2 Example

This agent demonstrates how to connect a pydantic-ai agent to the MCP Compose
using generic OAuth2 authentication with GitHub as the identity provider.

This example uses standard OAuth2/OIDC token validation via GitHub's userinfo
endpoint (https://api.github.com/user). This demonstrates how to use GitHub
OAuth with mcp-compose.

Features:
- Connection to MCP Compose via Streamable HTTP transport
- OAuth2 authentication via GitHub
- Interactive CLI interface powered by pydantic-ai
- Access to Calculator and Echo server tools through the composer

Authentication Flow:
1. Client obtains OAuth token via GitHub OAuth flow (browser-based)
2. Client sends bearer token to MCP Compose
3. MCP Compose validates token via GitHub's API (https://api.github.com/user)
4. Request proceeds if token is valid

Usage:
    # First start the composer server:
    make start
    
    # Then in another terminal, run the agent:
    python agent.py

Configuration:
    See mcp_compose.toml for the generic OAuth2 configuration with GitHub endpoints.
    See config.json for GitHub OAuth client credentials.

Servers:
- Calculator Server (mcp1.py): add, subtract, multiply, divide
- Echo Server (mcp2.py): ping, echo, reverse, uppercase, lowercase, count_words
"""

import sys
import io
import asyncio

# Pydantic AI imports
try:
    from pydantic_ai import Agent
    from pydantic_ai.mcp import MCPServerStreamableHTTP
    HAS_PYDANTIC_AI = True
except ImportError:
    HAS_PYDANTIC_AI = False
    print("❌ Error: pydantic-ai not installed")
    print("   Install with: pip install 'pydantic-ai[mcp]'")
    sys.exit(1)


def get_github_token(server_url: str = "http://localhost:8080") -> str:
    """
    Get GitHub OAuth access token via MCP Compose server's OAuth flow.
    
    The flow works as follows:
    1. Agent starts local callback server on port 8888
    2. Agent opens browser to MCP Compose /authorize endpoint
    3. MCP Compose redirects to GitHub for authentication
    4. GitHub redirects back to MCP Compose /oauth/callback
    5. MCP Compose exchanges code for token and redirects to agent's callback
    6. Agent receives token from callback
    
    Tries to get token from:
    1. Environment variable GITHUB_TOKEN
    2. OAuth flow via MCP Compose server
    
    Args:
        server_url: MCP Compose server URL (default: http://localhost:8080)
    
    Returns:
        Access token string
    """
    import os
    
    # First check for environment variable
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        print("\n🔐 Using GitHub token from GITHUB_TOKEN environment variable")
        return token
    
    print("\n🔐 Authenticating with GitHub via MCP Compose server...")
    print("   No GITHUB_TOKEN environment variable found.")
    print("   Starting OAuth flow...")
    
    try:
        import webbrowser
        import secrets
        import threading
        import http.server
        import socketserver
        import urllib.parse
        from urllib.parse import urlencode
        
        # Callback configuration
        callback_port = 8888
        callback_path = "/callback"
        callback_uri = f"http://localhost:{callback_port}{callback_path}"
        
        # Storage for the received token
        received_token = None
        received_username = None
        received_state = None
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(16)
        
        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            """HTTP handler for OAuth callback"""
            
            def log_message(self, format, *args):
                pass  # Suppress logging
            
            def do_GET(self):
                nonlocal received_token, received_username, received_state
                
                # Parse query parameters
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                
                if self.path.startswith(callback_path):
                    received_token = params.get("token", [None])[0]
                    received_username = params.get("username", [None])[0]
                    received_state = params.get("state", [None])[0]
                    
                    if received_token:
                        # Send success response
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        username_display = received_username or 'User'
                        self.wfile.write(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Authentication Successful</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
        }}
        h1 {{ color: #667eea; margin-bottom: 20px; }}
        .success-icon {{ font-size: 60px; margin-bottom: 20px; }}
        .user-info {{ color: #667eea; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✅</div>
        <h1>Authentication Successful!</h1>
        <p class="user-info">Authenticated as: {username_display}</p>
        <p>You can close this window and return to the terminal.</p>
        <script>setTimeout(function() {{ window.close(); }}, 3000);</script>
    </div>
</body>
</html>
""".encode())
                    else:
                        error = params.get("error", ["Unknown error"])[0]
                        self.send_response(400)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Authentication Failed</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #d32f2f;">❌ Authentication Failed</h1>
    <p>Error: {error}</p>
</body>
</html>
""".encode())
                else:
                    self.send_response(404)
                    self.end_headers()
        
        # Build authorization URL
        auth_params = {
            "redirect_uri": callback_uri,
            "state": state,
            "response_type": "code",
        }
        auth_url = f"{server_url}/authorize?{urlencode(auth_params)}"
        
        print(f"\n🌐 Starting local callback server on port {callback_port}...")
        print(f"📋 Opening browser for GitHub authentication...")
        print(f"   Server: {server_url}")
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Wait for callback
        with socketserver.TCPServer(("", callback_port), CallbackHandler) as httpd:
            httpd.timeout = 120  # 2 minute timeout
            httpd.handle_request()
        
        # Verify we got a token
        if not received_token:
            raise Exception("No token received from callback")
        
        # Verify state matches
        if received_state != state:
            raise Exception("State mismatch - possible CSRF attack")
        
        if received_username:
            print(f"✅ Authenticated as: {received_username}")
        else:
            print("✅ Successfully authenticated with GitHub")
        
        return received_token
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        print("")
        print("   Make sure the MCP Compose server is running with OAuth enabled:")
        print("   cd examples/github-oauth && make start")
        print("")
        print("   You can also set the GITHUB_TOKEN environment variable:")
        print("   export GITHUB_TOKEN='your-github-personal-access-token'")
        sys.exit(1)


def create_agent(model: str = "anthropic:claude-sonnet-4-0", server_url: str = "http://localhost:8080") -> tuple[Agent, str]:
    """
    Create a pydantic-ai Agent connected to the MCP Compose
    
    Args:
        model: Model string in format 'provider:model-name' (e.g., 'anthropic:claude-sonnet-4-0', 'openai:gpt-4o')
               For Azure OpenAI, use 'azure-openai:deployment-name'
        server_url: MCP Compose base URL
    
    Returns:
        Tuple of (configured pydantic-ai Agent, access token)
    
    Note:
        For Azure OpenAI, requires these environment variables:
        - AZURE_OPENAI_API_KEY
        - AZURE_OPENAI_ENDPOINT (base URL only, e.g., https://your-resource.openai.azure.com)
        - AZURE_OPENAI_API_VERSION (optional, defaults to latest)
    """
    print("\n" + "=" * 70)
    print("🤖 Pydantic AI Agent with MCP Compose")
    print("=" * 70)
    
    # Get GitHub access token
    access_token = get_github_token()
    
    print(f"\n📡 Connecting to MCP Compose: {server_url}/mcp")
    print("   Unified access to Calculator and Echo servers")
    print("   Using GitHub bearer token authentication")
    
    # Create MCP server connection with Streamable HTTP transport and authentication
    mcp_server = MCPServerStreamableHTTP(
        url=f"{server_url}/mcp",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        # Increase timeout for long-running tool calls
        timeout=300.0,  # 5 minutes
    )
    
    print(f"\n🤖 Initializing Agent with {model}")
    
    # Handle Azure OpenAI specially - needs OpenAIChatModel with provider='azure'
    model_obj = model
    if model.startswith('azure-openai:'):
        from pydantic_ai.models.openai import OpenAIChatModel
        deployment_name = model.split(':', 1)[1]
        model_obj = OpenAIChatModel(deployment_name, provider='azure')
        print(f"   Using Azure OpenAI deployment: {deployment_name}")
    
    # Create Agent with the specified model
    # The agent will have access to all tools from both servers
    agent = Agent(
        model=model_obj,
        toolsets=[mcp_server],
        system_prompt="""You are a helpful AI assistant with access to Calculator and Echo MCP server tools.

The tools are provided by two MCP servers managed by the composer:
- Calculator server: Math operations (calculator:add, calculator:subtract, calculator:multiply, calculator:divide)
- Echo server: String operations (echo:ping, echo:echo, echo:reverse, echo:uppercase, echo:lowercase, echo:count_words)

Tool names are prefixed with their server name to avoid conflicts.

When the user first connects, greet them and list all the available tools you have access to with a brief description of each.

When users ask you to perform calculations or string operations, use the appropriate tools.
Be friendly and explain what you're doing."""
    )
    
    print("✅ Agent created successfully!")
    
    return agent, access_token


def main():
    """Main entry point for the AI agent"""
    # Ensure UTF-8 encoding for emoji support
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # Parse command-line arguments
    model = "anthropic:claude-sonnet-4-0"  # Default model
    if len(sys.argv) > 1:
        model = sys.argv[1]
    
    try:
        print("\n" + "=" * 70)
        print("🚀 MCP Compose Agent")
        print("=" * 70)
        print(f"\nUsing model: {model}")
        print("\n⚠️  IMPORTANT: Make sure the MCP Compose is running!")
        print("   Run in another terminal: make start")
        print("\nConnecting to server at http://localhost:8080...")
        
        # Create agent with MCP server connection
        agent, access_token = create_agent(model=model)
        
        # List all available tools from the server using MCP SDK
        async def list_tools(access_token: str):
            """List all tools available from the MCP server"""
            try:
                # Import MCP SDK client for streamable HTTP
                from mcp import ClientSession
                from mcp.client.streamable_http import streamablehttp_client
                
                # Connect using Streamable HTTP client with authentication
                async with streamablehttp_client(
                    "http://localhost:8080/mcp",
                    headers={"Authorization": f"Bearer {access_token}"}
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        # Initialize the session
                        await session.initialize()
                        
                        # List tools
                        tools_result = await session.list_tools()
                        tools = tools_result.tools
                        
                        print("\n🔧 Available Tools:")
                        
                        for tool in tools:
                            name = tool.name
                            params = []
                            
                            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                                schema = tool.inputSchema
                                if isinstance(schema, dict) and "properties" in schema:
                                    params = list(schema["properties"].keys())
                            
                            param_str = f"({', '.join(params)})" if params else "()"
                            print(f"   • {name}{param_str}")
                        
                        print(f"\n   Total: {len(tools)} tools")
                        
            except Exception as e:
                print(f"\n⚠️  Could not list tools: {e}")
                print("   The agent will still work with available tools")
                import traceback
                traceback.print_exc()
        
        asyncio.run(list_tools(access_token))
        
        # Launch interactive CLI
        print("\n" + "=" * 70)
        print("🚀 Launching Interactive CLI")
        print("=" * 70)
        print("\nYou can now chat with the AI agent!")
        print("The agent has access to Calculator and Echo server tools.")
        print("\nCommands:")
        print("  /exit     - Exit the CLI")
        print("  /markdown - Toggle markdown rendering")
        print("  /multiline - Enter multiline mode")
        print("  /cp       - Copy last response to clipboard")
        print("\nExamples:")
        print("  'What is 15 plus 27?'")
        print("  'Multiply 8 by 9'")
        print("  'Reverse the text hello world'")
        print("  'Convert Python to uppercase'")
        print("  'How many words are in the quick brown fox'")
        print("\n" + "=" * 70 + "\n")
        
        # Launch the CLI interface
        async def _run_cli() -> None:
            assert agent is not None
            async with agent:
                await agent.to_cli(prog_name='github-oauth')

        asyncio.run(_run_cli())
    
    except KeyboardInterrupt:
        print("\n\n🛑 Agent stopped by user")
    except BaseExceptionGroup as exc:
        print("\n❌ Encountered errors while running the CLI:")
        for idx, sub_exc in enumerate(exc.exceptions, start=1):
            print(f"  [{idx}] {type(sub_exc).__name__}: {sub_exc}")
        
        print("\n" + "=" * 70)
        print("⚠️  CONNECTION ISSUE")
        print("=" * 70)
        print("\nThe agent cannot connect because the SSE endpoint is not yet")
        print("implemented in the serve command.")
        print("\nCurrent Status:")
        print("  ✅ Child servers (mcp1.py, mcp2.py) start successfully")
        print("  ❌ No SSE endpoint exposed at http://localhost:8080/sse")
        print("\nWhat's Needed:")
        print("  The serve command needs to be enhanced to:")
        print("  1. Create a unified FastMCP server")
        print("  2. Expose SSE transport at /sse endpoint")
        print("  3. Proxy requests between SSE clients and STDIO child servers")
        print("\nThis is documented in IMPLEMENTATION_STATUS.md")
        print("=" * 70)
        raise
    except ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print("   Make sure the MCP Compose is running on port 8080")
        print("   (Run: make start in another terminal)")
        print("\n⚠️  NOTE: The unified SSE endpoint is not yet implemented!")
        print("   The serve command currently only starts child processes.")
        print("   The SSE endpoint at http://localhost:8080/sse will be added soon.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
