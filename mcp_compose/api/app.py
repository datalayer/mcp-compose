"""
FastAPI application for MCP Compose REST API.

This module provides the main FastAPI application with routing,
middleware, and configuration for the REST API server.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..auth import AuthenticationError, InsufficientScopesError
from ..exceptions import (
    MCPComposerError,
    MCPConfigurationError,
    MCPDiscoveryError,
    MCPToolConflictError,
)
from ..__version__ import __version__

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting MCP Compose API")
    yield
    # Shutdown
    logger.info("Shutting down MCP Compose API")
    
    # Stop all translators
    from .routes.translators import shutdown_translators
    await shutdown_translators()


def create_app(
    title: str = "MCP Compose API",
    description: str = "REST API for managing MCP Compose",
    version: str = __version__,
    cors_origins: Optional[list] = None,
    cors_credentials: bool = True,
    cors_methods: Optional[list] = None,
    cors_headers: Optional[list] = None,
) -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Args:
        title: API title.
        description: API description.
        version: API version.
        cors_origins: List of allowed CORS origins (default: ["*"]).
        cors_credentials: Whether to allow credentials in CORS.
        cors_methods: List of allowed HTTP methods (default: ["*"]).
        cors_headers: List of allowed HTTP headers (default: ["*"]).
    
    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=cors_credentials,
        allow_methods=cors_methods or ["*"],
        allow_headers=cors_headers or ["*"],
    )
    
    # Add metrics middleware
    from .middleware import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)
    
    # Initialize metrics
    from ..metrics import metrics_collector
    import platform
    metrics_collector.initialize(version=version, platform=platform.system())
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Register routes
    register_routes(app)
    
    return app


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers for the application.
    
    Args:
        app: FastAPI application.
    """
    
    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request,
        exc: AuthenticationError
    ):
        """Handle authentication errors."""
        return JSONResponse(
            status_code=401,
            content={
                "error": "authentication_failed",
                "message": str(exc),
                "details": exc.details if hasattr(exc, 'details') else None,
            }
        )
    
    @app.exception_handler(InsufficientScopesError)
    async def insufficient_scopes_handler(
        request: Request,
        exc: InsufficientScopesError
    ):
        """Handle authorization errors."""
        return JSONResponse(
            status_code=403,
            content={
                "error": "insufficient_permissions",
                "message": str(exc),
                "required_scopes": exc.required_scopes if hasattr(exc, 'required_scopes') else None,
            }
        )
    
    @app.exception_handler(MCPConfigurationError)
    async def configuration_error_handler(
        request: Request,
        exc: MCPConfigurationError
    ):
        """Handle configuration errors."""
        return JSONResponse(
            status_code=400,
            content={
                "error": "configuration_error",
                "message": str(exc),
            }
        )
    
    @app.exception_handler(MCPDiscoveryError)
    async def discovery_error_handler(
        request: Request,
        exc: MCPDiscoveryError
    ):
        """Handle discovery errors."""
        return JSONResponse(
            status_code=500,
            content={
                "error": "discovery_error",
                "message": str(exc),
            }
        )
    
    @app.exception_handler(MCPToolConflictError)
    async def tool_conflict_handler(
        request: Request,
        exc: MCPToolConflictError
    ):
        """Handle tool conflict errors."""
        return JSONResponse(
            status_code=409,
            content={
                "error": "tool_conflict",
                "message": str(exc),
            }
        )
    
    @app.exception_handler(MCPComposerError)
    async def mcp_error_handler(
        request: Request,
        exc: MCPComposerError
    ):
        """Handle general MCP errors."""
        return JSONResponse(
            status_code=500,
            content={
                "error": "mcp_error",
                "message": str(exc),
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception
    ):
        """Handle unexpected exceptions."""
        logger.exception("Unhandled exception in API request")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
            }
        )


def register_routes(app: FastAPI) -> None:
    """
    Register API routes.
    
    Args:
        app: FastAPI application.
    """
    from .routes import config, health, servers, status, tools, translators, version
    
    # Register route modules
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(servers.router, prefix="/api/v1", tags=["servers"])
    app.include_router(tools.router, prefix="/api/v1", tags=["tools", "prompts", "resources"])
    app.include_router(config.router, prefix="/api/v1", tags=["config"])
    app.include_router(status.router, prefix="/api/v1", tags=["status", "composition", "metrics"])
    app.include_router(translators.router, prefix="/api/v1", tags=["translators"])
    app.include_router(version.router, prefix="/api/v1", tags=["version"])
    
    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint - redirects to docs."""
        return {
            "name": "MCP Compose API",
            "version": __version__,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }


__all__ = [
    "create_app",
    "register_exception_handlers",
    "register_routes",
]
