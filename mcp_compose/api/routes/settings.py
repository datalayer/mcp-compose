# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Settings API routes for MCP Compose.

This module provides endpoints for managing application settings.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# Settings storage file
SETTINGS_FILE = Path.home() / ".mcp-compose" / "ui-settings.json"


class Settings(BaseModel):
    """Application settings model."""
    
    api_endpoint: Optional[str] = Field(default="http://localhost:9456", description="API endpoint URL")
    refresh_interval: int = Field(default=5, ge=1, le=60, description="Auto-refresh interval in seconds")
    enable_notifications: bool = Field(default=True, description="Enable browser notifications")
    enable_sounds: bool = Field(default=False, description="Enable sound alerts")
    max_log_lines: int = Field(default=500, description="Maximum log lines to keep in memory")


def load_settings() -> Settings:
    """
    Load settings from file or return defaults.
    
    Returns:
        Settings object.
    """
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                return Settings(**data)
    except Exception as e:
        logger.warning(f"Failed to load settings: {e}")
    
    return Settings()


def save_settings(settings: Settings) -> None:
    """
    Save settings to file.
    
    Args:
        settings: Settings object to save.
    """
    try:
        # Ensure directory exists
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Save settings
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings.model_dump(), f, indent=2)
            
        logger.info(f"Settings saved to {SETTINGS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@router.get("/settings", response_model=Settings)
async def get_settings():
    """
    Get application settings.
    
    Returns:
        Current settings.
    """
    return load_settings()


@router.put("/settings", response_model=Settings)
async def update_settings(settings: Settings):
    """
    Update application settings.
    
    Args:
        settings: New settings values.
    
    Returns:
        Updated settings.
    """
    save_settings(settings)
    return settings


@router.post("/settings/reset", response_model=Settings)
async def reset_settings():
    """
    Reset settings to defaults.
    
    Returns:
        Default settings.
    """
    default_settings = Settings()
    save_settings(default_settings)
    return default_settings
