#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic AI Agent with MCP Compose and OpenTelemetry Instrumentation

This agent demonstrates how to connect a pydantic-ai agent to the MCP Compose
using STDIO transport with full OpenTelemetry tracing to Logfire.

Features:
- Connection to MCP Compose via STDIO transport
- OpenTelemetry instrumentation for observability
- Interactive CLI interface powered by pydantic-ai
- Access to Calculator and Echo server tools through the composer
- Traces sent to Logfire for visualization

Required environment variables:
    export DATALAYER_LOGFIRE_TOKEN="your-write-token"
    export DATALAYER_LOGFIRE_PROJECT="your-project"
    export DATALAYER_LOGFIRE_URL="https://logfire-us.pydantic.dev"

Usage:
    python agent.py

Servers:
- Calculator Server (mcp1.py): add, subtract, multiply, divide
- Echo Server (mcp2.py): ping, echo, reverse, uppercase, lowercase, count_words
"""

import sys
import os
import asyncio

# Read Logfire configuration from environment
LOGFIRE_TOKEN = os.environ.get("DATALAYER_LOGFIRE_TOKEN")
LOGFIRE_PROJECT = os.environ.get("DATALAYER_LOGFIRE_PROJECT", "starter-project")
LOGFIRE_URL = os.environ.get("DATALAYER_LOGFIRE_URL", "https://logfire-us.pydantic.dev")

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


def setup_otel_instrumentation():
    """Setup OpenTelemetry instrumentation for mcp-compose."""
    if not LOGFIRE_TOKEN:
        print("⚠️  Warning: DATALAYER_LOGFIRE_TOKEN not set")
        print("   Traces will not be sent to Logfire")
        return None
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from mcp_compose import instrument_mcp_compose
        
        print("📊 Setting up OpenTelemetry instrumentation...")
        
        # Create resource with service information
        resource = Resource.create({
            "service.name": "mcp-compose-agent",
            "service.version": "1.0.0",
        })
        
        # Create tracer provider
        provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter for Logfire
        exporter = OTLPSpanExporter(
            endpoint=f"{LOGFIRE_URL}/v1/traces",
            headers={"Authorization": LOGFIRE_TOKEN},
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        
        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        
        # Instrument mcp-compose
        instrument_mcp_compose(tracer_provider=provider)
        
        print(f"   ✓ Traces will be sent to: {LOGFIRE_URL}/datalayer/{LOGFIRE_PROJECT}")
        return provider
        
    except ImportError as e:
        print(f"⚠️  Warning: OpenTelemetry not available: {e}")
        print("   Install with: pip install mcp_compose[otel]")
        return None


def create_agent(model: str = "anthropic:claude-sonnet-4-0") -> Agent:
    """
    Create a pydantic-ai Agent connected to the MCP Compose via STDIO
    
    Args:
        model: Model string in format 'provider:model-name'
    
    Returns:
        Configured pydantic-ai Agent
    """
    print("\n" + "=" * 70)
    print("🤖 Pydantic AI Agent with MCP Compose + OpenTelemetry")
    print("=" * 70)
    
    print("\n📡 Spawning MCP Compose as subprocess with STDIO transport")
    print("   Unified access to Calculator and Echo servers")
    
    # Create MCP server connection with STDIO transport
    mcp_server = MCPServerStdio(
        'mcp-compose',
        args=['serve', '--config', 'mcp_compose.toml', '--transport', 'stdio'],
        timeout=300.0,
    )
    
    print(f"\n🤖 Initializing Agent with {model}")
    
    # Handle Azure OpenAI specially
    model_obj = model
    if model.startswith('azure-openai:'):
        from pydantic_ai.models.openai import OpenAIChatModel
        deployment_name = model.split(':', 1)[1]
        model_obj = OpenAIChatModel(deployment_name, provider='azure')
        print(f"   Using Azure OpenAI deployment: {deployment_name}")
    
    # Create Agent with the specified model
    agent = Agent(
        model=model_obj,
        toolsets=[mcp_server],
        system_prompt="""You are a helpful AI assistant with access to MCP server tools provided by the MCP Compose.

When the user asks about your tools or capabilities, use the actual tools available to you from the MCP server.
Do NOT make up or assume tool names - only report tools that are actually available.

When users ask you to perform operations, use the appropriate tools.
Be friendly and explain what you're doing."""
    )
    
    return agent


async def interactive_loop(agent: Agent):
    """Run interactive conversation loop."""
    print("\n" + "-" * 70)
    print("💬 Interactive Mode")
    print("-" * 70)
    print("Type your questions or commands. Type 'quit' or 'exit' to stop.")
    print("Try: 'What tools do you have?' or 'Add 5 and 3'")
    print("-" * 70 + "\n")
    
    async with agent:
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ('quit', 'exit', 'q'):
                    print("\n👋 Goodbye!")
                    break
                
                print("\n🤔 Thinking...")
                result = await agent.run(user_input)
                print(f"\n🤖 Assistant: {result.output}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


async def main():
    """Main entry point."""
    # Setup OpenTelemetry instrumentation
    provider = setup_otel_instrumentation()
    
    # Create agent
    agent = create_agent()
    
    # Run interactive loop
    await interactive_loop(agent)
    
    # Flush traces
    if provider:
        print("\n📤 Flushing traces to Logfire...")
        provider.force_flush()
        print(f"   View traces at: {LOGFIRE_URL}/datalayer/{LOGFIRE_PROJECT}")


if __name__ == "__main__":
    asyncio.run(main())
