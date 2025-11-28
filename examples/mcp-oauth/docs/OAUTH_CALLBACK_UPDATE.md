# OAuth Callback URL Update

## Overview

Updated the OAuth flow to work with the GitHub OAuth app callback URL change from `http://localhost:8081/callback` to `https://localhost:8080/oauth/callback`.

## Changes Made

### 1. Server Changes (`server.py`)

#### Updated `/oauth/callback` endpoint

Now detects legacy flows (agent/client) and handles them differently from Claude Desktop:

```python
# Check if this is a legacy flow (redirect_uri is our /callback endpoint)
redirect_uri = session["redirect_uri"]

if redirect_uri.endswith("/callback"):
    # Legacy flow: redirect to /callback with GitHub token
    callback_url = f"{redirect_uri}?token={gh_token}&state={state}&username={username}"
    return RedirectResponse(url=callback_url)
else:
    # Claude Desktop flow: issue authorization code for JWT
```

#### Updated `/callback` endpoint

Now receives the GitHub access token directly from `/oauth/callback` instead of exchanging an authorization code:

```python
@mcp.custom_route("/callback", ["GET"])
async def oauth_callback_legacy(request: Request):
    """
    Legacy OAuth callback endpoint for agent.py and client.py
    
    Receives GitHub access token from /oauth/callback and displays it
    to the user for copy/paste into their terminal.
    """
    token = request.query_params.get("token")
    username = request.query_params.get("username")
```

**Features:**
- Displays token in a beautiful HTML page with automatic clipboard copy
- Includes JavaScript to auto-close window after 30 seconds
- User-friendly instructions for pasting token in terminal
- Works with HTTPS and proper CORS

### 2. OAuth Client Changes (`oauth_client.py`)

#### Updated `callback_url` Property

Changed from hosting a local callback server to using the server's endpoint:

```python
@property
def callback_url(self) -> str:
    """Get the OAuth callback URL - uses server's /callback endpoint"""
    return f"{self.server_url}/callback"
```

#### Simplified `authenticate()` Method

**Before:** Started a local HTTP server on port 8081 to receive OAuth callback

**After:** Opens browser and prompts user to paste the token displayed by the server

Key improvements:
- ✅ No need to manage local callback server
- ✅ No port conflicts
- ✅ Works with HTTPS server
- ✅ Cleaner user experience
- ✅ Verifies token by making a test request to `/health` endpoint

#### Removed Unused Code

- Removed `OAuthCallbackHandler` class (no longer needed)
- Cleaned up imports:
  - Removed `http.server` imports (`HTTPServer`, `BaseHTTPRequestHandler`)
  - Removed `parse_qs`, `urlparse` imports
  - Removed `threading`, `time` imports
  - Added `os` import for file system operations

## User Flow

### Old Flow (Local Callback Server)
1. Agent starts local HTTP server on port 8081
2. Opens browser with GitHub OAuth URL
3. User authorizes on GitHub
4. GitHub redirects to `http://localhost:8081/callback`
5. Local server receives code and exchanges for token
6. Agent continues with token

**Problems:**
- Required port 8081 to be available
- HTTP vs HTTPS mismatch with server
- Complex threading for callback server
- GitHub OAuth app had to point to different URL

### New Flow (Server Callback)
1. Agent calls `/authorize` endpoint with `redirect_uri=https://localhost:8080/callback`
2. Server's `/authorize` redirects to GitHub with `redirect_uri=https://localhost:8080/oauth/callback`
3. User authorizes on GitHub
4. GitHub redirects to `https://localhost:8080/oauth/callback`
5. Server's `/oauth/callback` detects legacy flow, exchanges code for GitHub token
6. Server redirects to `https://localhost:8080/callback?token=...&username=...`
7. Browser displays token with automatic clipboard copy
8. User pastes token in terminal
9. Agent verifies token against `/health` endpoint and continues

**Benefits:**
- ✅ Consistent HTTPS communication
- ✅ No port management issues
- ✅ Simpler code (no local server needed)
- ✅ User can verify the token before using it
- ✅ Works with GitHub OAuth app callback to server

## Testing

### Test Agent Flow
```bash
cd examples/mcp-oauth
make agent
```

**Expected:**
1. Browser opens for GitHub authorization
2. After authorizing, browser shows token with copy button
3. Terminal prompts: "🔑 Paste your access token:"
4. Paste token and press Enter
5. Token is verified against `/health` endpoint
6. Agent starts with authenticated MCP connection

### Test Client Flow
```bash
cd examples/mcp-oauth
make client
```

Same flow as agent.

## Backward Compatibility

The `/callback` endpoint ensures backward compatibility for:
- ✅ `agent.py` - Pydantic-AI interactive agent
- ✅ `client.py` - MCP SDK demo client

Claude Desktop uses the `/oauth/callback` endpoint which issues JWT tokens instead.

## Security Notes

1. **Token Display**: The token is displayed in the browser for the user to copy. While this requires manual input, it:
   - Gives users visibility into what token they're using
   - Prevents automatic token theft from callback interception
   - Works with HTTPS and proper CORS

2. **Token Verification**: The client verifies the token by making a test request to the `/health` endpoint before proceeding

3. **Auto-Close**: The browser window automatically closes after 30 seconds to minimize token exposure

## Configuration

GitHub OAuth app settings:
- **Authorization callback URL**: `https://localhost:8080/oauth/callback`
- This single callback URL works for both Claude Desktop (JWT flow) and agent/client (GitHub token flow)

## Future Enhancements

Potential improvements:
1. Add WebSocket connection to automatically send token to waiting client
2. Implement QR code display for mobile OAuth flows
3. Add token expiration indicator in the browser UI
4. Support multiple concurrent authentication sessions
