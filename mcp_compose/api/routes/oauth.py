"""
OAuth2 callback routes for MCP Compose.

This module provides OAuth2 endpoints for the authorization code flow:
- /authorize - Initiates OAuth flow, redirects to identity provider (e.g., GitHub)
- /oauth/callback - Receives callback from identity provider, exchanges code for token

The flow works as follows:
1. Agent calls /authorize with its callback_uri (e.g., http://localhost:8888/callback)
2. MCP Compose redirects to GitHub with its own callback (http://localhost:8080/oauth/callback)
3. User authenticates with GitHub
4. GitHub redirects to /oauth/callback with authorization code
5. MCP Compose exchanges code for token with GitHub
6. MCP Compose redirects to agent's callback_uri with the token
"""

import logging
import secrets
import time
from typing import Optional, Dict, Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory stores for OAuth state
_oauth_state_store: Dict[str, Dict[str, Any]] = {}
_oauth_config: Optional[Dict[str, Any]] = None


def configure_oauth(
    provider: str,
    client_id: str,
    client_secret: str,
    server_url: str,
    authorization_endpoint: Optional[str] = None,
    token_endpoint: Optional[str] = None,
    userinfo_endpoint: Optional[str] = None,
    scopes: Optional[list] = None,
) -> None:
    """
    Configure OAuth settings for the server.
    
    Args:
        provider: OAuth provider name (e.g., "github")
        client_id: OAuth client ID
        client_secret: OAuth client secret
        server_url: This server's base URL (e.g., http://localhost:8080)
        authorization_endpoint: Provider's authorization endpoint
        token_endpoint: Provider's token endpoint
        userinfo_endpoint: Provider's userinfo endpoint
        scopes: OAuth scopes to request
    """
    global _oauth_config
    
    # Set defaults based on provider
    if provider.lower() == "github":
        _oauth_config = {
            "provider": "github",
            "client_id": client_id,
            "client_secret": client_secret,
            "server_url": server_url,
            "authorization_endpoint": authorization_endpoint or "https://github.com/login/oauth/authorize",
            "token_endpoint": token_endpoint or "https://github.com/login/oauth/access_token",
            "userinfo_endpoint": userinfo_endpoint or "https://api.github.com/user",
            "scopes": scopes or ["read:user"],
        }
    else:
        _oauth_config = {
            "provider": provider,
            "client_id": client_id,
            "client_secret": client_secret,
            "server_url": server_url,
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
            "userinfo_endpoint": userinfo_endpoint,
            "scopes": scopes or [],
        }
    
    logger.info(f"OAuth configured for provider: {provider}")


def is_oauth_configured() -> bool:
    """Check if OAuth is configured."""
    return _oauth_config is not None


@router.get("/authorize")
async def authorize(request: Request):
    """
    OAuth2 Authorization Endpoint.
    
    Initiates the OAuth flow by redirecting to the identity provider.
    
    Query Parameters:
        client_id: Optional client identifier
        redirect_uri: Agent's callback URL (e.g., http://localhost:8888/callback)
        response_type: Must be "code"
        scope: Requested scopes
        state: Client-provided state for CSRF protection
        code_challenge: PKCE code challenge (optional)
        code_challenge_method: PKCE method, typically "S256" (optional)
    
    Returns:
        Redirect to identity provider's authorization page
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    # Extract query parameters
    client_redirect_uri = request.query_params.get("redirect_uri")
    client_state = request.query_params.get("state", secrets.token_urlsafe(16))
    scope = request.query_params.get("scope", " ".join(_oauth_config["scopes"]))
    code_challenge = request.query_params.get("code_challenge")
    code_challenge_method = request.query_params.get("code_challenge_method")
    
    if not client_redirect_uri:
        raise HTTPException(status_code=400, detail="redirect_uri is required")
    
    # Generate our own state to track the session
    server_state = secrets.token_urlsafe(32)
    
    # Store session info
    _oauth_state_store[server_state] = {
        "client_redirect_uri": client_redirect_uri,
        "client_state": client_state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": time.time(),
    }
    
    # Build authorization URL for the identity provider
    server_callback_url = f"{_oauth_config['server_url']}/oauth/callback"
    
    auth_params = {
        "client_id": _oauth_config["client_id"],
        "redirect_uri": server_callback_url,
        "response_type": "code",
        "scope": scope,
        "state": server_state,
    }
    
    # GitHub-specific: don't allow signup
    if _oauth_config["provider"] == "github":
        auth_params["allow_signup"] = "false"
    
    auth_url = f"{_oauth_config['authorization_endpoint']}?{urlencode(auth_params)}"
    
    logger.info(f"Redirecting to OAuth provider: {_oauth_config['authorization_endpoint']}")
    logger.info(f"Client redirect_uri: {client_redirect_uri}")
    
    return RedirectResponse(url=auth_url)


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    """
    OAuth2 Callback Endpoint.
    
    Receives the authorization code from the identity provider,
    exchanges it for an access token, and redirects to the agent's callback.
    
    Query Parameters:
        code: Authorization code from identity provider
        state: State parameter for session lookup
        error: Error code if authorization failed
        error_description: Error description if authorization failed
    
    Returns:
        Redirect to agent's callback URL with token or error
    """
    if not HTTPX_AVAILABLE:
        raise HTTPException(status_code=500, detail="httpx not installed")
    
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    # Check for errors from the identity provider
    error = request.query_params.get("error")
    if error:
        error_desc = request.query_params.get("error_description", error)
        logger.error(f"OAuth error from provider: {error} - {error_desc}")
        return HTMLResponse(
            f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Authentication Error</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #d32f2f;">Authentication Error</h1>
    <p>Error: {error}</p>
    <p>{error_desc}</p>
</body>
</html>""",
            status_code=400
        )
    
    # Get authorization code and state
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    
    if not code or not state:
        logger.error(f"Missing code or state: code={code}, state={state}")
        return HTMLResponse(
            """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Invalid Request</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #d32f2f;">Invalid Request</h1>
    <p>Missing authorization code or state parameter</p>
</body>
</html>""",
            status_code=400
        )
    
    # Look up session
    session = _oauth_state_store.pop(state, None)
    if not session:
        logger.error(f"Invalid or expired state: {state}")
        return HTMLResponse(
            """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Invalid State</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #d32f2f;">Invalid or Expired Session</h1>
    <p>Please try authenticating again.</p>
</body>
</html>""",
            status_code=400
        )
    
    # Check session age (5 minute expiry)
    if time.time() - session["created_at"] > 300:
        logger.error("OAuth session expired")
        return HTMLResponse(
            """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Session Expired</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #d32f2f;">Session Expired</h1>
    <p>Please try authenticating again.</p>
</body>
</html>""",
            status_code=400
        )
    
    try:
        # Exchange authorization code for access token
        server_callback_url = f"{_oauth_config['server_url']}/oauth/callback"
        
        token_data = {
            "client_id": _oauth_config["client_id"],
            "client_secret": _oauth_config["client_secret"],
            "code": code,
            "redirect_uri": server_callback_url,
        }
        
        # GitHub expects form data, not JSON
        if _oauth_config["provider"] == "github":
            token_data["grant_type"] = "authorization_code"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _oauth_config["token_endpoint"],
                data=token_data,
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                raise Exception(f"Token exchange failed: {response.text}")
            
            token_response = response.json()
            
            if "error" in token_response:
                error_desc = token_response.get("error_description", token_response["error"])
                raise Exception(f"Token error: {error_desc}")
            
            access_token = token_response.get("access_token")
            if not access_token:
                raise Exception("No access_token in response")
            
            logger.info("Successfully exchanged code for access token")
            
            # Get user info
            username = None
            if _oauth_config["userinfo_endpoint"]:
                user_response = await client.get(
                    _oauth_config["userinfo_endpoint"],
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                    timeout=5.0,
                )
                
                if user_response.status_code == 200:
                    user_info = user_response.json()
                    username = user_info.get("login") or user_info.get("name") or user_info.get("email")
                    logger.info(f"Authenticated user: {username}")
        
        # Redirect to agent's callback with the token
        client_redirect_uri = session["client_redirect_uri"]
        client_state = session["client_state"]
        
        callback_params = {
            "token": access_token,
            "state": client_state,
        }
        if username:
            callback_params["username"] = username
        
        redirect_url = f"{client_redirect_uri}?{urlencode(callback_params)}"
        
        logger.info(f"Redirecting to agent callback: {client_redirect_uri}")
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.exception(f"OAuth callback error: {e}")
        return HTMLResponse(
            f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Authentication Failed</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
    <h1 style="color: #d32f2f;">Authentication Failed</h1>
    <p>Error: {str(e)}</p>
    <p>Please try again.</p>
</body>
</html>""",
            status_code=500
        )


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata(request: Request):
    """
    Protected Resource Metadata (RFC 9728).
    
    Returns metadata about this protected resource and its authorization requirements.
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    return JSONResponse({
        "resource": _oauth_config["server_url"],
        "authorization_servers": [_oauth_config["server_url"]],
        "bearer_methods_supported": ["header"],
        "scopes_supported": _oauth_config["scopes"],
    })


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata(request: Request):
    """
    Authorization Server Metadata (RFC 8414).
    
    Returns metadata about this server's OAuth endpoints.
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    server_url = _oauth_config["server_url"]
    
    return JSONResponse({
        "issuer": server_url,
        "authorization_endpoint": f"{server_url}/authorize",
        "token_endpoint": f"{server_url}/token",  # We proxy to the actual provider
        "scopes_supported": _oauth_config["scopes"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
    })
