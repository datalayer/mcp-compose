<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://images.datalayer.io/legacy/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# Streamable HTTP Transport Example

This example demonstrates how to use MCP Compose with **Streamable HTTP transport**. This is the modern, recommended HTTP transport for MCP that replaces the deprecated SSE transport.

## 🎯 Overview

This example shows:

1. **Two MCP Servers**: Calculator and Echo servers (`mcp1.py`, `mcp2.py`)
2. **Streamable HTTP Transport**: Modern HTTP-based MCP communication
3. **Unified Access**: Single interface to all tools from multiple servers

```
┌─────────────────────────────────────────────────────────────┐
│                     Pydantic AI Agent                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              MCPServerStreamableHTTP                   │  │
│  │        (connects to http://localhost:8888/mcp)         │  │
│  └──────────────────────┬─────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────┘
                          │ HTTP (Streamable HTTP transport)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP Compose Server                         │
│              (http://localhost:8888/mcp)                     │
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

- **Streamable HTTP Transport**: Modern, recommended MCP transport (SSE is deprecated)
- **Server Mode**: MCP Compose runs as a persistent server
- **Multiple Clients**: Multiple agents can connect simultaneously
- **REST-like**: Standard HTTP semantics for easier integration
- **Unified Interface**: All tools accessible through a single endpoint

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
- Expose a unified Streamable HTTP endpoint at `http://localhost:8888/mcp`

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

## 🔧 How Streamable HTTP Transport Works

With Streamable HTTP transport, the **server runs independently**:

1. **Server starts**: `mcp-compose serve --transport streamable-http`
2. **Endpoint exposed**: Server listens at `http://localhost:8888/mcp`
3. **Clients connect**: Using `MCPServerStreamableHTTP` from pydantic-ai
4. **Communication**: Standard HTTP requests with streaming responses

This is different from STDIO transport where the client spawns the server.

### Agent Code Snippet

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

# Create MCP server connection with Streamable HTTP transport
mcp_server = MCPServerStreamableHTTP(
    url="http://localhost:8888/mcp",
    timeout=300.0,
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

### Streamable HTTP vs SSE

| Feature | Streamable HTTP | SSE (deprecated) |
|---------|-----------------|------------------|
| Endpoint | `/mcp` | `/sse` |
| Protocol | Modern HTTP streaming | Server-Sent Events |
| Status | **Recommended** | Deprecated |
| Bidirectional | Yes | Limited |

## 📁 Files

| File | Description |
|------|-------------|
| `mcp_compose.toml` | Configuration for the MCP servers |
| `mcp1.py` | Calculator MCP server (add, subtract, multiply, divide) |
| `mcp2.py` | Echo MCP server (ping, echo, reverse, uppercase, etc.) |
| `agent.py` | Pydantic AI agent using Streamable HTTP transport |
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

## 🔍 When to Use Streamable HTTP Transport

**Use Streamable HTTP when:**
- ✅ Multiple clients need to connect
- ✅ Server should persist beyond client sessions
- ✅ Deploying as a standalone service
- ✅ Need standard HTTP for load balancers, proxies
- ✅ Using modern MCP features

**Use STDIO when:**
- ❌ Single client, local usage
- ❌ Client should manage server lifecycle
- ❌ Simpler deployment without network

## 📚 Learn More

- **[STDIO Example](../proxy-stdio/)** - STDIO transport (subprocess)
- **[SSE Example](../proxy-sse/)** - SSE transport (deprecated)
- **[User Guide](../../docs/USER_GUIDE.md)** - Complete feature documentation
- **[Architecture](../../docs/ARCHITECTURE.md)** - System design

## 🤝 Contributing

Found an issue or want to improve this example? Please open an issue or PR!

## 📄 License

BSD 3-Clause License - see [LICENSE](../../LICENSE)

---

**Made with ❤️ by [Datalayer](https://datalayer.ai)**
