#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic AI Agent with MCP Compose (STDIO Transport)

This agent demonstrates how to connect a pydantic-ai agent to the MCP Compose
using STDIO transport. The agent spawns the MCP Compose as a subprocess and
communicates with it via standard input/output.

Features:
- Connection to MCP Compose via STDIO transport
- Interactive CLI interface powered by pydantic-ai
- Access to Calculator and Echo server tools through the composer
- Uses Anthropic Claude Sonnet 4 model

Usage:
    # Simply run the agent (no need to start composer separately):
    python agent.py

Learning Objectives:
1. Integrate pydantic-ai Agent with MCP Compose via STDIO
2. Access multiple MCP servers through a unified interface
3. Build interactive CLI agents with pydantic-ai
4. Understand STDIO transport where client spawns the server

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
    from pydantic_ai.mcp import MCPServerStdio
    HAS_PYDANTIC_AI = True
except ImportError:
    HAS_PYDANTIC_AI = False
    print("❌ Error: pydantic-ai not installed")
    print("   Install with: pip install 'pydantic-ai[mcp]'")
    sys.exit(1)


def create_agent(model: str = "anthropic:claude-sonnet-4-0") -> Agent:
    """
    Create a pydantic-ai Agent connected to the MCP Compose via STDIO
    
    Args:
        model: Model string in format 'provider:model-name' (e.g., 'anthropic:claude-sonnet-4-0', 'openai:gpt-4o')
               For Azure OpenAI, use 'azure-openai:deployment-name'
    
    Returns:
        Configured pydantic-ai Agent
    
    Note:
        For Azure OpenAI, requires these environment variables:
        - AZURE_OPENAI_API_KEY
        - AZURE_OPENAI_ENDPOINT (base URL only, e.g., https://your-resource.openai.azure.com)
        - AZURE_OPENAI_API_VERSION (optional, defaults to latest)
    """
    print("\n" + "=" * 70)
    print("🤖 Pydantic AI Agent with MCP Compose (STDIO Transport)")
    print("=" * 70)
    
    print("\n📡 Spawning MCP Compose as subprocess with STDIO transport")
    print("   Unified access to Calculator and Echo servers")
    
    # Create MCP server connection with STDIO transport
    # The agent spawns mcp-compose as a subprocess
    mcp_server = MCPServerStdio(
        'mcp-compose',
        args=['serve', '--config', 'mcp_compose.toml', '--transport', 'stdio'],
        timeout=300.0,  # 5 minutes timeout
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
    
    try:
        print("\n" + "=" * 70)
        print("🚀 MCP Compose Agent (STDIO Transport)")
        print("=" * 70)
        print(f"\nUsing model: {model}")
        print("\n📋 STDIO Transport Mode:")
        print("   The agent will spawn mcp-compose as a subprocess")
        print("   No need to start the composer separately!")
        
        # Create agent with MCP server connection
        agent = create_agent(model=model)
        
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
                await agent.to_cli(prog_name='proxy-stdio-agent')

        asyncio.run(_run_cli())
    
    except KeyboardInterrupt:
        print("\n\n🛑 Agent stopped by user")
    except BaseExceptionGroup as exc:
        print("\n❌ Encountered errors while running the CLI:")
        for idx, sub_exc in enumerate(exc.exceptions, start=1):
            print(f"  [{idx}] {type(sub_exc).__name__}: {sub_exc}")
        raise
    except FileNotFoundError as e:
        print(f"\n❌ Command not found: {e}")
        print("   Make sure mcp-compose is installed:")
        print("   pip install -e ../..")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
