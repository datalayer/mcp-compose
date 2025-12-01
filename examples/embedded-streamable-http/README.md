<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# Embedded MCP Servers with Streamable HTTP Transport

This example demonstrates how to use **embedded MCP servers** with MCP Compose over **Streamable HTTP transport**. This is the most efficient approach for local servers that can run in the same process.

## 🎯 Overview

This example shows:

1. **Embedded MCP Servers**: Calculator and Echo servers imported as Python modules
2. **Streamable HTTP Transport**: Modern HTTP-based MCP communication
3. **In-Process Execution**: Servers run in the same process as the composer (no STDIO overhead)
4. **Unified Access**: Single interface to all tools from multiple servers

```
┌─────────────────────────────────────────────────────────────┐
│                     Pydantic AI Agent                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              MCPServerStreamableHTTP                   │  │
│  │        (connects to http://localhost:8080/mcp)         │  │
│  └──────────────────────┬─────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────┘
                          │ HTTP (Streamable HTTP transport)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP Compose Server                         │
│              (http://localhost:8080/mcp)                     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         EMBEDDED SERVERS (in-process)               │    │
│  │                                                      │    │
│  │  ┌──────────────────┐    ┌──────────────────┐      │    │
│  │  │   Calculator     │    │      Echo        │      │    │
│  │  │ (imported module)│    │ (imported module)│      │    │
│  │  │                  │    │                  │      │    │
│  │  │ • add            │    │ • ping           │      │    │
│  │  │ • subtract       │    │ • echo           │      │    │
│  │  │ • multiply       │    │ • reverse        │      │    │
│  │  │ • divide         │    │ • uppercase      │      │    │
│  │  │                  │    │ • lowercase      │      │    │
│  │  │                  │    │ • count_words    │      │    │
│  │  └──────────────────┘    └──────────────────┘      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Features

- **Embedded Servers**: Servers run in the same process as the composer (no subprocess overhead)
- **Streamable HTTP Transport**: Modern, recommended MCP transport (SSE is deprecated)
- **High Performance**: Direct function calls without STDIO serialization
- **Simple Deployment**: Single process to manage and monitor
- **Multiple Clients**: Multiple agents can connect simultaneously
- **Unified Interface**: All tools accessible through a single endpoint

## 🔄 Embedded vs Proxied Servers

**Embedded Servers** (this example):
- Run in the same process as the composer
- Imported as Python modules
- No subprocess overhead or STDIO communication
- Best for: Local servers, development, simple deployments

**Proxied STDIO Servers** (see `../stdio-streamable-http/`):
- Run as separate subprocesses
- Communication via STDIO
- Process isolation and independent restarts
- Best for: External tools, isolation requirements, language diversity

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
- Expose a unified Streamable HTTP endpoint at `http://localhost:8080/mcp`

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
2. **Endpoint exposed**: Server listens at `http://localhost:8080/mcp`
3. **Clients connect**: Using `MCPServerStreamableHTTP` from pydantic-ai
4. **Communication**: Standard HTTP requests with streaming responses

This is different from STDIO transport where the client spawns the server.

### Agent Code Snippet

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

# Create MCP server connection with Streamable HTTP transport
mcp_server = MCPServerStreamableHTTP(
    url="http://localhost:8080/mcp",
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
| `mcp_compose.toml` | Configuration with embedded server definitions |
| `calculator_server.py` | Calculator MCP server module (add, subtract, multiply, divide) |
| `echo_server.py` | Echo MCP server module (ping, echo, reverse, uppercase, etc.) |
| `agent.py` | Pydantic AI agent using Streamable HTTP transport |
| `Makefile` | Convenience commands |

## ⚙️ Configuration

The `mcp_compose.toml` defines the embedded MCP servers:

```toml
[composer]
name = "demo-composer"
conflict_resolution = "prefix"  # Tools become calculator_add, echo_ping, etc.
log_level = "INFO"

# Embedded servers - imported as Python modules
[[servers.embedded.servers]]
name = "calculator"
package = "calculator_server"
enabled = true

[[servers.embedded.servers]]
name = "echo"
package = "echo_server"
enabled = true
```

The servers must be importable Python modules with an `mcp` object exported.

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
