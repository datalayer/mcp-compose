"""
Tests for Settings API routes.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from mcp_compose.api.app import create_app
from mcp_compose.api.routes.settings import SETTINGS_FILE, Settings


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_settings():
    """Clean up settings file after each test."""
    yield
    if SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()


def test_get_default_settings(client):
    """Test getting default settings when file doesn't exist."""
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    
    # Check default values
    assert data["api_endpoint"] == "http://localhost:9456"
    assert data["refresh_interval"] == 5
    assert data["enable_notifications"] is True
    assert data["enable_sounds"] is False
    assert data["max_log_lines"] == 500


def test_update_settings(client):
    """Test updating settings."""
    new_settings = {
        "api_endpoint": "http://localhost:8000",
        "refresh_interval": 10,
        "enable_notifications": False,
        "enable_sounds": True,
        "max_log_lines": 1000,
    }
    
    response = client.put("/api/v1/settings", json=new_settings)
    assert response.status_code == 200
    data = response.json()
    
    # Check updated values
    assert data["api_endpoint"] == "http://localhost:8000"
    assert data["refresh_interval"] == 10
    assert data["enable_notifications"] is False
    assert data["enable_sounds"] is True
    assert data["max_log_lines"] == 1000
    
    # Verify file was created
    assert SETTINGS_FILE.exists()
    
    # Verify file content
    with open(SETTINGS_FILE) as f:
        saved_data = json.load(f)
    assert saved_data == new_settings


def test_get_saved_settings(client):
    """Test getting settings from file."""
    # First save settings
    new_settings = {
        "api_endpoint": "http://example.com",
        "refresh_interval": 15,
        "enable_notifications": True,
        "enable_sounds": False,
        "max_log_lines": 2000,
    }
    client.put("/api/v1/settings", json=new_settings)
    
    # Now get them
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    
    assert data["api_endpoint"] == "http://example.com"
    assert data["refresh_interval"] == 15
    assert data["max_log_lines"] == 2000


def test_reset_settings(client):
    """Test resetting settings to defaults."""
    # First save custom settings
    client.put("/api/v1/settings", json={
        "api_endpoint": "http://custom.com",
        "refresh_interval": 20,
        "max_log_lines": 5000,
    })
    
    # Reset to defaults
    response = client.post("/api/v1/settings/reset")
    assert response.status_code == 200
    data = response.json()
    
    # Check default values
    assert data["api_endpoint"] == "http://localhost:9456"
    assert data["refresh_interval"] == 5
    assert data["max_log_lines"] == 500


def test_update_partial_settings(client):
    """Test updating only some settings."""
    # Update only refresh interval
    response = client.put("/api/v1/settings", json={
        "refresh_interval": 30,
    })
    assert response.status_code == 200
    data = response.json()
    
    # refresh_interval should be updated, others should be defaults
    assert data["refresh_interval"] == 30
    assert data["api_endpoint"] == "http://localhost:9456"  # default
    assert data["enable_notifications"] is True  # default


def test_invalid_refresh_interval(client):
    """Test validation of refresh interval."""
    # Too low
    response = client.put("/api/v1/settings", json={
        "refresh_interval": 0,
    })
    assert response.status_code == 422  # Validation error
    
    # Too high
    response = client.put("/api/v1/settings", json={
        "refresh_interval": 100,
    })
    assert response.status_code == 422  # Validation error
