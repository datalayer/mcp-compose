# OAuth Flow Documentation

## Overview

The MCP Auth example now supports **automated OAuth flow** for agent.py and client.py, eliminating the need for manual token input.

## Supported Clients

### 1. Agent/Client (Automated) - NEW ✨

**Callback URL**: `http://localhost:8888/callback`

**Flow Type**: Direct GitHub token (legacy flow)

**Behavior**:
- Starts a local HTTP server on port 8888
- Opens browser for GitHub authentication
- Automatically captures the GitHub access token from callback
- No manual copy/paste required
- Auto-closes browser window after 3 seconds

**Usage**:
```bash
make agent
# or
make client
```

The authentication is now fully automated!

### 2. MCP Inspector

**Callback URL**: `http://localhost:6274/oauth/callback` (Inspector's own callback)

**Flow Type**: OAuth 2.0 Authorization Code + PKCE

**Behavior**:
- Full OAuth 2.0 flow with authorization code exchange
- Inspector exchanges code for JWT token at `/token` endpoint
- MCP server issues its own JWT tokens (HS256)

**Usage**:
```bash
make inspector
```

### 3. Claude Desktop

**Callback URL**: Configured in Claude Desktop settings

**Flow Type**: OAuth 2.0 Authorization Code + PKCE

**Behavior**:
- Full OAuth 2.0 flow per MCP specification
- Metadata discovery via `.well-known` endpoints
- JWT token issuance by MCP server
- Token used for all MCP tool invocations

## Flow Detection Logic

The server's `/oauth/callback` endpoint detects which flow to use:

```python
# Legacy flows use direct GitHub token (not authorization code):
# 1. Server's own /callback endpoint (old agent/client)
# 2. localhost:8888/callback (new agent/client with automated callback)
is_legacy_flow = (
    redirect_uri == f"{config.server_url}/callback" or
    redirect_uri.startswith("http://localhost:8888/")
)

if is_legacy_flow:
    # Redirect with GitHub token: ?token=...&state=...&username=...
    callback_url = f"{redirect_uri}?token={gh_token}&state={state}&username={username}"
else:
    # Inspector/Claude Desktop: issue authorization code
    auth_code = gen_random()
    # Store code for exchange at /token endpoint
    callback_url = f"{redirect_uri}?code={auth_code}&state={state}"
```

## GitHub OAuth App Configuration

Configure your GitHub OAuth App with these callback URLs:

1. `http://localhost:8080/oauth/callback` - Server's OAuth callback (receives GitHub code)
2. `http://localhost:8888/callback` - Agent/Client automated callback (optional, for additional security)

**Note**: The server's callback (`http://localhost:8080/oauth/callback`) is the primary callback that receives the GitHub authorization code. The server then redirects to the client's callback URL with either:
- A GitHub token (for agent/client)
- An authorization code (for Inspector/Claude Desktop)

## Architecture

```
┌─────────────┐
│   GitHub    │
│   OAuth     │
└──────┬──────┘
       │ 1. User authorizes
       ↓
┌──────────────────────────┐
│  MCP Server (port 8080)  │
│  /oauth/callback         │
└────────┬─────────────────┘
         │
         ├─→ Legacy Flow (Agent/Client)
         │   2. Extract GitHub token
         │   3. Redirect to http://localhost:8888/callback?token=...
         │   
         └─→ Modern Flow (Inspector/Claude)
             2. Issue authorization code
             3. Redirect to client callback?code=...
             4. Client exchanges code at /token for JWT

┌──────────────────────────┐
│  Client Callback Server  │
│  (port 8888)            │
└──────────────────────────┘
         │
         ↓
    4. Token captured automatically
    5. Display success page
    6. Auto-close browser
```

## Benefits

### Before (Manual)
1. User authenticates with GitHub
2. Server displays token in browser
3. User copies token manually
4. User pastes token in terminal
5. Continue...

### After (Automated)
1. User authenticates with GitHub
2. Token automatically captured
3. Browser auto-closes
4. Continue immediately!

## Testing

1. **Start the server**:
   ```bash
   make server
   ```

2. **Test automated agent flow**:
   ```bash
   make agent
   ```
   - Browser opens automatically
   - Authenticate with GitHub
   - Browser shows success and auto-closes
   - Agent continues automatically

3. **Test Inspector flow**:
   ```bash
   make inspector
   ```
   - Enter server URL: `http://localhost:8080/mcp`
   - Click "Connect"
   - Authenticate with GitHub
   - Inspector receives authorization code
   - Exchanges for JWT token
   - Connected!

## Troubleshooting

### Port 8888 already in use

If you see an error about port 8888:
```bash
# Find the process using port 8888
lsof -i :8888

# Kill it
kill -9 <PID>
```

Or change the port in `oauth_client.py`:
```python
@property
def callback_url(self) -> str:
    return "http://localhost:9999/callback"  # Change port
```

And update the callback server:
```python
self.callback_server = HTTPServer(('localhost', 9999), CallbackHandler)  # Change port
```

### Browser doesn't auto-close

Some browsers prevent JavaScript from closing windows. This is normal - just close it manually.

### Token verification fails

Make sure:
1. Server is running on port 8080
2. GitHub OAuth app is configured correctly
3. `config.json` has correct client_id and client_secret
