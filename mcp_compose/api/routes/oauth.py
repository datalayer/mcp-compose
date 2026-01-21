# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
OAuth2 Authorization Server for MCP Compose.

This module implements a local OAuth2 authorization server that:
1. Acts as the OAuth provider for clients (agents, Claude Desktop, etc.)
2. Delegates user authentication to an external provider (e.g., GitHub)
3. Issues its own tokens after successful external authentication

The flow matches the reference implementation in references/oauth:
1. Client calls /authorize with redirect_uri (e.g., http://localhost:8888/callback)
2. Server stores session, redirects to GitHub with callback http://localhost:8080/oauth/callback
3. User authenticates with GitHub
4. GitHub redirects to /oauth/callback with authorization code
5. Server exchanges code for GitHub token, gets user info
6. For legacy flows (agent): redirect to client with GitHub token
7. For modern flows (Claude): issue authorization code, exchange for JWT at /token

Endpoints:
- GET /.well-known/oauth-protected-resource - RFC 9728 Protected Resource Metadata
- GET /.well-known/oauth-authorization-server - RFC 8414 Authorization Server Metadata
- POST /register - RFC 7591 Dynamic Client Registration
- GET /authorize - Start OAuth flow
- GET /oauth/callback - Receive callback from external provider (GitHub)
- POST /token - Exchange authorization code for access token
"""

import json
import logging
import secrets
import time
import hashlib
import base64
from typing import Optional, Dict, Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import jwt as pyjwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory stores
_oauth_config: Optional[Dict[str, Any]] = None
_state_store: Dict[str, Dict[str, Any]] = {}  # OAuth session state
_auth_code_store: Dict[str, Dict[str, Any]] = {}  # Authorization codes for token exchange
_client_registry: Dict[str, Dict[str, Any]] = {}  # Dynamic client registrations

# JWT configuration
JWT_SIGN_KEY = secrets.token_hex(32)  # Generate at startup
ACCESS_TOKEN_EXPIRES = 3600  # 1 hour


def gen_random(length: int = 32) -> str:
    """Generate a random URL-safe string."""
    return secrets.token_urlsafe(length)


PROVIDER_DEFAULTS = {
    "github": {
        "authorization_endpoint": "https://github.com/login/oauth/authorize",
        "token_endpoint": "https://github.com/login/oauth/access_token",
        "userinfo_endpoint": "https://api.github.com/user",
        "scopes": ["read:user"],
    }
}


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
        client_id: OAuth client ID for the external provider
        client_secret: OAuth client secret for the external provider
        server_url: This server's base URL (e.g., http://localhost:8080)
        authorization_endpoint: External provider's authorization endpoint
        token_endpoint: External provider's token endpoint
        userinfo_endpoint: External provider's userinfo endpoint
        scopes: OAuth scopes to request from external provider
    """
    global _oauth_config
    
    # IMPORTANT: Always use localhost for callback URLs, never 0.0.0.0
    # GitHub OAuth requires exact URL match
    parsed = urlparse(server_url)
    if parsed.hostname == "0.0.0.0":
        server_url = server_url.replace("0.0.0.0", "localhost")
    
    provider_key = provider.lower()
    defaults = PROVIDER_DEFAULTS.get(provider_key, {})
    resolved_authorization = authorization_endpoint or defaults.get("authorization_endpoint")
    resolved_token = token_endpoint or defaults.get("token_endpoint")
    resolved_userinfo = userinfo_endpoint or defaults.get("userinfo_endpoint")
    resolved_scopes = scopes or defaults.get("scopes") or []

    missing_fields = []
    if not resolved_authorization:
        missing_fields.append("authorization_endpoint")
    if not resolved_token:
        missing_fields.append("token_endpoint")
    if not resolved_userinfo:
        missing_fields.append("userinfo_endpoint")

    if missing_fields:
        logger.error(
            "OAuth configuration missing %s for provider %s",
            ", ".join(missing_fields),
            provider,
        )
        raise ValueError(
            "Missing OAuth configuration values: "
            + ", ".join(missing_fields)
            + f" for provider '{provider}'. Provide them in authentication.oauth2"
        )
    
    _oauth_config = {
        "provider": provider,
        "client_id": client_id,
        "client_secret": client_secret,
        "server_url": server_url,
        "authorization_endpoint": resolved_authorization,
        "token_endpoint": resolved_token,
        "userinfo_endpoint": resolved_userinfo,
        "scopes": resolved_scopes,
    }
    
    logger.info(f"OAuth configured for provider: {provider}")
    logger.info(f"  Server URL: {server_url}")
    logger.info(f"  Callback: {server_url}/oauth/callback")


def is_oauth_configured() -> bool:
    """Check if OAuth is configured."""
    return _oauth_config is not None


def issue_jwt(sub: str) -> str:
    """
    Issue a JWT token for authenticated user.
    
    Args:
        sub: Subject (user identifier)
    
    Returns:
        JWT token string
    """
    if not JWT_AVAILABLE:
        # Fallback: return a simple token
        return f"token_{gen_random()}"
    
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": _oauth_config["server_url"],
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRES,
        "scope": "read:mcp write:mcp"
    }
    return pyjwt.encode(payload, JWT_SIGN_KEY, algorithm="HS256")


def verify_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token."""
    if not JWT_AVAILABLE:
        return None
    
    try:
        payload = pyjwt.decode(
            token,
            JWT_SIGN_KEY,
            algorithms=["HS256"],
            issuer=_oauth_config["server_url"]
        )
        return payload
    except Exception as e:
        logger.debug(f"JWT verification failed: {e}")
        return None


# ============================================================================
# OAUTH2 METADATA ENDPOINTS (RFC 9728, RFC 8414)
# ============================================================================

@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata(request: Request):
    """
    Protected Resource Metadata (RFC 9728).
    
    Tells clients (like Claude Desktop):
    - The issuer (this MCP server itself)
    - Where to get authorization (our /authorize endpoint)
    - Supported scopes
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    server_url = _oauth_config["server_url"]
    
    return JSONResponse(
        {
            "issuer": server_url,
            "authorization_endpoint": f"{server_url}/authorize",
            "token_endpoint": f"{server_url}/token",
            "scopes_supported": ["openid", "read:mcp", "write:mcp"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata(request: Request):
    """
    Authorization Server Metadata (RFC 8414).
    
    THIS MCP SERVER acts as the OAuth authorization server.
    It delegates user authentication to GitHub, but issues its own tokens.
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    server_url = _oauth_config["server_url"]
    
    return JSONResponse(
        {
            "issuer": server_url,
            "authorization_endpoint": f"{server_url}/authorize",
            "token_endpoint": f"{server_url}/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
            "scopes_supported": ["openid", "read:mcp", "write:mcp"],
            "registration_endpoint": f"{server_url}/register",
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


# ============================================================================
# DYNAMIC CLIENT REGISTRATION (RFC 7591)
# ============================================================================

@router.post("/register")
async def register_client(request: Request):
    """
    Dynamic Client Registration Endpoint (RFC 7591).
    
    Allows clients to register themselves without pre-configuration.
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    try:
        body = await request.json()
        
        # Validate required fields
        redirect_uris = body.get("redirect_uris")
        if not redirect_uris or not isinstance(redirect_uris, list) or len(redirect_uris) == 0:
            return JSONResponse(
                {
                    "error": "invalid_redirect_uri",
                    "error_description": "redirect_uris is required and must be a non-empty array"
                },
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        # Extract optional fields
        client_name = body.get("client_name", "Unnamed Client")
        scope = body.get("scope", "openid read:mcp write:mcp")
        grant_types = body.get("grant_types", ["authorization_code"])
        response_types = body.get("response_types", ["code"])
        token_endpoint_auth_method = body.get("token_endpoint_auth_method", "none")
        
        # Generate client credentials
        client_id = f"dcr_{gen_random()}"
        client_secret = None if token_endpoint_auth_method == "none" else gen_random()
        
        # Store client metadata
        client_metadata = {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "grant_types": grant_types,
            "response_types": response_types,
            "token_endpoint_auth_method": token_endpoint_auth_method,
            "scope": scope,
            "client_id_issued_at": int(time.time())
        }
        
        _client_registry[client_id] = client_metadata
        
        logger.info(f"Registered new client: {client_id} ({client_name})")
        logger.info(f"  Redirect URIs: {redirect_uris}")
        
        # Prepare response
        response_data = {
            "client_id": client_id,
            "client_id_issued_at": client_metadata["client_id_issued_at"],
            "redirect_uris": redirect_uris,
            "grant_types": grant_types,
            "response_types": response_types,
            "token_endpoint_auth_method": token_endpoint_auth_method,
            "client_name": client_name,
            "scope": scope
        }
        
        if client_secret:
            response_data["client_secret"] = client_secret
        
        return JSONResponse(
            response_data,
            status_code=201,
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Invalid JSON"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        logger.error(f"Client registration error: {e}")
        return JSONResponse(
            {"error": "server_error", "error_description": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"}
        )


# ============================================================================
# OAUTH2 AUTHORIZATION FLOW
# ============================================================================

@router.get("/authorize")
async def authorize(request: Request):
    """
    OAuth2 Authorization Endpoint.
    
    Clients (agents, Claude Desktop) redirect here to start OAuth flow.
    We redirect to the external provider (GitHub) for authentication.
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    # Extract OAuth params from client
    client_id = request.query_params.get("client_id", "default-client")
    redirect_uri = request.query_params.get("redirect_uri")
    state = request.query_params.get("state", gen_random())
    scope = request.query_params.get("scope", "openid read:mcp")
    code_challenge = request.query_params.get("code_challenge")
    code_challenge_method = request.query_params.get("code_challenge_method", "S256")
    
    if not redirect_uri:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Missing redirect_uri"},
            status_code=400
        )
    
    # Validate redirect_uri for registered clients
    if client_id in _client_registry:
        client_metadata = _client_registry[client_id]
        registered_uris = client_metadata.get("redirect_uris", [])
        
        if redirect_uri not in registered_uris:
            logger.warning(f"Client {client_id} used unregistered redirect_uri: {redirect_uri}")
            return JSONResponse(
                {
                    "error": "invalid_request",
                    "error_description": f"redirect_uri not registered. Registered: {', '.join(registered_uris)}"
                },
                status_code=400
            )
    
    # Store OAuth session state (keyed by our state, not client's)
    server_state = gen_random()
    _state_store[server_state] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "client_state": state,  # Preserve client's state
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": time.time()
    }
    
    # Build redirect to external provider (GitHub)
    server_url = _oauth_config["server_url"]
    external_callback = f"{server_url}/oauth/callback"
    
    github_params = {
        "client_id": _oauth_config["client_id"],
        "redirect_uri": external_callback,
        "scope": " ".join(_oauth_config["scopes"]),
        "state": server_state,
        "allow_signup": "false"
    }
    
    github_auth_url = f"{_oauth_config['authorization_endpoint']}?{urlencode(github_params)}"
    
    logger.info(f"Redirecting to GitHub for authentication")
    logger.info(f"  Client redirect_uri: {redirect_uri}")
    logger.info(f"  GitHub callback: {external_callback}")
    
    return RedirectResponse(url=github_auth_url)


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    """
    OAuth Callback from External Provider (GitHub).
    
    After user authenticates with GitHub, GitHub redirects here.
    We exchange the code for a token, then redirect back to the client.
    
    For legacy flows (agent with localhost:8888): redirect with GitHub token
    For modern flows (Claude Desktop): issue auth code for /token exchange
    """
    if not HTTPX_AVAILABLE:
        raise HTTPException(status_code=500, detail="httpx not installed")
    
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    # Check for errors from GitHub
    error = request.query_params.get("error")
    if error:
        error_desc = request.query_params.get("error_description", error)
        logger.error(f"GitHub OAuth error: {error} - {error_desc}")
        return HTMLResponse(
            f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Authentication Error</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #d32f2f;">Authentication Error</h1>
<p>{error}: {error_desc}</p>
</body></html>""",
            status_code=400
        )
    
    # Get authorization code and state from GitHub
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    
    if not code or not state:
        return HTMLResponse(
            """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Invalid Request</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #d32f2f;">Invalid Request</h1>
<p>Missing authorization code or state</p>
</body></html>""",
            status_code=400
        )
    
    # Look up session
    session = _state_store.pop(state, None)
    if not session:
        logger.error(f"Invalid or expired state: {state}")
        return HTMLResponse(
            """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Invalid Session</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #d32f2f;">Invalid or Expired Session</h1>
<p>Please try authenticating again.</p>
</body></html>""",
            status_code=400
        )
    
    # Check session age (5 minute expiry)
    if time.time() - session["created_at"] > 300:
        return HTMLResponse(
            """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Session Expired</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #d32f2f;">Session Expired</h1>
<p>Please try authenticating again.</p>
</body></html>""",
            status_code=400
        )
    
    try:
        server_url = _oauth_config["server_url"]
        external_callback = f"{server_url}/oauth/callback"
        
        # Exchange GitHub code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                _oauth_config["token_endpoint"],
                data={
                    "client_id": _oauth_config["client_id"],
                    "client_secret": _oauth_config["client_secret"],
                    "code": code,
                    "redirect_uri": external_callback,
                },
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
            
            if token_response.status_code != 200:
                raise Exception(f"Token exchange failed: {token_response.text}")
            
            token_data = token_response.json()
            
            if "error" in token_data:
                raise Exception(f"Token error: {token_data.get('error_description', token_data['error'])}")
            
            gh_token = token_data.get("access_token")
            if not gh_token:
                raise Exception("No access_token in response")
            
            logger.info("Successfully exchanged GitHub code for token")
            
            # Get user info from GitHub
            user_response = await client.get(
                _oauth_config["userinfo_endpoint"],
                headers={
                    "Authorization": f"Bearer {gh_token}",
                    "Accept": "application/json",
                },
                timeout=5.0,
            )
            
            username = None
            if user_response.status_code == 200:
                user_info = user_response.json()
                username = user_info.get("login") or user_info.get("name")
                logger.info(f"Authenticated user: {username}")
        
        # Get client's redirect_uri and state
        client_redirect_uri = session["redirect_uri"]
        client_state = session["client_state"]
        
        # Determine flow type based on redirect_uri
        # Legacy flow: agent/client with direct token (localhost:8888 or server's /callback)
        is_legacy_flow = (
            client_redirect_uri == f"{server_url}/callback" or
            client_redirect_uri.startswith("http://localhost:8888/")
        )
        
        if is_legacy_flow:
            # Legacy flow: redirect with GitHub token directly
            callback_params = {
                "token": gh_token,
                "state": client_state,
            }
            if username:
                callback_params["username"] = username
            
            redirect_url = f"{client_redirect_uri}?{urlencode(callback_params)}"
            logger.info(f"Legacy flow: redirecting to {client_redirect_uri}")
            return RedirectResponse(url=redirect_url)
        else:
            # Modern flow (Claude Desktop, Inspector): issue authorization code
            auth_code = gen_random()
            _auth_code_store[auth_code] = {
                "sub": username or "user",
                "client_id": session.get("client_id"),
                "scope": session.get("scope"),
                "code_challenge": session.get("code_challenge"),
                "redirect_uri": client_redirect_uri,
                "expires_at": time.time() + 120  # 2 minutes
            }
            
            callback_params = {
                "code": auth_code,
                "state": client_state,
            }
            
            redirect_url = f"{client_redirect_uri}?{urlencode(callback_params)}"
            logger.info(f"Modern flow: issuing auth code, redirecting to {client_redirect_uri}")
            return RedirectResponse(url=redirect_url)
    
    except Exception as e:
        logger.exception(f"OAuth callback error: {e}")
        return HTMLResponse(
            f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Authentication Failed</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
<h1 style="color: #d32f2f;">Authentication Failed</h1>
<p>Error: {str(e)}</p>
</body></html>""",
            status_code=500
        )


@router.post("/token")
async def token_endpoint(request: Request):
    """
    OAuth2 Token Endpoint.
    
    Clients exchange authorization code for access token (JWT).
    This is used by modern flows (Claude Desktop, Inspector).
    """
    if not is_oauth_configured():
        raise HTTPException(status_code=500, detail="OAuth not configured")
    
    form = await request.form()
    grant_type = form.get("grant_type")
    code = form.get("code")
    redirect_uri = form.get("redirect_uri")
    code_verifier = form.get("code_verifier")
    
    if grant_type != "authorization_code":
        return JSONResponse(
            {"error": "unsupported_grant_type"},
            status_code=400
        )
    
    if not code:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Missing code"},
            status_code=400
        )
    
    # Look up authorization code
    code_data = _auth_code_store.pop(code, None)
    if not code_data:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Invalid or expired code"},
            status_code=400
        )
    
    # Check expiry
    if time.time() > code_data["expires_at"]:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Code expired"},
            status_code=400
        )
    
    # Verify redirect_uri matches
    if redirect_uri and redirect_uri != code_data["redirect_uri"]:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "redirect_uri mismatch"},
            status_code=400
        )
    
    # Verify PKCE if code_challenge was provided
    if code_data.get("code_challenge") and code_verifier:
        # Compute S256 challenge from verifier
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
        
        if computed_challenge != code_data["code_challenge"]:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                status_code=400
            )
    
    # Issue JWT token
    access_token = issue_jwt(code_data["sub"])
    
    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRES,
        "scope": code_data.get("scope", "read:mcp write:mcp")
    })


@router.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "oauth_configured": is_oauth_configured()
    })
