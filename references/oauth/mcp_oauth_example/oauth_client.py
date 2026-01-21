#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

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
from urllib.parse import urlencode, urlparse, parse_qs
import requests
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading


class Config:
    """Configuration management for OAuth client"""
    
    def __init__(self, config_file: str = "config.json"):
        with open(config_file) as f:
            self.config = json.load(f)
    
    @property
    def github_client_id(self) -> str:
        return self.config["oauth"]["client_id"]
    
    @property
    def github_client_secret(self) -> str:
        return self.config["oauth"]["client_secret"]
    
    @property
    def authorization_endpoint(self) -> str:
        return self.config["oauth"]["authorization_endpoint"]
    
    @property
    def token_endpoint(self) -> str:
        return self.config["oauth"]["token_endpoint"]
    
    @property
    def userinfo_endpoint(self) -> str:
        return self.config["oauth"]["userinfo_endpoint"]
    
    @property
    def server_url(self) -> str:
        """
        Get server URL with HTTPS if certificates are available.
        Matches the logic in server.py for consistency.
        """
        import os
        host = self.config["server"]["host"]
        port = self.config["server"]["port"]
        
        # Check for SSL certificates (same logic as server.py)
        cert_file = os.path.join(os.path.dirname(__file__), "..", "localhost+2.pem")
        key_file = os.path.join(os.path.dirname(__file__), "..", "localhost+2-key.pem")
        ssl_enabled = os.path.exists(cert_file) and os.path.exists(key_file)
        
        protocol = "https" if ssl_enabled else "http"
        return f"{protocol}://{host}:{port}"
    
    @property
    def callback_url(self) -> str:
        """
        Callback URL for OAuth
        
        Uses a local callback server for automated token capture.
        """
        return "http://localhost:8888/callback"
    
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


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
    
    # Class variables to store callback data
    callback_data: Optional[Dict[str, str]] = None
    callback_received = threading.Event()
    
    def do_GET(self):
        """Handle GET request for OAuth callback"""
        # Parse the callback URL
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        # Extract token or error from query parameters
        token = params.get('token', [None])[0]
        error = params.get('error', [None])[0]
        state = params.get('state', [None])[0]
        username = params.get('username', [None])[0]
        
        # Store callback data
        CallbackHandler.callback_data = {
            'token': token,
            'error': error,
            'state': state,
            'username': username
        }
        
        # Send response to browser
        if token:
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
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
                    .user-info {{ color: #667eea; font-weight: bold; margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✅</div>
                    <h1>Authentication Successful!</h1>
                    <div class="user-info">Authenticated as: {username or 'User'}</div>
                    <p>Token has been automatically captured.</p>
                    <p>You can close this window and return to your terminal.</p>
                    <script>
                        // Auto-close after 3 seconds
                        setTimeout(function() {{
                            window.close();
                        }}, 3000);
                    </script>
                </div>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        else:
            error_msg = error or 'Unknown error'
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Authentication Error</title>
            </head>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1 style="color: #d32f2f;">❌ Authentication Error</h1>
                <p>Error: {error_msg}</p>
                <p>You can close this window.</p>
            </body>
            </html>
            """
            self.send_response(400)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        # Signal that callback was received
        CallbackHandler.callback_received.set()
    
    def log_message(self, format, *args):
        """Suppress request logging"""
        pass


class OAuthClient:
    """
    Reusable OAuth2 client for MCP server authentication
    
    This class handles the complete OAuth2 flow including:
    - Metadata discovery (RFC 8414, RFC 9728)
    - PKCE generation (RFC 7636)
    - Authorization code flow with GitHub
    - Token exchange
    - Automated callback handling with local HTTP server
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
        self.callback_server: Optional[HTTPServer] = None
        self.callback_thread: Optional[threading.Thread] = None
    
    def _should_verify_ssl(self, url: str) -> bool:
        """
        Determine if SSL verification should be enabled for a URL.
        
        For local development with mkcert (https://localhost), we disable verification
        since mkcert creates trusted certificates in the system store, but Python's
        requests library may not find them depending on the environment.
        
        In production with proper CA-signed certificates, this should return True.
        """
        return not url.startswith("https://localhost")
    
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
            # For local HTTPS (mkcert), disable SSL verification or it will fail
            # In production, this should be True with proper certificates
            verify_ssl = not self.config.server_url.startswith("https://localhost")
            response = requests.get(f"{self.config.server_url}/mcp", timeout=5, verify=verify_ssl)
            
            if response.status_code == 401:
                self._print("✅ Received 401 Unauthorized (expected)")
                
                # Extract WWW-Authenticate header
                www_auth = response.headers.get("WWW-Authenticate")
                if not www_auth:
                    self._print("❌ Error: No WWW-Authenticate header found")
                    return False
                
                self._print(f"   WWW-Authenticate: {www_auth}")
                
                # Extract resource_metadata URL from WWW-Authenticate header
                # New format: Bearer realm="mcp", resource_metadata="https://...", scope="..."
                # Old format: Bearer realm="https://..."
                metadata_url = None
                if 'resource_metadata="' in www_auth:
                    # New format - extract resource_metadata parameter
                    metadata_url = www_auth.split('resource_metadata="')[1].split('"')[0]
                elif 'realm="' in www_auth:
                    # Old format - use realm if it's a full URL
                    realm = www_auth.split('realm="')[1].split('"')[0]
                    if realm.startswith('http'):
                        metadata_url = realm
                
                # Fallback to default well-known URL
                if not metadata_url:
                    metadata_url = f"{self.config.server_url}/.well-known/oauth-protected-resource"
                
                # Fetch Protected Resource Metadata
                self._print(f"\n📡 Fetching metadata from: {metadata_url}")
                pr_response = requests.get(metadata_url, timeout=5, verify=self._should_verify_ssl(metadata_url))
                
                if pr_response.status_code != 200:
                    self._print(f"❌ Error: Failed to fetch metadata (status: {pr_response.status_code})")
                    return False
                
                self.server_metadata = pr_response.json()
                if self.verbose:
                    self._print("✅ Protected Resource Metadata received:")
                    self._print(f"   {json.dumps(self.server_metadata, indent=3)}")
                
                # Handle two possible formats:
                # 1. New format: metadata includes authorization_endpoint directly (server is its own auth server)
                # 2. Old format: metadata includes authorization_servers array pointing to separate auth server
                
                if "authorization_endpoint" in self.server_metadata:
                    # New format: server metadata IS the authorization server metadata
                    self.auth_server_metadata = self.server_metadata
                    if self.verbose:
                        self._print("✅ Server acts as its own authorization server")
                else:
                    # Old format: need to fetch separate authorization server metadata
                    auth_servers = self.server_metadata.get("authorization_servers", [])
                    if not auth_servers:
                        self._print("❌ Error: No authorization servers found")
                        return False
                    
                    auth_server_url = auth_servers[0]
                    
                    # Fetch Authorization Server Metadata
                    as_metadata_url = f"{auth_server_url}/.well-known/oauth-authorization-server"
                    self._print(f"📡 Fetching auth server metadata from: {as_metadata_url}")
                    
                    as_response = requests.get(as_metadata_url, timeout=5, verify=self._should_verify_ssl(as_metadata_url))
                    
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
    
    def _start_callback_server(self) -> bool:
        """
        Start local HTTP server to receive OAuth callback
        
        Returns:
            True if server started successfully, False otherwise
        """
        try:
            # Reset callback state
            CallbackHandler.callback_data = None
            CallbackHandler.callback_received.clear()
            
            # Start server on localhost:8888
            self.callback_server = HTTPServer(('localhost', 8888), CallbackHandler)
            
            # Run server in background thread
            def serve():
                # Handle a single request then stop
                self.callback_server.handle_request()
            
            self.callback_thread = threading.Thread(target=serve, daemon=True)
            self.callback_thread.start()
            
            self._print("✅ Local callback server started on http://localhost:8888")
            return True
            
        except Exception as e:
            self._print(f"❌ Failed to start callback server: {e}")
            self._print("   Make sure port 8888 is not in use")
            return False
    
    def _stop_callback_server(self):
        """Stop the local callback server"""
        if self.callback_server:
            try:
                self.callback_server.server_close()
            except:
                pass
            self.callback_server = None
        self.callback_thread = None
    
    def authenticate(self) -> bool:
        """
        Perform OAuth2 authentication flow with automated callback handling
        
        Following OAuth 2.1 with PKCE (RFC 6749, RFC 7636):
        1. Start local callback server
        2. Generate PKCE parameters
        3. Build authorization URL
        4. Open browser for user authentication
        5. Automatically receive token via callback
        6. Verify token
        
        Returns:
            True if authentication successful, False otherwise
        """
        if self.verbose:
            self._print("\n" + "=" * 70)
            self._print("🔐 OAuth2 Authentication Flow (Automated)")
            self._print("=" * 70)
        
        # Ensure metadata is available
        if not self.auth_server_metadata:
            self._print("📡 Discovering metadata first...")
            if not self.discover_metadata():
                self._print("❌ Error: Metadata discovery failed")
                return False
        
        # Start local callback server
        self._print("\n🌐 Starting local callback server...")
        if not self._start_callback_server():
            return False
        
        try:
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
            self._print(f"   Authorization URL: {auth_endpoint}")
            self._print(f"   Callback URL: {self.config.callback_url}")
            
            # Open browser
            webbrowser.open(auth_url)
            
            self._print("\n⏳ Waiting for you to complete authentication in the browser...")
            self._print("   The token will be captured automatically.")
            
            # Wait for callback (with timeout)
            callback_received = CallbackHandler.callback_received.wait(timeout=120)  # 2 minutes
            
            if not callback_received:
                self._print("❌ Timeout: Did not receive callback within 2 minutes")
                return False
            
            # Extract callback data
            callback_data = CallbackHandler.callback_data
            
            if not callback_data:
                self._print("❌ Error: No callback data received")
                return False
            
            # Check for errors
            if callback_data.get('error'):
                self._print(f"❌ OAuth error: {callback_data['error']}")
                return False
            
            # Verify state matches (CSRF protection)
            if callback_data.get('state') != state:
                self._print("❌ Error: State mismatch (possible CSRF attack)")
                return False
            
            # Extract token
            token = callback_data.get('token')
            username = callback_data.get('username')
            
            if not token:
                self._print("❌ Error: No token in callback")
                return False
            
            self._print(f"✅ Token received automatically!")
            if username:
                self._print(f"   Authenticated as: {username}")
            
            # Store the token
            self.access_token = token
            
            # Verify the token works by making a test request
            self._print("\n🔍 Verifying token...")
            test_response = requests.get(
                f"{self.config.server_url}/health",
                headers={"Authorization": f"Bearer {self.access_token}"},
                verify=self._should_verify_ssl(self.config.server_url)
            )
            
            if test_response.status_code == 200:
                self._print("✅ Token verified successfully")
                return True
            else:
                self._print(f"❌ Token verification failed (status: {test_response.status_code})")
                self._print(f"   Response: {test_response.text}")
                return False
        
        except KeyboardInterrupt:
            self._print("\n❌ Authentication cancelled")
            return False
        except Exception as e:
            self._print(f"❌ Error during authentication: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Clean up callback server
            self._stop_callback_server()
    
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
