"""
Example demonstrating OpenTelemetry instrumentation with mcp-compose.

This example shows how to instrument mcp-compose to send traces to Logfire
or any OpenTelemetry-compatible backend.

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


# Option 1: Using Logfire
def setup_with_logfire():
    """Setup instrumentation using Logfire."""
    import logfire
    from mcp_compose import instrument_mcp_compose
    
    # Configure Logfire (reads token from env or config)
    logfire.configure(
        service_name="mcp-compose-example",
    )
    
    # Instrument mcp-compose
    instrument_mcp_compose(logfire)
    
    return logfire


# Option 2: Using plain OpenTelemetry SDK
def setup_with_otel():
    """Setup instrumentation using plain OpenTelemetry."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from mcp_compose import instrument_mcp_compose
    
    if not LOGFIRE_TOKEN:
        raise ValueError("DATALAYER_LOGFIRE_TOKEN environment variable is required")
    
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
    
    return provider


async def example_composition():
    """Example showing mcp-compose operations being traced."""
    from mcp_compose import MCPServerComposer, ConflictResolution
    
    # Create a composer - operations will be automatically traced
    composer = MCPServerComposer(
        composed_server_name="traced-example",
        conflict_resolution=ConflictResolution.PREFIX,
    )
    
    print(f"Created composer: {composer.composed_server_name}")
    print(f"Tools composed: {len(composer.composed_tools)}")
    
    return composer


async def main():
    """Main entry point."""
    
    # Choose instrumentation method based on available packages
    try:
        import logfire
        print("Using Logfire for instrumentation")
        tracer = setup_with_logfire()
        
        # Run example with Logfire span
        with logfire.span("mcp-compose example"):
            await example_composition()
            
        # Force flush to ensure spans are sent
        tracer.force_flush()
        
    except ImportError:
        print("Logfire not available, using plain OpenTelemetry")
        provider = setup_with_otel()
        
        # Run example
        await example_composition()
        
        # Force flush
        provider.force_flush()
    
    print("\n✓ Example complete!")
    print(f"View traces at: {LOGFIRE_URL}/datalayer/{LOGFIRE_PROJECT}")


if __name__ == "__main__":
    asyncio.run(main())
