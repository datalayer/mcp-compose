# OpenTelemetry Instrumentation Example

This example demonstrates how to instrument mcp-compose for observability using OpenTelemetry,
sending traces to Logfire.

## Files

- `mcp_compose.toml` - MCP Compose configuration with two servers
- `mcp1.py` - Calculator MCP server (add, subtract, multiply, divide)
- `mcp2.py` - Echo MCP server (ping, echo, reverse, uppercase, lowercase, count_words)
- `agent.py` - Pydantic AI agent with OpenTelemetry tracing

## Prerequisites

Install the dependencies:

```bash
make install
# Or manually:
pip install -e ../..[otel]
pip install fastmcp
```

For the agent, also install pydantic-ai:
```bash
make install-agent
# Or manually:
pip install 'pydantic-ai[mcp]'
```

## Configuration

Set the required environment variables:

```bash
export DATALAYER_LOGFIRE_TOKEN="your-write-token"
export DATALAYER_LOGFIRE_PROJECT="your-project"
export DATALAYER_LOGFIRE_URL="https://logfire-us.pydantic.dev"
```

Create a write token at: https://logfire-us.pydantic.dev/your-org/your-project/settings/write-tokens

## Usage

### Run the mcp-compose Server with Tracing

```bash
make serve
# Or directly:
mcp-compose serve -c mcp_compose.toml --transport streamable-http --port 8000
```

### Run the AI Agent with Tracing

```bash
make agent
# Or:
python agent.py
```

The agent connects to mcp-compose via STDIO and all MCP operations are traced to Logfire.

## View Traces

After running the examples, view your traces at:
```
https://logfire-us.pydantic.dev/datalayer/{DATALAYER_LOGFIRE_PROJECT}
```

## Quick Start with setup_otel()

The simplest way to enable tracing in your code:

```python
from mcp_compose import setup_otel

# One-line setup - reads config from environment variables
provider, tracer = setup_otel(service_name="my-app")

# Create custom spans
with tracer.start_as_current_span("my-operation") as span:
    span.set_attribute("key", "value")
    # ... your code ...

# Flush on shutdown
provider.force_flush()
```

## Usage with plain OpenTelemetry

You can also use the instrumentation with any OpenTelemetry-compatible backend:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from mcp_compose import instrument_mcp_compose

# Configure your tracer provider
provider = TracerProvider()
trace.set_tracer_provider(provider)

# Instrument mcp-compose
instrument_mcp_compose(tracer_provider=provider)
```

## What Gets Traced

The instrumentation provides **both client-side and server-side tracing**.

### Client-Side Tracing (Agent/Client)

When you call `instrument_mcp_compose()` in your agent or client code, it traces:

- **Tool Discovery**: When tools are discovered from child MCP servers
- **Tool Calls**: Each MCP tool call with arguments and results
- **Server Composition**: Operations like `compose_from_pyproject` and `compose_from_discovery`
- **Tool Registration**: When tools are registered with conflict resolution
- **Process Management**: Starting and stopping child processes

### Server-Side Tracing (mcp-compose serve)

When running `mcp-compose serve` with environment variables set, the server automatically:

- Configures OpenTelemetry with OTLP exporter to Logfire
- Instruments all mcp-compose components
- Traces incoming tool calls from clients
- Traces proxy calls to upstream MCP servers
- Flushes traces on shutdown

**Environment variables for server-side tracing:**
```bash
export DATALAYER_LOGFIRE_TOKEN="your-write-token"
export DATALAYER_LOGFIRE_PROJECT="your-project"
export DATALAYER_LOGFIRE_URL="https://logfire-us.pydantic.dev"
```

When these are set, running `mcp-compose serve` will output:
```
📊 OpenTelemetry tracing enabled
   Traces: https://logfire-us.pydantic.dev/datalayer/your-project
```

## Span Attributes

The instrumentation adds the following attributes to spans:

| Attribute | Description |
|-----------|-------------|
| `mcp.operation` | The operation being performed |
| `mcp.server.name` | Name of the MCP server |
| `mcp.tool.name` | Name of the tool being called |
| `mcp.tool.arguments` | JSON-encoded tool arguments |
| `mcp.tools.count` | Number of tools discovered/registered |
| `rpc.system` | Always "jsonrpc" for MCP operations |
| `rpc.method` | The JSON-RPC method being called |
