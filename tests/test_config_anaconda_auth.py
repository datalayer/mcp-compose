# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Integration test for Anaconda authentication configuration.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from mcp_compose.config_loader import load_config_from_dict
from mcp_compose.config import AuthProvider
from mcp_compose.auth import create_authenticator, AuthType


def test_anaconda_auth_config_parsing():
    """Test parsing Anaconda authentication configuration from TOML."""
    config_dict = {
        "composer": {
            "name": "test-composer",
            "port": 8080,
        },
        "authentication": {
            "enabled": True,
            "providers": ["anaconda"],
            "default_provider": "anaconda",
            "anaconda": {
                "domain": "anaconda.com"
            }
        },
        "servers": {
            "proxied": {
                "stdio": []
            }
        }
    }
    
    config = load_config_from_dict(config_dict)
    
    # Verify authentication config
    assert config.authentication.enabled is True
    assert AuthProvider.ANACONDA in config.authentication.providers
    assert config.authentication.default_provider == AuthProvider.ANACONDA
    assert config.authentication.anaconda is not None
    assert config.authentication.anaconda.domain == "anaconda.com"


def test_anaconda_auth_config_custom_domain():
    """Test Anaconda configuration with custom domain."""
    config_dict = {
        "composer": {"name": "test"},
        "authentication": {
            "enabled": True,
            "providers": ["anaconda"],
            "default_provider": "anaconda",
            "anaconda": {
                "domain": "enterprise.anaconda.com"
            }
        },
        "servers": {"proxied": {"stdio": []}}
    }
    
    config = load_config_from_dict(config_dict)
    assert config.authentication.anaconda.domain == "enterprise.anaconda.com"


def test_anaconda_auth_config_validation_missing():
    """Test validation fails when Anaconda config is missing."""
    from mcp_compose.exceptions import MCPConfigurationError
    
    config_dict = {
        "composer": {"name": "test"},
        "authentication": {
            "enabled": True,
            "providers": ["anaconda"],
            "default_provider": "anaconda",
            # Missing anaconda config
        },
        "servers": {"proxied": {"stdio": []}}
    }
    
    with pytest.raises(MCPConfigurationError, match="Anaconda authentication enabled but anaconda config missing"):
        load_config_from_dict(config_dict)


def test_create_anaconda_authenticator_from_config():
    """Test creating Anaconda authenticator from configuration."""
    config_dict = {
        "composer": {"name": "test"},
        "authentication": {
            "enabled": True,
            "providers": ["anaconda"],
            "default_provider": "anaconda",
            "anaconda": {
                "domain": "test.anaconda.com"
            }
        },
        "servers": {"proxied": {"stdio": []}}
    }
    
    config = load_config_from_dict(config_dict)
    
    # Create authenticator from config
    with patch('anaconda_auth.token.TokenInfo'):
        auth = create_authenticator(
            AuthType.ANACONDA,
            domain=config.authentication.anaconda.domain
        )
        
        assert auth is not None
        assert auth.domain == "test.anaconda.com"
        assert auth.auth_type == AuthType.API_KEY  # Anaconda uses API_KEY type internally


def test_anaconda_auth_disabled():
    """Test configuration with authentication disabled."""
    config_dict = {
        "composer": {"name": "test"},
        "authentication": {
            "enabled": False,
        },
        "servers": {"proxied": {"stdio": []}}
    }
    
    config = load_config_from_dict(config_dict)
    assert config.authentication.enabled is False


def test_multiple_auth_providers_with_anaconda():
    """Test configuration with multiple authentication providers."""
    config_dict = {
        "composer": {"name": "test"},
        "authentication": {
            "enabled": True,
            "providers": ["api_key", "anaconda"],
            "default_provider": "anaconda",
            "api_key": {
                "header_name": "X-API-Key",
                "keys": ["test-key"]
            },
            "anaconda": {
                "domain": "anaconda.com"
            }
        },
        "servers": {"proxied": {"stdio": []}}
    }
    
    config = load_config_from_dict(config_dict)
    assert AuthProvider.API_KEY in config.authentication.providers
    assert AuthProvider.ANACONDA in config.authentication.providers
    assert config.authentication.default_provider == AuthProvider.ANACONDA


@pytest.mark.asyncio
async def test_anaconda_authenticator_integration():
    """Integration test for Anaconda authenticator with mocked anaconda-auth."""
    # Mock the TokenInfo class
    mock_token_info = MagicMock()
    mock_token_info.get_access_token.return_value = "mock_access_token"
    mock_token_info.username = "integration_test_user"
    
    with patch('anaconda_auth.token.TokenInfo', return_value=mock_token_info):
        # Create authenticator
        auth = create_authenticator(AuthType.ANACONDA, domain="test.com")
        
        # Authenticate
        context = await auth.authenticate({"token": "test_bearer_token"})
        
        # Verify context
        assert context.user_id == "integration_test_user"
        assert context.token == "test_bearer_token"
        assert context.metadata["domain"] == "test.com"
        assert context.metadata["access_token"] == "mock_access_token"
        
        # Validate context
        is_valid = await auth.validate(context)
        assert is_valid is True


def test_example_config_file():
    """Test that the example configuration file is valid."""
    # This test would read the actual mcp_compose.toml from the example
    example_path = Path(__file__).parent.parent / "examples" / "proxy-anaconda" / "mcp_compose.toml"
    
    if example_path.exists():
        from mcp_compose.config_loader import load_config
        
        config = load_config(example_path)
        
        # Verify the example has authentication enabled
        assert config.authentication.enabled is True
        assert config.authentication.default_provider == AuthProvider.ANACONDA
        assert config.authentication.anaconda is not None
        assert config.authentication.anaconda.domain == "anaconda.com"
