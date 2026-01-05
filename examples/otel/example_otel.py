"""
Example demonstrating OpenTelemetry instrumentation with mcp-compose.

This example shows how to instrument mcp-compose to send traces to Logfire
using the OpenTelemetry SDK directly (no interactive prompts).

Required environment variables:
    export DATALAYER_LOGFIRE_TOKEN="your-write-token"
    export DATALAYER_LOGFIRE_PROJECT="your-project"
    export DATALAYER_LOGFIRE_URL="https://logfire-us.pydantic.dev"
"""

import asyncio
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)

# Read configuration from environment variables
LOGFIRE_TOKEN = os.environ.get("DATALAYER_LOGFIRE_TOKEN")
LOGFIRE_PROJECT = os.environ.get("DATALAYER_LOGFIRE_PROJECT", "starter-project")
LOGFIRE_URL = os.environ.get("DATALAYER_LOGFIRE_URL", "https://logfire-us.pydantic.dev")


def setup_otel():
    """Setup OpenTelemetry instrumentation for mcp-compose."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from mcp_compose import instrument_mcp_compose
    
    if not LOGFIRE_TOKEN:
        raise ValueError(
            "DATALAYER_LOGFIRE_TOKEN environment variable is required.\n"
            "Get a write token from: https://logfire-us.pydantic.dev/datalayer/starter-project/settings/write-tokens"
        )
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": "mcp-compose-example",
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
    
    print(f"✓ OpenTelemetry configured")
    print(f"  Traces: {LOGFIRE_URL}/datalayer/{LOGFIRE_PROJECT}")
    
    return provider, trace.get_tracer("mcp-compose-example")


async def example_composition(tracer):
    """Example showing mcp-compose operations being traced."""
    from mcp_compose import MCPServerComposer, ConflictResolution
    
    # Create a span for the example
    with tracer.start_as_current_span("example_composition") as span:
        span.set_attribute("example.name", "mcp-compose-otel-demo")
        
        # Create a composer - operations will be automatically traced
        composer = MCPServerComposer(
            composed_server_name="traced-example",
            conflict_resolution=ConflictResolution.PREFIX,
        )
        
        span.set_attribute("composer.name", composer.composed_server_name)
        span.set_attribute("composer.tools_count", len(composer.composed_tools))
        
        print(f"\nCreated composer: {composer.composed_server_name}")
        print(f"Tools composed: {len(composer.composed_tools)}")
    
    return composer


async def main():
    """Main entry point."""
    print("OpenTelemetry Example for mcp-compose\n")
    
    # Setup OpenTelemetry
    provider, tracer = setup_otel()
    
    # Create a root span for the entire example
    with tracer.start_as_current_span("mcp-compose-example") as root_span:
        root_span.set_attribute("example.type", "otel-demo")
        
        # Run the example composition
        await example_composition(tracer)
    
    # Force flush to ensure all spans are sent
    provider.force_flush()
    
    print("\n✓ Example complete!")
    print(f"View traces at: {LOGFIRE_URL}/datalayer/{LOGFIRE_PROJECT}")


if __name__ == "__main__":
    asyncio.run(main())
