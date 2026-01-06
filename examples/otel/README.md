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

## What Gets Traced and Measured

The instrumentation provides **comprehensive tracing and metrics** following the Logfire pattern 
of external monkey-patching (non-intrusive instrumentation).

### Traces

#### Client-Side Tracing (Agent/Client)

When you call `instrument_mcp_compose()` in your agent or client code, it traces:

- **Tool Discovery**: When tools are discovered from child MCP servers
- **Tool Calls**: Each MCP tool call with arguments and results
- **JSON-RPC Requests**: All JSON-RPC communication with timing
- **Server Composition**: Operations like `compose_from_pyproject` and `compose_from_discovery`
- **Tool Registration**: When tools are registered with conflict resolution
- **Process Management**: Starting, stopping, and restarting child processes
- **Process I/O**: Message sending and receiving on STDIO
- **HTTP Transport**: Connection, send, and receive operations

#### Server-Side Tracing (mcp-compose serve)

When running `mcp-compose serve` with environment variables set, the server automatically:

- Configures OpenTelemetry with OTLP exporter to Logfire
- Instruments all mcp-compose components
- Traces incoming HTTP requests via middleware
- Traces tool invocations from clients
- Traces proxy calls to upstream MCP servers
- Flushes traces on shutdown

**Environment variables for server-side tracing:**
```bash
export DATALAYER_LOGFIRE_TOKEN="your-write-token"
export DATALAYER_LOGFIRE_PROJECT="your-project"
export DATALAYER_LOGFIRE_URL="https://logfire-us.pydantic.dev"
```

### Metrics

The instrumentation also exports the following metrics (requires `opentelemetry-exporter-otlp-proto-http`):

| Metric | Type | Description |
|--------|------|-------------|
| `mcp_compose.tool_calls_total` | Counter | Total number of tool calls |
| `mcp_compose.tool_call_duration_seconds` | Histogram | Duration of tool calls |
| `mcp_compose.tool_call_errors_total` | Counter | Total number of tool call errors |
| `mcp_compose.active_processes` | UpDownCounter | Number of active MCP server processes |
| `mcp_compose.process_restarts_total` | Counter | Total number of process restarts |
| `mcp_compose.jsonrpc_requests_total` | Counter | Total number of JSON-RPC requests |
| `mcp_compose.jsonrpc_request_duration_seconds` | Histogram | Duration of JSON-RPC requests |
| `mcp_compose.jsonrpc_errors_total` | Counter | Total number of JSON-RPC errors |
| `mcp_compose.tools_discovered_total` | Counter | Total number of tools discovered |
| `mcp_compose.servers_connected` | UpDownCounter | Number of connected MCP servers |
| `mcp_compose.http_requests_total` | Counter | Total number of HTTP requests |
| `mcp_compose.http_request_duration_seconds` | Histogram | Duration of HTTP requests |

## Span Attributes

The instrumentation adds the following attributes to spans:

| Attribute | Description |
|-----------|-------------|
| `mcp.operation` | The operation being performed |
| `mcp.server.name` | Name of the MCP server |
| `mcp.tool.name` | Name of the tool being called |
| `mcp.tool.id` | Full tool ID (server.tool_name) |
| `mcp.tool.arguments` | JSON-encoded tool arguments |
| `mcp.tool.result_preview` | Preview of tool result |
| `mcp.tools.count` | Number of tools discovered/registered |
| `mcp.duration_seconds` | Operation duration in seconds |
| `mcp.process.name` | Name of the child process |
| `mcp.process.pid` | Process ID |
| `mcp.process.command` | Command used to start process |
| `mcp.message.size_bytes` | Size of JSON-RPC message |
| `rpc.system` | Always "jsonrpc" for MCP operations |
| `rpc.method` | The JSON-RPC method being called |
| `rpc.jsonrpc.version` | JSON-RPC version (2.0) |
| `rpc.jsonrpc.request_id` | Request ID for correlation |
| `rpc.jsonrpc.error_code` | Error code if request failed |
| `rpc.jsonrpc.error_message` | Error message if request failed |
| `http.method` | HTTP method (GET, POST, etc.) |
| `http.url` | Full request URL |
| `http.status_code` | HTTP response status code |
