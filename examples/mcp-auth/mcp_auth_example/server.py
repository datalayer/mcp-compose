#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Server with GitHub OAuth2 Authentication

This server combines:
1. OAuth2 authorization server (GitHub-based)
2. MCP server with FastMCP SDK exposing protected tools

Implements MCP Authorization specification (2025-06-18):
- Protected Resource Metadata (RFC 9728)
- Authorization Server Metadata (RFC 8414)
- Resource Indicators (RFC 8707)
- Bearer token authentication

The server exposes MCP tools via HTTP Streaming (NDJSON) transport while requiring
OAuth2 authentication for all tool invocations.
"""

import json
import logging
import time
import secrets
import hashlib
import base64
from typing import Dict, Optional, Any
from urllib.parse import urlencode
import requests

from fastapi import Request, HTTPException, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse, RedirectResponse
from mcp.server.fastmcp import FastMCP

try:
    import jwt
except ImportError:
    print("⚠️  PyJWT not installed. Run: pip install PyJWT")
    jwt = None

logger = logging.getLogger(__name__)


class Config:
    """Configuration management"""
    
    def __init__(self, config_file: str = "config.json"):
        with open(config_file) as f:
            self.config = json.load(f)
    
    @property
    def github_client_id(self) -> str:
        return self.config["github"]["client_id"]
    
    @property
    def github_client_secret(self) -> str:
        return self.config["github"]["client_secret"]
    
    @property
    def server_host(self) -> str:
        return self.config["server"]["host"]
    
    @property
    def server_port(self) -> int:
        return self.config["server"]["port"]
    
    @property
    def server_url(self) -> str:
        """Get server URL with HTTPS if certificates are available"""
        import os
        cert_file = os.path.join(os.path.dirname(__file__), "..", "localhost+2.pem")
        key_file = os.path.join(os.path.dirname(__file__), "..", "localhost+2-key.pem")
        ssl_enabled = os.path.exists(cert_file) and os.path.exists(key_file)
        protocol = "https" if ssl_enabled else "http"
        return f"{protocol}://{self.server_host}:{self.server_port}"


class TokenValidator:
    """Validates OAuth tokens with GitHub"""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate token with GitHub API
        
        Returns user info if valid, None otherwise
        """
        # Check cache first
        if token in self.cache:
            return self.cache[token]
        
        # Validate with GitHub
        try:
            response = requests.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=5
            )
            
            if response.status_code == 200:
                user_info = response.json()
                self.cache[token] = user_info
                return user_info
            else:
                return None
        except Exception as e:
            print(f"Token validation error: {e}")
            return None
    
    def clear_cache(self):
        """Clear token cache"""
        self.cache.clear()


# Global instances
config = Config()
token_validator = TokenValidator()

# ============================================================================
# JWT TOKEN MANAGEMENT
# ============================================================================

JWT_SIGN_KEY = "dev_sign_key_change_in_production"  # TODO: Use env var
ACCESS_TOKEN_EXPIRES = 3600  # 1 hour

# In-memory stores (replace with database in production)
state_store: Dict[str, Dict[str, Any]] = {}  # OAuth state -> session data
auth_code_store: Dict[str, Dict[str, Any]] = {}  # auth_code -> user data


def gen_random() -> str:
    """Generate random token"""
    return secrets.token_urlsafe(32)


def mint_jwt(sub: str) -> str:
    """
    Mint a JWT access token for MCP access
    
    Args:
        sub: Subject (username/user ID)
    
    Returns:
        JWT token string
    """
    if not jwt:
        raise RuntimeError("PyJWT not installed")
    
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": config.server_url,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRES,
        "scope": "read:mcp write:mcp"
    }
    token = jwt.encode(payload, JWT_SIGN_KEY, algorithm="HS256")
    return token


def verify_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload if valid, None otherwise
    """
    if not jwt:
        return None
    
    try:
        payload = jwt.decode(
            token,
            JWT_SIGN_KEY,
            algorithms=["HS256"],
            issuer=config.server_url
        )
        return payload
    except Exception as e:
        logger.debug(f"JWT verification failed: {e}")
        return None


# Create FastMCP server for tools
mcp = FastMCP("github-auth-mcp-server")


# ============================================================================
# AUTHENTICATION HELPERS
# ============================================================================

async def verify_token(authorization: Optional[str]) -> Dict[str, Any]:
    """
    Verify OAuth token from Authorization header
    
    Raises HTTPException if invalid
    Returns user info if valid
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": f'Bearer realm="{config.server_url}/.well-known/oauth-protected-resource"'}
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": f'Bearer realm="{config.server_url}/.well-known/oauth-protected-resource"'}
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    user_info = token_validator.validate_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": f'Bearer realm="{config.server_url}/.well-known/oauth-protected-resource"'}
        )
    
    return user_info


# ============================================================================
# MCP TOOLS - Protected by OAuth2
# ============================================================================

@mcp.tool()
def calculator_add(a: int, b: int) -> int:
    """
    Add two numbers
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        Sum of a and b
    """
    return a + b


@mcp.tool()
def calculator_multiply(a: int, b: int) -> int:
    """
    Multiply two numbers
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        Product of a and b
    """
    return a * b


@mcp.tool()
def greeter_hello(name: str) -> str:
    """
    Greet someone
    
    Args:
        name: Name of the person to greet
    
    Returns:
        Greeting message
    """
    return f"Hello, {name}! Welcome to the authenticated MCP server!"


@mcp.tool()
def greeter_goodbye(name: str) -> str:
    """
    Say goodbye to someone
    
    Args:
        name: Name of the person
    
    Returns:
        Goodbye message
    """
    return f"Goodbye, {name}! Thanks for using our secure MCP server!"


@mcp.tool()
def get_server_info() -> Dict[str, Any]:
    """
    Get information about the MCP server
    
    Returns:
        Server information including name, version, and capabilities
    """
    return {
        "name": "github-auth-mcp-server",
        "version": "1.0.0",
        "authentication": "GitHub OAuth2",
        "transport": "HTTP Streaming (NDJSON)",
        "tools": ["calculator_add", "calculator_multiply", "greeter_hello", "greeter_goodbye", "get_server_info"],
        "specification": "MCP Authorization 2025-06-18"
    }


# ============================================================================
# AUTHENTICATION MIDDLEWARE
# ============================================================================

async def verify_token(authorization: Optional[str]) -> Dict[str, Any]:
    """
    Verify OAuth token from Authorization header
    
    Supports two token types:
    1. JWT tokens issued by this server (for Claude Desktop)
    2. GitHub tokens (for backward compatibility with client.py and agent.py)
    
    Args:
        authorization: Authorization header value
    
    Returns:
        User information if token is valid
    
    Raises:
        HTTPException: If token is missing or invalid
    """
    www_auth_header = f'Bearer realm="mcp", resource_metadata="{config.server_url}/.well-known/oauth-protected-resource", scope="openid read:mcp write:mcp"'
    
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": www_auth_header}
        )
    
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": www_auth_header}
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    
    # Try JWT first (for Claude Desktop)
    jwt_payload = verify_jwt(token)
    if jwt_payload:
        return {
            "login": jwt_payload["sub"],
            "type": "jwt",
            "scope": jwt_payload.get("scope", "")
        }
    
    # Fall back to GitHub token validation (for backward compatibility)
    user_info = token_validator.validate_token(token)
    if user_info:
        return {**user_info, "type": "github"}
    
    raise HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": www_auth_header}
    )


# ============================================================================
# STARTUP MESSAGE
# ============================================================================

def print_startup_message():
    """Print startup information"""
    print("\n" + "=" * 70)
    print("🔐 MCP Server with GitHub OAuth2 Authentication")
    print("=" * 70)
    print()
    print("📋 Server Information:")
    print(f"   Server URL: {config.server_url}")
    print(f"   MCP Transport: HTTP Streaming (NDJSON)")
    print(f"   Authentication: GitHub OAuth2")
    print()
    print("🔗 OAuth Metadata Endpoints:")
    print(f"   Protected Resource: {config.server_url}/.well-known/oauth-protected-resource")
    print(f"   Authorization Server: {config.server_url}/.well-known/oauth-authorization-server")
    print()
    print("🔗 MCP Endpoints:")
    print(f"   HTTP Streaming:    {config.server_url}/mcp")
    print()
    print("🛠️  Available Tools:")
    print("   - calculator_add - Add two numbers")
    print("   - calculator_multiply - Multiply two numbers")
    print("   - greeter_hello - Greet someone")
    print("   - greeter_goodbye - Say goodbye")
    print("   - get_server_info - Get server information")
    print()
    print("✅ Server is ready! All MCP tools require authentication.")
    print("=" * 70)
    print()


# ============================================================================
# OAUTH2 METADATA ENDPOINTS (RFC 9728, RFC 8414) - Using custom_route
# ============================================================================

@mcp.custom_route("/.well-known/oauth-protected-resource", ["GET", "OPTIONS"])
async def protected_resource_metadata(request: Request):
    """
    Protected Resource Metadata (RFC 9728)
    
    This tells Claude Desktop:
    - The issuer (this MCP server itself)
    - Where to get authorization (our /authorize endpoint)
    - Where to exchange tokens (our /token endpoint)
    - Supported scopes
    
    Claude will use this to initiate OAuth flow.
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return JSONResponse(
            {},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    return JSONResponse(
        {
            "issuer": config.server_url,
            "authorization_endpoint": f"{config.server_url}/authorize",
            "token_endpoint": f"{config.server_url}/token",
            "scopes_supported": ["openid", "read:mcp", "write:mcp"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


@mcp.custom_route("/.well-known/oauth-authorization-server", ["GET", "OPTIONS"])
async def authorization_server_metadata(request: Request):
    """
    Authorization Server Metadata (RFC 8414)
    
    THIS MCP SERVER acts as the OAuth authorization server.
    It delegates user authentication to GitHub, but issues its own JWT tokens.
    Claude Desktop will use these endpoints for the OAuth flow.
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return JSONResponse(
            {},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    return JSONResponse(
        {
            "issuer": config.server_url,
            "authorization_endpoint": f"{config.server_url}/authorize",
            "token_endpoint": f"{config.server_url}/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
            "scopes_supported": ["openid", "read:mcp", "write:mcp"],
            "service_documentation": "https://github.com/datalayer/mcp-compose/tree/main/examples/mcp-auth"
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


# ============================================================================
# OAUTH2 AUTHORIZATION FLOW ENDPOINTS
# ============================================================================

@mcp.custom_route("/authorize", ["GET"])
async def authorize(request: Request):
    """
    OAuth2 Authorization Endpoint
    
    Claude Desktop will redirect user here to start OAuth flow.
    We redirect to GitHub for authentication, then issue our own tokens.
    
    Query params (from Claude):
    - response_type: Should be "code"
    - client_id: Claude's client ID (optional for public clients)
    - redirect_uri: Where to send auth code (Claude's callback)
    - scope: Requested scopes
    - state: CSRF protection token
    - code_challenge: PKCE challenge (S256)
    - code_challenge_method: Should be "S256"
    """
    # Extract OAuth params
    client_id = request.query_params.get("client_id", "claude-desktop")
    redirect_uri = request.query_params.get("redirect_uri")
    state = request.query_params.get("state", gen_random())
    scope = request.query_params.get("scope", "openid read:mcp")
    code_challenge = request.query_params.get("code_challenge")
    code_challenge_method = request.query_params.get("code_challenge_method", "S256")
    
    # Validate redirect_uri
    if not redirect_uri:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Missing redirect_uri"},
            status_code=400
        )
    
    # Store OAuth session state
    state_store[state] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": time.time()
    }
    
    # Redirect user to GitHub for authentication
    github_params = {
        "client_id": config.github_client_id,
        "redirect_uri": f"{config.server_url}/oauth/callback",
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "false"
    }
    
    github_auth_url = "https://github.com/login/oauth/authorize?" + urlencode(github_params)
    return RedirectResponse(url=github_auth_url)


@mcp.custom_route("/oauth/callback", ["GET"])
async def oauth_callback_github(request: Request):
    """
    GitHub OAuth Callback
    
    After user authenticates with GitHub, GitHub redirects here.
    We exchange the GitHub code for a token, verify the user,
    then issue our own authorization code to Claude.
    """
    # Log all query parameters for debugging
    logger.info(f"OAuth callback received with params: {dict(request.query_params)}")
    
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    
    # Handle OAuth errors from GitHub
    if error:
        return HTMLResponse(
            f"<h1>Authentication Error</h1><p>GitHub returned error: {error}</p>",
            status_code=400
        )
    
    # Validate state
    if not code or not state or state not in state_store:
        logger.error(f"Invalid callback: code={code}, state={state}, state_in_store={state in state_store if state else False}")
        return HTMLResponse(
            "<h1>Invalid Request</h1><p>Invalid state or missing authorization code</p>",
            status_code=400
        )
    
    session = state_store[state]
    logger.info(f"GitHub callback received: code={code[:10]}..., state={state[:20]}...")
    logger.info(f"Session data: redirect_uri={session['redirect_uri']}")
    
    # Exchange GitHub code for access token
    try:
        logger.info(f"Exchanging GitHub code for access token...")
        token_resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": config.github_client_id,
                "client_secret": config.github_client_secret,
                "code": code,
                "redirect_uri": f"{config.server_url}/oauth/callback"
            },
            timeout=10
        )
        token_json = token_resp.json()
        logger.info(f"GitHub token response: {token_json}")
        gh_token = token_json.get("access_token")
        
        if not gh_token:
            logger.error(f"No access_token in GitHub response: {token_json}")
            raise Exception(f"No access_token in response: {token_json}")
        
        # Fetch user info from GitHub
        logger.info(f"Fetching user info from GitHub...")
        user_resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {gh_token}",
                "Accept": "application/json"
            },
            timeout=5
        )
        gh_user = user_resp.json()
        logger.info(f"GitHub user response status: {user_resp.status_code}")
        username = gh_user.get("login")
        
        if not username:
            logger.error(f"Unable to fetch GitHub username. Response: {gh_user}")
            raise Exception("Unable to fetch GitHub username")
        
        logger.info(f"GitHub user authenticated: {username}")
        
        # Check if this is a legacy flow (redirect_uri is our /callback endpoint)
        redirect_uri = session["redirect_uri"]
        legacy_callback_url = f"{config.server_url}/callback"
        
        if redirect_uri == legacy_callback_url:
            # Legacy flow: agent.py or client.py
            # Redirect to /callback with the GitHub access token in URL
            callback_url = f"{redirect_uri}?token={gh_token}&state={state}&username={username}"
            return RedirectResponse(url=callback_url)
        else:
            # Inspector and Claude Desktop flow: issue authorization code for token exchange
            auth_code = gen_random()
            auth_code_store[auth_code] = {
                "sub": username,
                "client_id": session.get("client_id"),
                "scope": session.get("scope"),
                "code_challenge": session.get("code_challenge"),
                "expires_at": time.time() + 120  # 2 minutes
            }
            
            callback_url = f"{redirect_uri}?code={auth_code}&state={state}"
            logger.info(f"Redirecting to Inspector or Claude Desktop callback: {callback_url}")
            logger.info(f"Authorization code: {auth_code}, expires in 120s")
            return RedirectResponse(url=callback_url)
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return HTMLResponse(
            f"<h1>Authentication Failed</h1><p>Error: {str(e)}</p>",
            status_code=500
        )


@mcp.custom_route("/token", ["POST"])
async def token_endpoint(request: Request):
    """
    OAuth2 Token Endpoint
    
    Claude Desktop exchanges the authorization code for an access token here.
    We validate the code and issue a JWT token.
    
    Form params (from Claude):
    - grant_type: Should be "authorization_code"
    - code: Authorization code from /authorize flow
    - redirect_uri: Must match original redirect_uri
    - code_verifier: PKCE verifier (if code_challenge was provided)
    - client_id: Optional client identifier
    """
    form = await request.form()
    grant_type = form.get("grant_type")
    code = form.get("code")
    code_verifier = form.get("code_verifier")
    redirect_uri = form.get("redirect_uri")
    
    # Validate grant type
    if grant_type != "authorization_code":
        return JSONResponse(
            {"error": "unsupported_grant_type"},
            status_code=400
        )
    
    # Validate authorization code
    if not code or code not in auth_code_store:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Invalid authorization code"},
            status_code=400
        )
    
    entry = auth_code_store.pop(code)  # One-time use
    
    # Check expiration
    if time.time() > entry["expires_at"]:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Authorization code expired"},
            status_code=400
        )
    
    # Verify PKCE if code_challenge was provided
    if entry.get("code_challenge"):
        if not code_verifier:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing code_verifier"},
                status_code=400
            )
        
        # Compute challenge from verifier
        import hashlib
        import base64
        verifier_hash = hashlib.sha256(code_verifier.encode()).digest()
        computed_challenge = base64.urlsafe_b64encode(verifier_hash).rstrip(b'=').decode('ascii')
        
        if computed_challenge != entry["code_challenge"]:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                status_code=400
            )
    
    # Issue JWT access token
    sub = entry["sub"]
    access_token = mint_jwt(sub)
    
    return JSONResponse({
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRES,
        "scope": entry.get("scope", "openid read:mcp write:mcp")
    })


# ============================================================================
# OAUTH2 CALLBACK ENDPOINT (Legacy - for client.py and agent.py)
# ============================================================================

@mcp.custom_route("/callback", ["GET"])
async def oauth_callback_legacy(request: Request):
    """
    Legacy OAuth callback endpoint for agent.py and client.py
    
    This endpoint receives the GitHub access token from /oauth/callback
    and displays it to the user for copy/paste into their terminal.
    
    For Claude Desktop, /oauth/callback handles the full OAuth flow with JWT tokens.
    """
    token = request.query_params.get("token")
    username = request.query_params.get("username")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    
    if error:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Authentication Error</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1 style="color: #d32f2f;">❌ Authentication Error</h1>
            <p>Error: {error}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=400)
    
    if not token:
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Missing Token</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1>❌ Missing Access Token</h1>
            <p>No access token received.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=400)
    
    # Display the token to the user
    try:
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 600px;
                }}
                h1 {{ color: #667eea; margin-bottom: 20px; }}
                p {{ color: #666; margin-bottom: 15px; }}
                .success-icon {{ font-size: 60px; margin-bottom: 20px; }}
                .token-box {{
                    background: #f4f4f4;
                    padding: 15px;
                    border-radius: 5px;
                    font-family: monospace;
                    word-break: break-all;
                    font-size: 12px;
                    margin: 20px 0;
                    max-height: 150px;
                    overflow-y: auto;
                }}
                .user-info {{
                    color: #667eea;
                    font-weight: bold;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Authentication Successful!</h1>
                <div class="user-info">Authenticated as: {username}</div>
                <p>Copy this token and paste it in your terminal:</p>
                <div class="token-box" id="token">{token}</div>
                <p style="font-size: 12px; color: #999;">
                    Token automatically copied to clipboard.<br/>
                    You can close this window and return to your terminal.
                </p>
                <script>
                    // Copy token to clipboard
                    navigator.clipboard.writeText('{token}').then(function() {{
                        console.log('Token copied to clipboard');
                    }}, function(err) {{
                        console.error('Could not copy token: ', err);
                    }});
                    
                    // Auto-close after 30 seconds
                    setTimeout(function() {{
                        window.close();
                    }}, 30000);
                </script>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
        
    except Exception as e:
        logger.error(f"Legacy callback error: {e}")
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Authentication Failed</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1 style="color: #d32f2f;">❌ Authentication Failed</h1>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=500)


# ============================================================================
# PUBLIC ENDPOINTS - Using custom_route
# ============================================================================

@mcp.custom_route("/", ["GET"])
async def root(request: Request):
    """Root endpoint with server information"""
    return JSONResponse({
        "name": "MCP Server with GitHub OAuth2",
        "version": "1.0.0",
        "authentication": "GitHub OAuth2",
        "transport": "HTTP Streaming (NDJSON)",
        "mcp_endpoints": {
            "http_streaming": f"{config.server_url}/mcp",
        },
        "oauth_metadata": {
            "protected_resource": f"{config.server_url}/.well-known/oauth-protected-resource",
            "authorization_server": f"{config.server_url}/.well-known/oauth-authorization-server"
        },
        "documentation": "https://github.com/datalayer/mcp-compose/tree/main/examples/mcp-auth"
    })


@mcp.custom_route("/health", ["GET"])
async def health_check(request: Request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "authentication": "required",
        "oauth_provider": "GitHub"
    })


# ============================================================================
# AUTHENTICATION MIDDLEWARE FOR MCP HTTP STREAMING ENDPOINTS
# ============================================================================

class AuthMiddleware:
    """
    Pure ASGI middleware that validates OAuth2 token for MCP requests
    
    This works properly with streaming responses (HTTP streaming)
    """
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get the path
        path = scope["path"]
        
        # Skip auth for public endpoints
        public_paths = ["/", "/health", "/callback", 
                       "/.well-known/oauth-protected-resource", 
                       "/.well-known/oauth-authorization-server"]
        
        if path in public_paths:
            await self.app(scope, receive, send)
            return
        
        # Require auth for MCP endpoint (/mcp)
        if path == "/mcp" or path.startswith("/mcp/"):
            # Extract Authorization header
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode("utf-8")
            
            try:
                # Validate token
                user_info = await verify_token(auth_header)
                
                # Store user info in scope state for potential use in tools
                if "state" not in scope:
                    scope["state"] = {}
                scope["state"]["user"] = user_info
                
                # Continue to the app
                await self.app(scope, receive, send)
            
            except HTTPException as e:
                # Send error response
                response = JSONResponse(
                    status_code=e.status_code,
                    content={"error": e.detail},
                    headers=e.headers or {}
                )
                await response(scope, receive, send)
        else:
            # For all other paths, pass through
            await self.app(scope, receive, send)


# ============================================================================
# RUN SERVER
# ============================================================================

def main():
    """Main entry point for running the server"""
    import sys
    import io
    import os
    import uvicorn
    
    # Ensure stdout uses UTF-8 encoding for emoji support
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # Print startup message
    print_startup_message()
    
    # Get FastMCP's streamable HTTP app
    # This includes our custom HTTP streaming endpoints and built-in MCP support
    app = mcp.streamable_http_app()
    
    # Add CORS middleware for browser-based clients (like MCP Inspector)
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    # Wrap with authentication middleware (pure ASGI, supports streaming)
    app = AuthMiddleware(app)
    
    # Check for SSL certificates (mkcert generated)
    cert_file = os.path.join(os.path.dirname(__file__), "..", "localhost+2.pem")
    key_file = os.path.join(os.path.dirname(__file__), "..", "localhost+2-key.pem")
    
    ssl_enabled = os.path.exists(cert_file) and os.path.exists(key_file)
    
    # Run with uvicorn
    if ssl_enabled:
        print(f"\n🔒 HTTPS enabled with certificates:")
        print(f"   Certificate: {cert_file}")
        print(f"   Key: {key_file}")
        uvicorn.run(
            app,
            host=config.server_host,
            port=config.server_port,
            log_level="info",
            ssl_certfile=cert_file,
            ssl_keyfile=key_file
        )
    else:
        print(f"\n⚠️  Running in HTTP mode (no SSL certificates found)")
        print(f"   To enable HTTPS, generate certificates with: mkcert localhost 127.0.0.1 ::1")
        uvicorn.run(
            app,
            host=config.server_host,
            port=config.server_port,
            log_level="info"
        )


if __name__ == "__main__":
    main()
