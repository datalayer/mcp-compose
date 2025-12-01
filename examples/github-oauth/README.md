<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# GitHub OAuth2 Authentication Example

This example demonstrates how to use MCP Compose with **generic OAuth2 token validation** using GitHub as the identity provider.

## 🎯 Overview

This example uses the generic OAuth2 provider in mcp-compose to validate GitHub OAuth tokens via the GitHub API userinfo endpoint (`https://api.github.com/user`).

| Feature | Description |
|---------|-------------|
| **Authentication** | `oauth2` (generic) provider |
| **Token Validation** | GitHub API userinfo endpoint |
| **Configuration** | `[authentication.oauth2]` |
| **Use Case** | GitHub-based authentication for any MCP Compose setup |

This configuration launches two simple Python MCP servers behind an authenticated MCP Compose:

1. **Calculator Server** (`mcp1.py`) - Math operations (add, subtract, multiply, divide)
   - Transport: **STDIO** (managed by composer)
2. **Echo Server** (`mcp2_http.py`) - String operations (ping, echo, reverse, uppercase, lowercase, count_words)
   - Transport: **HTTP Streaming** with JSON Lines protocol (standalone HTTP server on port 8082)
   - Alternative: `mcp2_sse.py` for SSE transport (port 8081)

Both servers:
- Run in **proxy mode** (STDIO and SSE transports)
- Are managed/proxied by the MCP Compose
- Are accessed through the **composer's authentication layer**

## 🔐 Authentication Architecture

```
┌─────────────┐
│   Client    │
│  (Agent)    │
└──────┬──────┘
       │ HTTP/SSE + Bearer Token
       ▼
┌─────────────────────────────┐
│    MCP Compose              │
│  ┌─────────────────────┐    │
│  │ OAuth2 Token        │    │ ← Validates via GitHub API
│  │ Validator           │    │   userinfo endpoint
│  └─────────┬───────────┘    │
│            │                 │
│            ▼                 │
│  ┌─────────────────────┐    │
│  │ GitHub API          │◄───┼── https://api.github.com/user
│  │ (userinfo endpoint) │    │
│  └─────────────────────┘    │
│            │                 │
│  ┌─────────┴───────────┐    │
│  │  Tool Manager       │    │
│  └─────────┬───────────┘    │
└────────────┼─────────────────┘
             │ STDIO (no auth)
       ┌─────┴─────┐
       ▼           ▼
┌────────────┐ ┌────────────┐
│ Calculator │ │   Echo     │
│   Server   │ │   Server   │
└────────────┘ └────────────┘
```

**Key Points**:
- Authentication happens at the **MCP Compose level**
- Tokens are validated via **GitHub API userinfo endpoint**
- This pattern works with **any OAuth2/OIDC provider** (Google, Anaconda, Keycloak, etc.)

## 📋 Features

- **Generic OAuth2**: Works with any OAuth2-compliant provider
- **GitHub Integration**: Uses GitHub as the identity provider
- **Two Simple Servers**: Calculator and Echo servers with basic tools
- **Pure Python**: Minimal dependencies (FastMCP + requests)
- **Configuration-Based**: Define servers in `mcp_compose.toml`
- **Process Management**: Composer manages server lifecycles

## 🔑 Prerequisites

### 1. GitHub OAuth App

You need to create a GitHub OAuth App:

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the details:
   - **Application name**: MCP Compose Test (or any name)
   - **Homepage URL**: http://localhost:8080
   - **Authorization callback URL**: http://localhost:8080/oauth/callback
4. Click "Register application"
5. Copy the **Client ID** and generate a **Client Secret**

> **Note**: The callback URL is `http://localhost:8080/oauth/callback` because MCP Compose
> handles the GitHub OAuth flow. The agent receives the token via a local callback on port 8888.

### 2. Configure Credentials

Copy `config.template.json` to `config.json` and update with your credentials:

```bash
cp config.template.json config.json
```

Then edit `config.json`:

```json
{
  "oauth": {
    "authorization_endpoint": "https://github.com/login/oauth/authorize",
    "token_endpoint": "https://github.com/login/oauth/access_token",
    "userinfo_endpoint": "https://api.github.com/user",
    "client_id": "YOUR_GITHUB_CLIENT_ID",
    "client_secret": "YOUR_GITHUB_CLIENT_SECRET"
  },
  "server": {
    "host": "localhost",
    "port": 8080
  }
}
```

When `client_id` and `client_secret` are omitted from `mcp_compose.toml`, the
CLI now reads them from this `config.json` file automatically, keeping secrets
out of version-controlled configs. You can still hard-code them in the TOML if
you prefer.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
make install
```

This will install:
- `mcp-compose` (the orchestrator)
- `fastmcp` (for the demo MCP servers)
- `requests` (for OAuth client)

### 2. Configure GitHub OAuth

Create a GitHub OAuth App (see Prerequisites above) and update `config.json`.

### 3. Test OAuth Setup

```bash
make oauth-test
```

This will open your browser for GitHub authentication and display your access token.

### 4. Start the Echo HTTP Server

Start the echo server in HTTP streaming mode (in a separate terminal):

```bash
make start-echo-streamable-http
```

### 5. Start the Composer

In another terminal:

```bash
make start
```

The composer will:
- Read configuration from `mcp_compose.toml`
- Start the Calculator MCP server as a child process (STDIO)
- Connect to the Echo MCP server via HTTP (http://localhost:8082/stream)
- Listen on port 8080 for client connections
- Validate bearer tokens using GitHub's API

### 6. Run the AI Agent

```bash
make install-agent
make agent
```

The agent will:
- Prompt you for GitHub authentication (or use `GITHUB_TOKEN` env var)
- Connect to MCP Compose with the OAuth token
- Provide an interactive CLI for using the MCP tools

## 📁 Files

| File | Purpose |
|------|---------|
| `mcp_compose.toml` | MCP Compose configuration with GitHub OAuth |
| `config.json` | GitHub OAuth App credentials |
| `agent.py` | Pydantic AI agent with MCP Compose integration |
| `mcp1.py` | Calculator MCP server (STDIO) |
| `mcp2_http.py` | Echo MCP server (HTTP Streaming) |
| `mcp2_sse.py` | Echo MCP server (SSE - alternative) |

**Note**: The OAuth client functionality is provided by the `mcp_compose.oauth_client` module which includes `GitHubOAuthClient`.

## 🔧 Configuration

### mcp_compose.toml

```toml
[authentication]
enabled = true
providers = ["oauth2"]
default_provider = "oauth2"

[authentication.oauth2]
provider = "github"
# client_id/client_secret are optional; they'll be loaded from config.json when omitted
# client_id = "..."
# client_secret = "..."
authorization_endpoint = "https://github.com/login/oauth/authorize"
token_endpoint = "https://github.com/login/oauth/access_token"
userinfo_endpoint = "https://api.github.com/user"
user_id_claim = "login"  # GitHub username
```

The additional `authorization_endpoint` and `token_endpoint` values make the
OAuth relay generic: swap them (and `userinfo_endpoint`) to point at any other
OAuth2/OIDC provider without touching the Python code.

### Environment Variables

You can also use environment variables instead of the OAuth flow:

```bash
export GITHUB_TOKEN="your-github-personal-access-token"
make agent
```

## 📚 Related Examples

- **`oauth/`** - Standalone MCP server with full GitHub OAuth implementation
- **`anaconda-token/`** - Anaconda authentication using anaconda-auth library
- **`anaconda-oauth/`** - Anaconda authentication using generic OAuth2

## 📖 See Also

- [MCP Compose Documentation](../../docs/USER_GUIDE.md)
- [OAuth2 Architecture](../../docs/ARCHITECTURE.md#authentication)
- [GitHub OAuth Apps Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)
