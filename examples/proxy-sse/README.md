<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# SSE Transport Example

> ⚠️ **Note**: SSE (Server-Sent Events) transport is **deprecated**. For new projects, use **Streamable HTTP** transport instead. See [proxy-streamable-http](../proxy-streamable-http/).

This example demonstrates how to use MCP Compose with **SSE (Server-Sent Events) transport**. While deprecated, SSE is still supported for backward compatibility with existing clients.

## 🎯 Overview

This example shows:

1. **Two MCP Servers**: Calculator and Echo servers (`mcp1.py`, `mcp2.py`)
2. **SSE Transport**: HTTP-based Server-Sent Events for MCP communication
3. **Unified Access**: Single interface to all tools from multiple servers

```
┌─────────────────────────────────────────────────────────────┐
│                     Pydantic AI Agent                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  MCPServerSSE                          │  │
│  │        (connects to http://localhost:8080/sse)         │  │
│  └──────────────────────┬─────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────┘
                          │ HTTP (Server-Sent Events)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP Compose Server                         │
│              (http://localhost:8080/sse)                     │
│                                                              │
│  ┌─────────────────┐         ┌─────────────────┐            │
│  │   Calculator    │         │      Echo       │            │
│  │    (mcp1.py)    │         │    (mcp2.py)    │            │
│  │                 │         │                 │            │
│  │ • add           │         │ • ping          │            │
│  │ • subtract      │         │ • echo          │            │
│  │ • multiply      │         │ • reverse       │            │
│  │ • divide        │         │ • uppercase     │            │
│  │                 │         │ • lowercase     │            │
│  │                 │         │ • count_words   │            │
│  └─────────────────┘         └─────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Features

- **SSE Transport**: HTTP-based Server-Sent Events (deprecated, but supported)
- **Server Mode**: MCP Compose runs as a persistent server
- **Multiple Clients**: Multiple agents can connect simultaneously
- **Unified Interface**: All tools accessible through a single endpoint
- **Pure Python**: No external dependencies beyond FastMCP and pydantic-ai

## 🚀 Quick Start

### 1. Install Dependencies

```bash
make install
```

This will install:
- `mcp-compose` (the orchestrator)
- `fastmcp` (for the demo MCP servers)

### 2. Start the Composer Server

```bash
make start
```

The composer will:
- Read configuration from `mcp_compose.toml`
- Start both Calculator and Echo MCP servers
- Expose a unified SSE endpoint at `http://localhost:8080/sse`

### 3. Install Agent Dependencies

```bash
make install-agent
```

### 4. Run the Agent (in another terminal)

```bash
make agent
```

### Example Interactions

Once the agent is running:
- "What is 15 plus 27?"
- "Multiply 8 by 9"
- "Reverse the text 'hello world'"
- "Convert 'Hello World' to uppercase"
- "Count the words in 'The quick brown fox jumps'"

### 5. Stop the Composer

Press `Ctrl+C` in the terminal where the composer is running.

## 🔧 How SSE Transport Works

With SSE transport, the **server runs independently**:

1. **Server starts**: `mcp-compose serve --transport sse`
2. **Endpoint exposed**: Server listens at `http://localhost:8080/sse`
3. **Clients connect**: Using `MCPServerSSE` from pydantic-ai
4. **Communication**: Server-Sent Events over HTTP

### Agent Code Snippet

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerSSE

# Create MCP server connection with SSE transport
mcp_server = MCPServerSSE(
    url="http://localhost:8080/sse",
    read_timeout=300.0,
    max_retries=2,
)

# Create agent with MCP tools
agent = Agent(
    model="anthropic:claude-sonnet-4-0",
    toolsets=[mcp_server],
)

# Use async context manager
async with agent:
    result = await agent.run("What is 5 + 3?")
```

### SSE vs Streamable HTTP

| Feature | SSE | Streamable HTTP |
|---------|-----|-----------------|
| Endpoint | `/sse` | `/mcp` |
| Protocol | Server-Sent Events | Modern HTTP streaming |
| Status | **Deprecated** | Recommended |
| Legacy support | Yes | No |

## 📁 Files

| File | Description |
|------|-------------|
| `mcp_compose.toml` | Configuration for the MCP servers |
| `mcp1.py` | Calculator MCP server (add, subtract, multiply, divide) |
| `mcp2.py` | Echo MCP server (ping, echo, reverse, uppercase, etc.) |
| `agent.py` | Pydantic AI agent using SSE transport |
| `Makefile` | Convenience commands |

## ⚙️ Configuration

The `mcp_compose.toml` defines the managed MCP servers:

```toml
[composer]
name = "demo-composer"
conflict_resolution = "prefix"  # Tools become calculator:add, echo:ping, etc.
log_level = "INFO"

[[servers.proxied.stdio]]
name = "calculator"
command = ["python", "mcp1.py"]
restart_policy = "never"

[[servers.proxied.stdio]]
name = "echo"
command = ["python", "mcp2.py"]
restart_policy = "never"
```

## 🛠️ Makefile Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install mcp-compose and FastMCP |
| `make install-agent` | Install pydantic-ai with MCP support |
| `make start` | Start the MCP Compose server |
| `make agent` | Run the AI agent (requires composer running) |
| `make stop` | Stop the MCP Compose server |
| `make clean` | Clean up temporary files |

## 🔍 When to Use SSE Transport

**Consider SSE when:**
- ⚠️ You have existing clients that only support SSE
- ⚠️ You're maintaining legacy integrations

**For new projects, use:**
- ✅ **Streamable HTTP** for server mode ([proxy-streamable-http](../proxy-streamable-http/))
- ✅ **STDIO** for subprocess mode ([proxy-stdio](../proxy-stdio/))

## 📚 Learn More

- **[Streamable HTTP Example](../proxy-streamable-http/)** - Recommended HTTP transport
- **[STDIO Example](../proxy-stdio/)** - STDIO transport (subprocess)
- **[User Guide](../../docs/USER_GUIDE.md)** - Complete feature documentation
- **[Architecture](../../docs/ARCHITECTURE.md)** - System design

## 🤝 Contributing

Found an issue or want to improve this example? Please open an issue or PR!

## 📄 License

BSD 3-Clause License - see [LICENSE](../../LICENSE)

---

**Made with ❤️ by [Datalayer](https://datalayer.ai)**
