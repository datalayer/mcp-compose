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
import uuid
import asyncio
import logging
from typing import Dict, Optional, Any
import requests

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from mcp.server.fastmcp import FastMCP

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
        return f"http://{self.server_host}:{self.server_port}"


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
    
    Args:
        authorization: Authorization header value
    
    Returns:
        User information if token is valid
    
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": f'Bearer realm="{config.server_url}/.well-known/oauth-protected-resource"'}
        )
    
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": f'Bearer realm="{config.server_url}/.well-known/oauth-protected-resource"'}
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    
    # Validate token
    user_info = token_validator.validate_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": f'Bearer realm="{config.server_url}/.well-known/oauth-protected-resource"'}
        )
    
    return user_info


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

@mcp.custom_route("/.well-known/oauth-protected-resource", ["GET"])
async def protected_resource_metadata(request: Request):
    """
    Protected Resource Metadata (RFC 9728)
    
    Indicates which authorization server(s) protect this resource
    """
    return JSONResponse({
        "resource": config.server_url,
        "authorization_servers": [config.server_url],
        "bearer_methods_supported": ["header"],
        "resource_documentation": "https://github.com/datalayer/mcp-compose/tree/main/examples/mcp-auth"
    })


@mcp.custom_route("/.well-known/oauth-authorization-server", ["GET"])
async def authorization_server_metadata(request: Request):
    """
    Authorization Server Metadata (RFC 8414)
    
    Describes OAuth endpoints and capabilities
    This server proxies to GitHub OAuth
    """
    return JSONResponse({
        "issuer": config.server_url,
        "authorization_endpoint": "https://github.com/login/oauth/authorize",
        "token_endpoint": "https://github.com/login/oauth/access_token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "service_documentation": "https://docs.github.com/en/developers/apps/building-oauth-apps"
    })


# ============================================================================
# OAUTH2 CALLBACK ENDPOINT - Using custom_route
# ============================================================================

@mcp.custom_route("/callback", ["GET"])
async def oauth_callback(request: Request):
    """
    OAuth callback endpoint
    
    Users are redirected here after authorizing with GitHub
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Authentication Successful</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                text-align: center;
                max-width: 500px;
            }
            h1 { color: #667eea; margin-bottom: 20px; }
            p { color: #666; margin-bottom: 15px; }
            .success-icon { font-size: 60px; margin-bottom: 20px; }
            .code { background: #f4f4f4; padding: 10px; border-radius: 5px; 
                    font-family: monospace; word-break: break-all; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>Authentication Successful!</h1>
            <p>You have successfully authenticated with GitHub.</p>
            <p>You can now close this window and return to your application.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


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
    import uvicorn
    
    # Ensure stdout uses UTF-8 encoding for emoji support
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # Print startup message
    print_startup_message()
    
    # Get FastMCP's streamable HTTP app
    # This includes our custom HTTP streaming endpoints and built-in MCP support
    app = mcp.streamable_http_app()
    
    # Wrap with authentication middleware (pure ASGI, supports streaming)
    app = AuthMiddleware(app)
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=config.server_host,
        port=config.server_port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
