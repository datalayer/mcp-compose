#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Pydantic AI Agent with MCP Compose (Streamable HTTP Transport)

This agent demonstrates how to connect a pydantic-ai agent to the MCP Compose
using Streamable HTTP transport. This is the modern, recommended HTTP transport
for MCP that replaces the deprecated SSE transport.

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
1. Integrate pydantic-ai Agent with MCP Compose via Streamable HTTP
2. Access multiple MCP servers through a unified interface
3. Build interactive CLI agents with pydantic-ai
4. Understand modern HTTP-based MCP transport

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


def create_agent(model: str = "anthropic:claude-sonnet-4-0", server_url: str = "http://localhost:8888") -> Agent:
    """
    Create a pydantic-ai Agent connected to the MCP Compose via Streamable HTTP
    
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
    print("🤖 Pydantic AI Agent with MCP Compose (Streamable HTTP Transport)")
    print("=" * 70)
    
    print(f"\n📡 Connecting to MCP Compose: {server_url}/mcp")
    print("   Unified access to Calculator and Echo servers")
    
    # Create MCP server connection with Streamable HTTP transport
    # This is the modern, recommended transport (SSE is deprecated)
    mcp_server = MCPServerStreamableHTTP(
        url=f"{server_url}/mcp",
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

    server_url = os.environ.get("MCP_COMPOSE_URL", "http://localhost:8888")
    
    try:
        print("\n" + "=" * 70)
        print("🚀 MCP Compose Agent (Streamable HTTP Transport)")
        print("=" * 70)
        print(f"\nUsing model: {model}")
        print("\n⚠️  IMPORTANT: Make sure the MCP Compose is running!")
        print("   Run in another terminal: make start")
        print(f"\nConnecting to server at {server_url}/mcp...")
        
        # Create agent with MCP server connection
        agent = create_agent(model=model, server_url=server_url)
        
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
                await agent.to_cli(prog_name='proxy-streamable-http-agent')

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
        print("\nThe agent cannot connect to the MCP Compose.")
        print("\nTroubleshooting:")
        print("  1. Make sure mcp-compose is running: make start")
        print(f"  2. Check that the endpoint is {server_url}/mcp")
        print("  3. Verify no firewall blocking the MCP Compose port")
        print("=" * 70)
        raise
    except ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print(f"   Make sure the MCP Compose is running at {server_url}")
        print("   (Run: make start in another terminal)")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
