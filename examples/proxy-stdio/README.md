<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# STDIO Transport Example

This example demonstrates how to use MCP Compose with **STDIO transport**. The agent spawns the MCP Compose as a subprocess and communicates via standard input/output.

## 🎯 Overview

This example shows:

1. **Two MCP Servers**: Calculator and Echo servers (`mcp1.py`, `mcp2.py`)
2. **STDIO Transport**: The agent spawns `mcp-compose` as a subprocess
3. **Unified Access**: Single interface to all tools from multiple servers

```
┌─────────────────────────────────────────────────────────────┐
│                     Pydantic AI Agent                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  MCPServerStdio                        │  │
│  │         (spawns mcp-compose subprocess)                │  │
│  └──────────────────────┬─────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────┘
                          │ STDIO (stdin/stdout)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP Compose                                │
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

- **STDIO Transport**: Agent spawns MCP Compose as a subprocess
- **No Separate Server**: No need to start the composer in another terminal
- **Process Lifecycle**: Agent manages the subprocess lifecycle automatically
- **Unified Interface**: All tools accessible through a single connection
- **Pure Python**: No external dependencies beyond FastMCP and pydantic-ai

## 🚀 Quick Start

### 1. Install Dependencies

```bash
make install
```

This will install:
- `mcp-compose` (the orchestrator)
- `fastmcp` (for the demo MCP servers)

### 2. Install Agent Dependencies

```bash
make install-agent
```

This will install:
- `pydantic-ai[mcp]` (AI agent with MCP support)

### 3. Run the Agent

```bash
make agent
```

**That's it!** The agent automatically:
- Spawns `mcp-compose` as a subprocess
- Connects via STDIO transport
- Provides access to all tools from both servers

### Example Interactions

Once the agent is running:
- "What is 15 plus 27?"
- "Multiply 8 by 9"
- "Reverse the text 'hello world'"
- "Convert 'Hello World' to uppercase"
- "Count the words in 'The quick brown fox jumps'"

## 🔧 How STDIO Transport Works

With STDIO transport, the **client spawns the server** as a subprocess:

1. **Agent starts**: Creates an `MCPServerStdio` pointing to `mcp-compose`
2. **Subprocess spawned**: `mcp-compose serve --transport stdio` is executed
3. **Communication**: JSON-RPC messages flow through stdin/stdout
4. **Lifecycle managed**: Agent cleans up subprocess when done

This is different from SSE transport where the server runs independently.

### Agent Code Snippet

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

# Create MCP server connection with STDIO transport
mcp_server = MCPServerStdio(
    'mcp-compose',
    args=['serve', '--config', 'mcp_compose.toml', '--transport', 'stdio'],
    timeout=300.0,
)

# Create agent with MCP tools
agent = Agent(
    model="anthropic:claude-sonnet-4-0",
    toolsets=[mcp_server],
)

# Use async context manager to manage subprocess
async with agent:
    result = await agent.run("What is 5 + 3?")
```

## 📁 Files

| File | Description |
|------|-------------|
| `mcp_compose.toml` | Configuration for the MCP servers |
| `mcp1.py` | Calculator MCP server (add, subtract, multiply, divide) |
| `mcp2.py` | Echo MCP server (ping, echo, reverse, uppercase, etc.) |
| `agent.py` | Pydantic AI agent using STDIO transport |
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
| `make agent` | Run the AI agent (spawns composer) |
| `make clean` | Clean up temporary files |

## 🔍 When to Use STDIO Transport

**Use STDIO when:**
- ✅ Single client connecting to the MCP server
- ✅ You want the client to manage server lifecycle
- ✅ Running locally without network overhead
- ✅ Simpler deployment (no server to manage separately)

**Use SSE/HTTP when:**
- ❌ Multiple clients need to connect
- ❌ Server should persist beyond client sessions
- ❌ Need HTTP-based authentication/authorization
- ❌ Deploying as a standalone service

## 📚 Learn More

- **[SSE Example](../proxy-sse/)** - Server-Sent Events transport
- **[Streamable HTTP Example](../proxy-streamable-http/)** - Modern HTTP transport
- **[User Guide](../../docs/USER_GUIDE.md)** - Complete feature documentation
- **[Architecture](../../docs/ARCHITECTURE.md)** - System design

## 🤝 Contributing

Found an issue or want to improve this example? Please open an issue or PR!

## 📄 License

BSD 3-Clause License - see [LICENSE](../../LICENSE)

---

**Made with ❤️ by [Datalayer](https://datalayer.ai)**
