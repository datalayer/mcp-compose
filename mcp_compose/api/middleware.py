"""
Metrics middleware for tracking HTTP requests.

Automatically records metrics for all HTTP requests including
duration, status codes, and request/response sizes.

Note: This middleware uses a pure ASGI implementation instead of
BaseHTTPMiddleware to properly support SSE/streaming responses.
"""

import time
from typing import Callable

from starlette.types import ASGIApp, Receive, Send, Scope

from ..metrics import metrics_collector


class MetricsMiddleware:
    """
    Pure ASGI Middleware for collecting HTTP request metrics.
    
    This implementation uses raw ASGI instead of BaseHTTPMiddleware
    to properly support SSE and streaming responses.
    """
    
    # Paths that should skip metrics (streaming endpoints)
    SKIP_PATHS = {"/sse", "/mcp", "/stream"}
    
    def __init__(self, app: ASGIApp):
        """
        Initialize metrics middleware.
        
        Args:
            app: ASGI application.
        """
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ASGI interface - process request and record metrics.
        
        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        # Only process HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get request info
        path = scope.get("path", "/")
        method = scope.get("method", "GET")
        
        # Skip metrics for streaming endpoints (SSE, MCP streaming)
        # These don't work well with metrics collection due to their streaming nature
        if any(path.startswith(skip_path) for skip_path in self.SKIP_PATHS):
            await self.app(scope, receive, send)
            return
        
        # Record start time
        start_time = time.time()
        
        # Normalize endpoint
        endpoint = self._normalize_endpoint(path)
        
        # Get request size from headers
        request_size = 0
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"content-length":
                try:
                    request_size = int(header_value.decode())
                except (ValueError, UnicodeDecodeError):
                    pass
                break
        
        # Track response info
        status_code = 200
        response_size = 0
        
        async def send_wrapper(message):
            nonlocal status_code, response_size
            
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                # Get content-length from response headers
                for header_name, header_value in message.get("headers", []):
                    if header_name == b"content-length":
                        try:
                            response_size = int(header_value.decode())
                        except (ValueError, UnicodeDecodeError):
                            pass
                        break
            
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            metrics_collector.record_http_request(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration_seconds=duration,
                request_size_bytes=request_size,
                response_size_bytes=response_size,
            )
    
    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize endpoint path by removing dynamic parts.
        
        Args:
            path: Request path.
        
        Returns:
            Normalized endpoint path.
        """
        # Split path into parts
        parts = path.split("/")
        
        # Normalize dynamic parts (UUIDs, IDs, etc.)
        normalized_parts = []
        for part in parts:
            if not part:
                continue
            
            # Check if part looks like an ID or UUID
            if self._is_dynamic_part(part):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)
        
        # Reconstruct path
        return "/" + "/".join(normalized_parts) if normalized_parts else "/"
    
    def _is_dynamic_part(self, part: str) -> bool:
        """
        Check if path part is dynamic (ID, UUID, etc.).
        
        Args:
            part: Path part.
        
        Returns:
            True if dynamic, False otherwise.
        """
        # Check for common ID patterns
        
        # UUIDs (8-4-4-4-12 format)
        if len(part) == 36 and part.count("-") == 4:
            return True
        
        # Numeric IDs
        if part.isdigit():
            return True
        
        # Hex IDs
        if len(part) > 8 and all(c in "0123456789abcdef" for c in part.lower()):
            return True
        
        # Short IDs (alphanumeric, length < 16)
        if len(part) < 16 and part.replace("-", "").replace("_", "").isalnum():
            # Check if it's NOT a known endpoint keyword
            keywords = [
                "api", "v1", "health", "version", "servers", "tools", "prompts",
                "resources", "config", "status", "composition", "metrics",
                "start", "stop", "restart", "logs", "invoke", "validate", "reload",
                "detailed", "prometheus",
            ]
            if part.lower() not in keywords:
                return True
        
        return False


__all__ = ["MetricsMiddleware"]
