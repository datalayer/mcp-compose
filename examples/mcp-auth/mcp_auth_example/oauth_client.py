#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OAuth2 Client Module - Shared Authentication Logic

This module provides reusable OAuth2 authentication functionality for both
the CLI demo client and the pydantic-ai agent.

Features:
- PKCE (Proof Key for Code Exchange) helper
- OAuth2 metadata discovery (RFC 8414, RFC 9728)
- Authorization code flow with GitHub
- Local callback server for handling OAuth redirects
- Token management

Usage:
    from oauth_client import OAuthClient
    
    oauth = OAuthClient("config.json")
    if oauth.authenticate():
        token = oauth.access_token
        # Use token with MCP server
"""

import json
import hashlib
import secrets
import base64
import webbrowser
from typing import Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, urlencode
import requests
import threading
import time


class Config:
    """Configuration management for OAuth client"""
    
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
    def server_url(self) -> str:
        host = self.config["server"]["host"]
        port = self.config["server"]["port"]
        return f"http://{host}:{port}"
    
    @property
    def callback_url(self) -> str:
        """Callback URL for OAuth - uses port 8081 to avoid conflict with server on 8080"""
        host = self.config["server"]["host"]
        return f"http://{host}:8081/callback"
    
    @property
    def server_host(self) -> str:
        return self.config["server"]["host"]


class PKCEHelper:
    """Helper for PKCE (Proof Key for Code Exchange) - RFC 7636"""
    
    @staticmethod
    def generate_code_verifier() -> str:
        """
        Generate a random code verifier
        
        Per RFC 7636: 43-128 characters, [A-Z] / [a-z] / [0-9] / "-" / "." / "_" / "~"
        """
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        """
        Generate code challenge from verifier using S256 method
        
        challenge = BASE64URL(SHA256(verifier))
        """
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles OAuth callback from GitHub"""
    
    authorization_code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    
    def do_GET(self):
        """Handle callback from OAuth provider"""
        query_components = parse_qs(urlparse(self.path).query)
        
        # Extract authorization code, state, and error
        if "code" in query_components:
            OAuthCallbackHandler.authorization_code = query_components["code"][0]
        
        if "state" in query_components:
            OAuthCallbackHandler.state = query_components["state"][0]
        
        if "error" in query_components:
            OAuthCallbackHandler.error = query_components["error"][0]
        
        # Send success response
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        
        if OAuthCallbackHandler.error:
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Error</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #f06292 0%, #ba68c8 100%);
                    }}
                    .container {{
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                        text-align: center;
                    }}
                    h1 {{ color: #f06292; margin-bottom: 20px; }}
                    p {{ color: #666; }}
                    .error-icon {{ font-size: 60px; margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">❌</div>
                    <h1>Authentication Error</h1>
                    <p>Error: {OAuthCallbackHandler.error}</p>
                    <p>You can close this window and return to your terminal.</p>
                </div>
            </body>
            </html>
            """
        else:
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Complete</title>
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
                    }
                    h1 { color: #667eea; margin-bottom: 20px; }
                    p { color: #666; }
                    .success-icon { font-size: 60px; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <!--
                    <div class="success-icon">✅</div>
                    -->
                    <h1>Authorization Complete!</h1>
                    <p>You can close this window and return to your terminal.</p>
                </div>
            </body>
            </html>
            """
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Suppress log messages"""
        pass


class OAuthClient:
    """
    Reusable OAuth2 client for MCP server authentication
    
    This class handles the complete OAuth2 flow including:
    - Metadata discovery (RFC 8414, RFC 9728)
    - PKCE generation (RFC 7636)
    - Authorization code flow with GitHub
    - Token exchange
    """
    
    def __init__(self, config_file: str = "config.json", verbose: bool = True):
        """
        Initialize OAuth client
        
        Args:
            config_file: Path to configuration file
            verbose: Whether to print detailed status messages
        """
        self.config = Config(config_file)
        self.verbose = verbose
        self.access_token: Optional[str] = None
        self.server_metadata: Optional[Dict] = None
        self.auth_server_metadata: Optional[Dict] = None
    
    def _print(self, message: str):
        """Print message if verbose mode is enabled"""
        if self.verbose:
            print(message, flush=True)
    
    def discover_metadata(self) -> bool:
        """
        Discover OAuth metadata from MCP server
        
        Following MCP Authorization spec:
        1. Make unauthenticated request to MCP server endpoint
        2. Receive 401 with WWW-Authenticate header
        3. Fetch Protected Resource Metadata (RFC 9728)
        4. Fetch Authorization Server Metadata (RFC 8414)
        
        Returns:
            True if metadata discovery successful, False otherwise
        """
        if self.verbose:
            self._print("\n" + "=" * 70)
            self._print("🔍 Discovering OAuth Metadata")
            self._print("=" * 70)
        
        try:
            # Make unauthenticated request to MCP endpoint
            self._print(f"\n📡 Requesting: {self.config.server_url}/mcp")
            response = requests.get(f"{self.config.server_url}/mcp", timeout=5)
            
            if response.status_code == 401:
                self._print("✅ Received 401 Unauthorized (expected)")
                
                # Extract WWW-Authenticate header
                www_auth = response.headers.get("WWW-Authenticate")
                if not www_auth:
                    self._print("❌ Error: No WWW-Authenticate header found")
                    return False
                
                self._print(f"   WWW-Authenticate: {www_auth}")
                
                # Extract realm (protected resource metadata URL)
                if 'realm=' in www_auth:
                    realm = www_auth.split('realm="')[1].split('"')[0]
                else:
                    realm = f"{self.config.server_url}/.well-known/oauth-protected-resource"
                
                # Fetch Protected Resource Metadata
                self._print(f"\n📡 Fetching metadata from: {realm}")
                pr_response = requests.get(realm, timeout=5)
                
                if pr_response.status_code != 200:
                    self._print(f"❌ Error: Failed to fetch metadata (status: {pr_response.status_code})")
                    return False
                
                self.server_metadata = pr_response.json()
                if self.verbose:
                    self._print("✅ Protected Resource Metadata received:")
                    self._print(f"   {json.dumps(self.server_metadata, indent=3)}")
                
                # Extract authorization server URL
                auth_servers = self.server_metadata.get("authorization_servers", [])
                if not auth_servers:
                    self._print("❌ Error: No authorization servers found")
                    return False
                
                auth_server_url = auth_servers[0]
                
                # Fetch Authorization Server Metadata
                as_metadata_url = f"{auth_server_url}/.well-known/oauth-authorization-server"
                self._print(f"📡 Fetching auth server metadata from: {as_metadata_url}")
                
                as_response = requests.get(as_metadata_url, timeout=5)
                
                if as_response.status_code != 200:
                    self._print(f"❌ Error: Failed to fetch auth server metadata (status: {as_response.status_code})")
                    return False
                
                self.auth_server_metadata = as_response.json()
                if self.verbose:
                    self._print("✅ Authorization Server Metadata received")
                
                return True
            
            else:
                self._print(f"❌ Error: Expected 401, got {response.status_code}")
                return False
        
        except Exception as e:
            self._print(f"❌ Error during metadata discovery: {e}")
            return False
    
    def authenticate(self) -> bool:
        """
        Perform OAuth2 authentication flow
        
        Following OAuth 2.1 with PKCE (RFC 6749, RFC 7636):
        1. Generate PKCE parameters
        2. Build authorization URL
        3. Open browser for user authentication
        4. Receive authorization code via callback
        5. Exchange code for access token
        
        Returns:
            True if authentication successful, False otherwise
        """
        if self.verbose:
            self._print("\n" + "=" * 70)
            self._print("🔐 OAuth2 Authentication Flow")
            self._print("=" * 70)
        
        # Ensure metadata is available
        if not self.auth_server_metadata:
            self._print("📡 Discovering metadata first...")
            if not self.discover_metadata():
                self._print("❌ Error: Metadata discovery failed")
                return False
        
        # Generate PKCE parameters
        self._print("\n🔑 Generating PKCE parameters...")
        code_verifier = PKCEHelper.generate_code_verifier()
        code_challenge = PKCEHelper.generate_code_challenge(code_verifier)
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Build authorization URL
        auth_endpoint = self.auth_server_metadata["authorization_endpoint"]
        
        params = {
            "client_id": self.config.github_client_id,
            "redirect_uri": self.config.callback_url,
            "response_type": "code",
            "scope": "user",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # RFC 8707: Resource parameter binds token to MCP server
            "resource": self.config.server_url
        }
        
        auth_url = f"{auth_endpoint}?{urlencode(params)}"
        
        self._print(f"\n🌐 Opening browser for GitHub authentication...")
        
        # Start local callback server on port 8081
        try:
            callback_server = HTTPServer(
                (self.config.server_host, 8081),
                OAuthCallbackHandler
            )
        except OSError as e:
            self._print(f"❌ Error: Failed to start callback server: {e}")
            self._print("   Make sure port 8081 is available")
            return False
        
        # Reset class variables
        OAuthCallbackHandler.authorization_code = None
        OAuthCallbackHandler.state = None
        OAuthCallbackHandler.error = None
        
        # Run callback server in background thread
        server_thread = threading.Thread(target=callback_server.handle_request)
        server_thread.daemon = True
        server_thread.start()
        
        # Open browser
        webbrowser.open(auth_url)
        
        self._print("⏳ Waiting for authorization...")
        self._print("   (Callback server listening on port 8081)")
        
        # Wait for callback
        timeout = 300  # 5 minutes
        start_time = time.time()
        
        while OAuthCallbackHandler.authorization_code is None and OAuthCallbackHandler.error is None:
            if time.time() - start_time > timeout:
                self._print("❌ Timeout waiting for authorization")
                return False
            time.sleep(0.5)
        
        # Give the server thread a moment to finish
        time.sleep(0.5)
        
        # Check for errors
        if OAuthCallbackHandler.error:
            self._print(f"❌ OAuth error: {OAuthCallbackHandler.error}")
            return False
        
        self._print("✅ Authorization code received")
        
        # Verify state
        if OAuthCallbackHandler.state != state:
            self._print("❌ Error: State mismatch (possible CSRF attack)")
            return False
        
        # Exchange authorization code for access token
        self._print("\n🔄 Exchanging code for access token...")
        
        token_endpoint = self.auth_server_metadata["token_endpoint"]
        
        token_data = {
            "client_id": self.config.github_client_id,
            "client_secret": self.config.github_client_secret,
            "code": OAuthCallbackHandler.authorization_code,
            "redirect_uri": self.config.callback_url,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code"
        }
        
        try:
            token_response = requests.post(
                token_endpoint,
                data=token_data,
                headers={"Accept": "application/json"},
                timeout=10
            )
            
            if token_response.status_code != 200:
                self._print(f"❌ Error: Token exchange failed (status: {token_response.status_code})")
                self._print(f"   Response: {token_response.text}")
                return False
            
            token_json = token_response.json()
            self.access_token = token_json.get("access_token")
            
            if not self.access_token:
                self._print("❌ Error: No access token in response")
                return False
            
            self._print("✅ Access token received")
            
            return True
        
        except Exception as e:
            self._print(f"❌ Error during token exchange: {e}")
            return False
    
    def get_token(self) -> Optional[str]:
        """
        Get the current access token
        
        Returns:
            Access token if available, None otherwise
        """
        return self.access_token
    
    def get_server_url(self) -> str:
        """Get the MCP server URL"""
        return self.config.server_url
