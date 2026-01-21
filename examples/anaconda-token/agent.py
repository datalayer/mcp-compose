#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Pydantic AI Agent with MCP Compose

This agent demonstrates how to connect a pydantic-ai agent to the MCP Compose.
The composer manages multiple MCP servers and exposes them through a unified endpoint.

Features:
- Connection to MCP Compose via Streamable HTTP transport
- Interactive CLI interface powered by pydantic-ai
- Access to Calculator and Echo server tools through the composer
- Uses Anthropic Claude Sonnet 4 model

Usage:
    # First start the composer server:
    make start
    
    # Then in another terminal, run the agent:
    python agent.py

Learning Objectives:
1. Integrate pydantic-ai Agent with MCP Compose
2. Access multiple MCP servers through a unified interface
3. Build interactive CLI agents with pydantic-ai

Servers:
- Calculator Server (mcp1.py): add, subtract, multiply, divide
- Echo Server (mcp2.py): ping, echo, reverse, uppercase, lowercase, count_words
"""

import sys
import io
import os
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


def get_anaconda_token(auto_login: bool = False) -> str | None:
    """
    Get Anaconda access token.
    
    If MCP_COMPOSE_ANACONDA_TOKEN="fallback", returns None to allow
    the server to use its local anaconda_auth token.
    
    If no token is found and auto_login is True, initiates the login process via browser.
    If no token is found and auto_login is False, returns None (no auth header will be sent).
    
    Args:
        auto_login: If True, automatically trigger browser login when no token found.
    
    Returns:
        Access token string, or None if no token available
    """
    # Check if server is in fallback mode
    fallback_env = os.environ.get("MCP_COMPOSE_ANACONDA_TOKEN", "")
    if fallback_env == "fallback":
        print("\n🔐 Server fallback mode enabled")
        print("   Server will use its local anaconda_auth token")
        print("   No Bearer token will be sent from client")
        return None
    
    print("\n🔐 Getting Anaconda token...")
    try:
        from anaconda_auth.token import TokenInfo
        from anaconda_auth import login
        
        # Try to get existing token
        api_key = None
        try:
            token_info = TokenInfo().load()
            api_key = token_info.api_key if token_info else None
        except Exception:
            # No token stored yet, api_key remains None
            pass
        
        if api_key:
            print("✅ Using existing Anaconda authentication")
            return api_key
        else:
            if auto_login:
                # No token found, initiate login process
                print("⚠️  No Anaconda token found, initiating login...")
                print("   A browser window will open for authentication.")
                login()
                
                # Try to get token again after login
                try:
                    token_info = TokenInfo().load()
                    api_key = token_info.api_key if token_info else None
                except Exception:
                    api_key = None
                
                if api_key:
                    print("✅ Login successful!")
                    return api_key
                else:
                    print("⚠️  Login did not complete - continuing without authentication")
                    print("   No Authorization header will be sent")
                    return None
            else:
                print("⚠️  No Anaconda token found - continuing without authentication")
                print("   To authenticate: anaconda auth login")
                print("   Or run with --auto-login flag to automatically open browser")
                return None
        
    except ImportError:
        print("⚠️  anaconda-auth not installed - continuing without authentication")
        print("   Install with: pip install anaconda-auth")
        return None
    except Exception as e:
        print(f"⚠️  Could not get token: {e} - continuing without authentication")
        return None


def create_agent(model: str = "anthropic:claude-sonnet-4-0", server_url: str = "http://localhost:8080", auto_login: bool = False) -> tuple[Agent, str]:
    """
    Create a pydantic-ai Agent connected to the MCP Compose
    
    Args:
        model: Model string in format 'provider:model-name' (e.g., 'anthropic:claude-sonnet-4-0', 'openai:gpt-4o')
               For Azure OpenAI, use 'azure-openai:deployment-name'
        server_url: MCP Compose base URL
        auto_login: If True, automatically trigger browser login when no token found
    
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
    
    # Get Anaconda access token (None if fallback mode)
    access_token = get_anaconda_token(auto_login=auto_login)
    
    print(f"\n📡 Connecting to MCP Compose: {server_url}/mcp")
    print("   Unified access to Calculator and Echo servers")
    
    # Build headers - only add Authorization if we have a token
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
        print("   Using Anaconda bearer token authentication")
    else:
        print("   Using server-side fallback authentication")
    
    # Create MCP server connection with Streamable HTTP transport
    mcp_server = MCPServerStreamableHTTP(
        url=f"{server_url}/mcp",
        headers=headers if headers else None,
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
        system_prompt="""You are a helpful AI assistant with access to MCP server tools provided by the MCP Compose.

When the user asks about your tools or capabilities, use the actual tools available to you from the MCP server.
Do NOT make up or assume tool names - only report tools that are actually available.

When users ask you to perform operations, use the appropriate tools.
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
    import argparse
    parser = argparse.ArgumentParser(description="MCP Compose Agent with Anaconda authentication")
    parser.add_argument("model", nargs="?", default="anthropic:claude-sonnet-4-0",
                        help="Model to use (e.g., 'anthropic:claude-sonnet-4-0', 'openai:gpt-4o', 'azure-openai:gpt-4o-mini')")
    parser.add_argument("--auto-login", action="store_true",
                        help="Automatically open browser for Anaconda login if not authenticated")
    args = parser.parse_args()
    
    model = args.model
    auto_login = args.auto_login
    
    try:
        print("\n" + "=" * 70)
        print("🚀 MCP Compose Agent")
        print("=" * 70)
        print(f"\nUsing model: {model}")
        print("\n⚠️  IMPORTANT: Make sure the MCP Compose is running!")
        print("   Run in another terminal: make start")
        print("\nConnecting to server at http://localhost:8080...")
        
        # Create agent with MCP server connection
        agent, access_token = create_agent(model=model, auto_login=auto_login)
        
        # List all available tools from the server using MCP SDK
        async def list_tools(access_token: str | None):
            """List all tools available from the MCP server"""
            try:
                # Import MCP SDK client for streamable HTTP
                from mcp import ClientSession
                from mcp.client.streamable_http import streamablehttp_client
                
                # Build headers - only add Authorization if we have a token
                headers = {}
                if access_token:
                    headers["Authorization"] = f"Bearer {access_token}"
                
                # Connect using Streamable HTTP client
                async with streamablehttp_client(
                    "http://localhost:8080/mcp",
                    headers=headers if headers else None
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
            try:
                async with agent:
                    await agent.to_cli(prog_name='anaconda-token-agent')
            except BaseExceptionGroup as exc:
                # Check if this is an authentication error
                auth_error = False
                for sub_exc in exc.exceptions:
                    exc_str = str(sub_exc).lower()
                    if any(term in exc_str for term in ['401', 'unauthorized', 'authentication', 'forbidden', '403']):
                        auth_error = True
                        break
                
                if auth_error or access_token is None:
                    print("\n" + "=" * 70)
                    print("🔐 AUTHENTICATION REQUIRED")
                    print("=" * 70)
                    print("\nThe MCP Compose server requires authentication.")
                    print("\nTo authenticate:")
                    print("  1. Run: anaconda auth login")
                    print("  2. Or use: make agent-auto-login (to auto-open browser)")
                    print("\nAlternatively, if the server supports fallback mode:")
                    print("  export MCP_COMPOSE_ANACONDA_TOKEN=fallback")
                    print("=" * 70)
                else:
                    # Re-raise for other errors
                    raise

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
