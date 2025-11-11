#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic AI Agent with MCP Compose

This agent demonstrates how to connect a pydantic-ai agent to the MCP Compose.
The composer manages multiple MCP servers and exposes them through a unified endpoint.

Features:
- Connection to MCP Compose via SSE transport
- Interactive CLI interface powered by pydantic-ai
- Access to Calculator and Echo server tools through the composer
- Uses Anthropic Claude Sonnet 4.5 model

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
import asyncio

# Pydantic AI imports
try:
    from pydantic_ai import Agent
    from pydantic_ai.mcp import MCPServerSSE
    HAS_PYDANTIC_AI = True
except ImportError:
    HAS_PYDANTIC_AI = False
    print("❌ Error: pydantic-ai not installed")
    print("   Install with: pip install 'pydantic-ai[mcp]'")
    sys.exit(1)


def create_agent(model: str = "anthropic:claude-sonnet-4-0", server_url: str = "http://localhost:8080") -> Agent:
    """
    Create a pydantic-ai Agent connected to the MCP Compose
    
    Args:
        model: Model string in format 'provider:model-name' (e.g., 'anthropic:claude-sonnet-4-0', 'openai:gpt-4o')
               For Azure OpenAI, use 'azure-openai:deployment-name'
        server_url: MCP Compose base URL
    
    Returns:
        Configured pydantic-ai Agent
    
    Note:
        For Azure OpenAI, requires these environment variables:
        - AZURE_OPENAI_API_KEY
        - AZURE_OPENAI_ENDPOINT (base URL only, e.g., https://your-resource.openai.azure.com)
        - AZURE_OPENAI_API_VERSION (optional, defaults to latest)
    """
    print("\n" + "=" * 70)
    print("🤖 Pydantic AI Agent with MCP Compose")
    print("=" * 70)
    
    print(f"\n📡 Connecting to MCP Compose: {server_url}/sse")
    print("   Unified access to Calculator and Echo servers")
    
    # Create MCP server connection with SSE transport
    # No authentication required for this example
    mcp_server = MCPServerSSE(
        url=f"{server_url}/sse",
        # Increase read timeout for long-running tool calls
        read_timeout=300.0,  # 5 minutes
        # Allow retries for transient failures
        max_retries=2
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
    
    return agent


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
        agent = create_agent(model=model)
        
        # List all available tools from the server using MCP SDK
        async def list_tools():
            """List all tools available from the MCP server"""
            try:
                # Import MCP SDK client
                from mcp import ClientSession
                from mcp.client.sse import sse_client
                
                # Connect using SSE client
                async with sse_client("http://localhost:8080/sse") as (read, write):
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
        
        asyncio.run(list_tools())
        
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
                await agent.to_cli(prog_name='proxy-anonymous-agent')

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
