# Pydantic AI Agent with MCP Server

This document explains how to use the interactive AI agent (`agent.py`) that connects to the authenticated MCP server using **pydantic-ai**.

## Overview

The agent provides a natural language interface to the MCP server tools, powered by **Anthropic Claude Sonnet 4.5**. Instead of manually calling tools through the client API, you can simply chat with the AI agent and it will automatically use the appropriate tools.

## Features

- 🤖 **Natural Language Interface** - Talk to the agent in plain English
- 🔐 **OAuth2 Authentication** - Automatic GitHub OAuth flow
- 🛠️ **MCP Tool Access** - Agent has access to all server tools
- 💬 **Interactive CLI** - Rich command-line interface with markdown support
- 🧠 **Smart Tool Selection** - Agent automatically chooses the right tools
- 📝 **Context Awareness** - Maintains conversation history

## Quick Start

1. **Start the MCP server** (in one terminal):
   ```bash
   make start
   # Or: python -m mcp_oauth_example server
   ```

2. **Launch the agent** (in another terminal):
   ```bash
   make agent
   # Or: python -m mcp_oauth_example agent
   ```

3. **Authenticate**: The agent will open your browser for GitHub OAuth

4. **Chat with the agent**:
   ```
   You: What is 15 + 27?
   Agent: [Uses calculator_add tool] The answer is 42!
   
   You: Multiply 8 by 9
   Agent: [Uses calculator_multiply tool] 8 multiplied by 9 equals 72.
   
   You: Say hello to Alice
   Agent: [Uses greeter_hello tool] Hello Alice! 👋
   ```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Input (Natural Language)            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Pydantic AI Agent (agent.py)                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Anthropic Claude Sonnet 4.5 (LLM)                  │   │
│  │  - Understands user intent                          │   │
│  │  - Decides which tools to use                       │   │
│  │  - Generates natural responses                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  MCPServerStreamableHTTP (pydantic_ai.mcp)          │   │
│  │  - URL: http://localhost:8080/mcp                   │   │
│  │  - Auth: Bearer token from OAuth                    │   │
│  │  - Tools: calculator_*, greeter_*, get_server_info  │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              MCP Server (server.py)                         │
│  - Validates Bearer token with GitHub                       │
│  - Executes tool functions                                  │
│  - Returns results via HTTP Streaming (NDJSON)              │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **OAuth Client** (`oauth_client.py`)
   - Handles GitHub OAuth2 authentication
   - Manages PKCE flow for security
   - Returns access token for MCP server

3. **Agent Setup** (`agent.py`)
   - Creates `httpx.AsyncClient` with Bearer token
   - Initializes `MCPServerStreamableHTTP` connection
   - Creates `Agent` with Anthropic Claude model
   - Registers MCP server as toolset

4. **Tool Invocation Flow**
   - User types natural language query
   - Agent (Claude) analyzes query and decides which tool to call
   - Agent calls tool via MCP protocol (HTTP Streaming)
   - MCP server validates token and executes tool
   - Agent receives result and formulates response
   - Agent displays natural language answer to user

## Code Walkthrough

### Authentication
```python
from oauth_client import OAuthClient

# Create OAuth client (shared with client.py)
oauth = OAuthClient("config.json", verbose=True)

# Authenticate with GitHub (opens browser)
if oauth.authenticate():
    token = oauth.get_token()
    server_url = oauth.get_server_url()
```

### Agent Creation
```python
import httpx
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

# Create HTTP client with authentication
http_client = httpx.AsyncClient(
    headers={"Authorization": f"Bearer {token}"},
    timeout=30.0
)

# Connect to MCP server
mcp_server = MCPServerStreamableHTTP(
    url=f"{server_url}/mcp",
    http_client=http_client
)

# Create agent with Claude Sonnet 4.5
agent = Agent(
    model='anthropic:claude-sonnet-4-0',
    toolsets=[mcp_server],
    system_prompt="You are a helpful AI assistant..."
)
```

### CLI Launch
```python
# Launch interactive CLI
agent.to_cli_sync()
```

## CLI Commands

The agent CLI supports these special commands:

- `/exit` - Exit the CLI
- `/markdown` - Toggle markdown rendering
- `/multiline` - Enter multiline mode for longer prompts
- `/cp` - Copy the last response to clipboard

## Example Conversations

### Calculator Operations
```
You: What is 42 plus 17?

Agent: I'll calculate that for you!

[Tool: calculator_add(a=42, b=17)]
Result: 59

The answer is 59.
```

### Multiple Tool Calls
```
You: Calculate 5 times 8, then add 10 to the result

Agent: I'll do this step by step.

[Tool: calculator_multiply(a=5, b=8)]
Result: 40

[Tool: calculator_add(a=40, b=10)]
Result: 50

First, 5 times 8 equals 40.
Then, adding 10 to 40 gives us 50.
```

### Greetings
```
You: Say hello to Bob and goodbye to Alice

Agent: I'll greet and bid farewell for you!

[Tool: greeter_hello(name="Bob")]
Result: Hello Bob! 👋

[Tool: greeter_goodbye(name="Alice")]
Result: Goodbye Alice! 👋 See you next time!

I've said hello to Bob and goodbye to Alice.
```

### Server Information
```
You: What can you tell me about the server?

Agent: Let me check the server information.

[Tool: get_server_info()]
Result: {
  "name": "Simple MCP Server with GitHub OAuth",
  "version": "1.0.0",
  "authentication": "GitHub OAuth2 with PKCE",
  "tools": 5
}

The server is running "Simple MCP Server with GitHub OAuth" 
version 1.0.0. It uses GitHub OAuth2 with PKCE for authentication 
and provides 5 tools.
```

## Environment Variables

Set `ANTHROPIC_API_KEY` environment variable for Anthropic Claude:

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
make agent
```

Alternatively, configure in pydantic-ai's configuration file.

## Comparison: Client vs Agent

| Feature | `client.py` | `agent.py` |
|---------|-------------|------------|
| **Interface** | Programmatic API | Natural language |
| **Usage** | Direct tool calls | Conversational |
| **Tool Selection** | Manual | Automatic by AI |
| **Best For** | Integration, testing | Interactive use, demos |
| **Authentication** | Shared OAuth logic | Shared OAuth logic |
| **Output** | Structured data | Natural language |

## Troubleshooting

### Agent Can't Find Tools
**Problem**: Agent says it doesn't have access to tools

**Solution**: 
- Ensure MCP server is running (`make start`)
- Check that OAuth authentication succeeded
- Verify the Bearer token is being sent in headers

### Authentication Fails
**Problem**: OAuth flow doesn't complete

**Solution**:
- Check `config.json` has correct GitHub OAuth credentials
- Ensure callback URL in GitHub OAuth app is `http://localhost:8081/callback`
- Make sure port 8081 is available

### Model Not Available
**Problem**: "Model 'anthropic:claude-sonnet-4-0' not found"

**Solution**:
- Set `ANTHROPIC_API_KEY` environment variable
- Check your Anthropic API subscription includes Claude Sonnet 4
- Try alternative model: `'anthropic:claude-3-5-sonnet-20241022'`

## Advanced Usage

### Custom System Prompt

Modify the `system_prompt` in `agent.py` to customize agent behavior:

```python
agent = Agent(
    model='anthropic:claude-sonnet-4-0',
    toolsets=[mcp_server],
    system_prompt="""You are a math tutor assistant.
    
    When students ask math questions, use the calculator tools
    and explain each step clearly. Be encouraging and patient."""
)
```

### Different Models

Change the model to use different LLM providers:

```python
# OpenAI GPT-4
agent = Agent(model='openai:gpt-4', toolsets=[mcp_server])

# Google Gemini
agent = Agent(model='google:gemini-1.5-pro', toolsets=[mcp_server])
```

### Programmatic Usage

Use the agent programmatically instead of CLI:

```python
async def main():
    result = await agent.run('What is 15 + 27?')
    print(result.output)
    # Output: "The answer is 42."
    
asyncio.run(main())
```

## Learn More

- **Pydantic AI Documentation**: https://ai.pydantic.dev/
- **Pydantic AI MCP Client**: https://ai.pydantic.dev/mcp/client/
- **Pydantic AI CLI**: https://ai.pydantic.dev/cli/
- **MCP Specification**: https://modelcontextprotocol.io/
- **Anthropic Claude**: https://www.anthropic.com/claude

## Next Steps

1. **Extend Tools**: Add more MCP tools to `server.py`
2. **Custom Prompts**: Modify system prompt for specific use cases
3. **Multiple Agents**: Create specialized agents for different domains
4. **Tool Composition**: Build complex workflows with multiple tool calls
5. **Error Handling**: Add robust error handling and recovery
6. **Logging**: Integrate with pydantic-ai's logfire for observability
