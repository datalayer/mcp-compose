# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
API routes for proxy/translator functionality.

Provides endpoints for managing protocol translators.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status

from ...exceptions import ValidationError
from ...proxy import TranslatorManager
from ..dependencies import get_composer
from ..models import ErrorResponse

router = APIRouter(prefix="/translators", tags=["translators"])

# Global translator manager
_translator_manager: Optional[TranslatorManager] = None


def get_translator_manager() -> TranslatorManager:
    """Get or create the global translator manager."""
    global _translator_manager
    if _translator_manager is None:
        _translator_manager = TranslatorManager()
    return _translator_manager


@router.post(
    "/stdio-to-sse",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid configuration"},
        500: {"model": ErrorResponse, "description": "Failed to start translator"},
    },
)
async def create_stdio_to_sse_translator(
    name: str,
    sse_url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
):
    """
    Create a STDIO→SSE translator.
    
    Enables STDIO clients to communicate with SSE servers.
    
    Args:
        name: Unique translator identifier.
        sse_url: URL of the SSE server endpoint.
        headers: Optional HTTP headers (e.g., authentication).
        timeout: Request timeout in seconds.
    
    Returns:
        Translator configuration.
    """
    manager = get_translator_manager()
    
    # Check if translator already exists
    if manager.get_translator(name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Translator '{name}' already exists",
        )
    
    try:
        translator = await manager.add_stdio_to_sse(
            name=name,
            sse_url=sse_url,
            headers=headers,
            timeout=timeout,
        )
        
        return {
            "name": name,
            "type": "stdio-to-sse",
            "sse_url": sse_url,
            "timeout": timeout,
            "status": "running",
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start translator: {str(e)}",
        )


@router.post(
    "/sse-to-stdio",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid configuration"},
        500: {"model": ErrorResponse, "description": "Failed to start translator"},
    },
)
async def create_sse_to_stdio_translator(
    name: str,
    command: str,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
):
    """
    Create an SSE→STDIO translator.
    
    Enables SSE clients to communicate with STDIO servers.
    
    Args:
        name: Unique translator identifier.
        command: Command to run STDIO server.
        args: Command arguments.
        env: Environment variables.
        cwd: Working directory.
    
    Returns:
        Translator configuration.
    """
    manager = get_translator_manager()
    
    # Check if translator already exists
    if manager.get_translator(name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Translator '{name}' already exists",
        )
    
    try:
        translator = await manager.add_sse_to_stdio(
            name=name,
            command=command,
            args=args,
            env=env,
            cwd=cwd,
        )
        
        return {
            "name": name,
            "type": "sse-to-stdio",
            "command": command,
            "args": args or [],
            "status": "running",
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start translator: {str(e)}",
        )


@router.get(
    "",
    responses={
        500: {"model": ErrorResponse, "description": "Failed to list translators"},
    },
)
async def list_translators():
    """
    List all active translators.
    
    Returns:
        List of translator configurations.
    """
    manager = get_translator_manager()
    
    translators = []
    for name, translator in manager.translators.items():
        translator_type = (
            "stdio-to-sse"
            if translator.__class__.__name__ == "StdioToSseTranslator"
            else "sse-to-stdio"
        )
        
        translators.append({
            "name": name,
            "type": translator_type,
            "status": "running" if translator.running else "stopped",
        })
    
    return {
        "translators": translators,
        "total": len(translators),
    }


@router.delete(
    "/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "Translator not found"},
        500: {"model": ErrorResponse, "description": "Failed to stop translator"},
    },
)
async def delete_translator(name: str):
    """
    Stop and remove a translator.
    
    Args:
        name: Translator identifier.
    """
    manager = get_translator_manager()
    
    if not manager.get_translator(name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translator '{name}' not found",
        )
    
    try:
        await manager.remove_translator(name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop translator: {str(e)}",
        )


@router.post(
    "/{name}/translate",
    responses={
        404: {"model": ErrorResponse, "description": "Translator not found"},
        500: {"model": ErrorResponse, "description": "Translation failed"},
    },
)
async def translate_message(name: str, request: Request):
    """
    Translate a message through the specified translator.
    
    Args:
        name: Translator identifier.
        request: FastAPI request containing message.
    
    Returns:
        Translated message.
    """
    manager = get_translator_manager()
    
    translator = manager.get_translator(name)
    if not translator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translator '{name}' not found",
        )
    
    try:
        # Get message from request body
        message = await request.json()
        
        # Translate message
        response = await translator.translate(message)
        
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}",
        )


# Cleanup on shutdown
async def shutdown_translators():
    """Stop all translators on shutdown."""
    manager = get_translator_manager()
    await manager.stop_all()
