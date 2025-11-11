"""
Metrics middleware for tracking HTTP requests.

Automatically records metrics for all HTTP requests including
duration, status codes, and request/response sizes.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..metrics import metrics_collector


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP request metrics."""
    
    def __init__(self, app: ASGIApp):
        """
        Initialize metrics middleware.
        
        Args:
            app: ASGI application.
        """
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and record metrics.
        
        Args:
            request: HTTP request.
            call_next: Next middleware/handler.
        
        Returns:
            HTTP response.
        """
        # Record start time
        start_time = time.time()
        
        # Get request info
        method = request.method
        path = request.url.path
        
        # Normalize endpoint (remove IDs and dynamic parts)
        endpoint = self._normalize_endpoint(path)
        
        # Get request size
        request_size = int(request.headers.get("content-length", 0))
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Get response size
        response_size = int(response.headers.get("content-length", 0))
        
        # Record metrics
        metrics_collector.record_http_request(
            method=method,
            endpoint=endpoint,
            status_code=response.status_code,
            duration_seconds=duration,
            request_size_bytes=request_size,
            response_size_bytes=response_size,
        )
        
        return response
    
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
