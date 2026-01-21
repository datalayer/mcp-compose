# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for configuration loading and validation.
"""

import os
import tempfile
from pathlib import Path

import pytest

from mcp_compose.config import (
    ApiConfig,
    AuthenticationConfig,
    AuthorizationConfig,
    AuthProvider,
    ComposerConfig,
    ConflictResolutionStrategy,
    EmbeddedServerConfig,
    EmbeddedServersConfig,
    HealthCheckMethod,
    MCPComposerConfig,
    MonitoringConfig,
    ProxyMode,
    RestartPolicy,
    ServersConfig,
    SseProxiedServerConfig,
    StdioProxiedServerConfig,
    ToolManagerConfig,
    TransportConfig,
    UiConfig,
)
from mcp_compose.config_loader import (
    find_config_file,
    load_config,
    load_config_from_dict,
    validate_config_file,
)
from mcp_compose.exceptions import MCPConfigurationError


class TestConfigModels:
    """Test configuration model classes."""

    def test_composer_config_defaults(self):
        """Test ComposerConfig default values."""
        config = ComposerConfig()
        assert config.name == "composed-mcp-server"
        assert config.conflict_resolution == ConflictResolutionStrategy.PREFIX
        assert config.log_level == "INFO"
        assert config.port == 8080

    def test_transport_config_defaults(self):
        """Test TransportConfig default values."""
        config = TransportConfig()
        assert config.stdio_enabled is True
        assert config.sse_enabled is True
        assert config.sse_path == "/sse"
        assert config.sse_cors_enabled is True

    def test_embedded_server_config(self):
        """Test EmbeddedServerConfig validation."""
        config = EmbeddedServerConfig(
            name="test-server",
            package="test_package",
            enabled=True,
            version=">=1.0.0"
        )
        assert config.name == "test-server"
        assert config.package == "test_package"
        assert config.enabled is True
        assert config.version == ">=1.0.0"

    def test_stdio_proxied_server_config(self):
        """Test StdioProxiedServerConfig validation."""
        config = StdioProxiedServerConfig(
            name="weather-server",
            command=["uvx", "mcp-server-weather"],
            env={"API_KEY": "test123"},
            restart_policy=RestartPolicy.ON_FAILURE,
            health_check_enabled=True,
            health_check_method=HealthCheckMethod.TOOL,
            health_check_tool="health"
        )
        assert config.name == "weather-server"
        assert config.command == ["uvx", "mcp-server-weather"]
        assert config.env == {"API_KEY": "test123"}
        assert config.restart_policy == RestartPolicy.ON_FAILURE
        assert config.health_check_enabled is True
        assert config.health_check_tool == "health"

    def test_sse_proxied_server_config(self):
        """Test SseProxiedServerConfig validation."""
        config = SseProxiedServerConfig(
            name="remote-server",
            url="https://example.com/mcp/sse",
            auth_token="secret123",
            mode=ProxyMode.PROXY
        )
        assert config.name == "remote-server"
        assert config.url == "https://example.com/mcp/sse"
        assert config.auth_token == "secret123"
        assert config.mode == ProxyMode.PROXY

    def test_authentication_config_validation_success(self):
        """Test authentication config with proper provider config."""
        config = MCPComposerConfig(
            authentication=AuthenticationConfig(
                enabled=True,
                providers=[AuthProvider.API_KEY],
                api_key={"header_name": "X-API-Key", "keys": ["key1", "key2"]}
            )
        )
        assert config.authentication.enabled is True
        assert config.authentication.api_key.keys == ["key1", "key2"]

    def test_authentication_config_validation_failure(self):
        """Test authentication config validation fails without provider config."""
        with pytest.raises(ValueError, match="API Key authentication enabled"):
            MCPComposerConfig(
                authentication=AuthenticationConfig(
                    enabled=True,
                    providers=[AuthProvider.API_KEY],
                    api_key=None
                )
            )

    def test_health_check_validation_failure(self):
        """Test health check validation fails when tool method without tool name."""
        with pytest.raises(ValueError, match="health_check_method is 'tool'"):
            MCPComposerConfig(
                servers=ServersConfig(
                    proxied={
                        "stdio": [
                            StdioProxiedServerConfig(
                                name="test-server",
                                command=["test"],
                                health_check_enabled=True,
                                health_check_method=HealthCheckMethod.TOOL,
                                health_check_tool=None
                            )
                        ]
                    }
                )
            )

    def test_tool_manager_config(self):
        """Test ToolManagerConfig."""
        config = ToolManagerConfig(
            conflict_resolution=ConflictResolutionStrategy.CUSTOM,
            aliases={"old_name": "new_name"}
        )
        assert config.conflict_resolution == ConflictResolutionStrategy.CUSTOM
        assert config.aliases == {"old_name": "new_name"}


class TestConfigLoader:
    """Test configuration loading functionality."""

    def test_load_config_from_file(self):
        """Test loading config from a TOML file."""
        config_content = """
[composer]
name = "test-server"
conflict_resolution = "prefix"
log_level = "DEBUG"
port = 9090

[transport]
stdio_enabled = true
sse_enabled = false

[[servers.embedded.servers]]
name = "test-embedded"
package = "test_package"
enabled = true
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.composer.name == "test-server"
            assert config.composer.log_level == "DEBUG"
            assert config.composer.port == 9090
            assert config.transport.stdio_enabled is True
            assert config.transport.sse_enabled is False
            assert len(config.servers.embedded.servers) == 1
            assert config.servers.embedded.servers[0].name == "test-embedded"
        finally:
            os.unlink(config_path)

    def test_load_config_file_not_found(self):
        """Test loading config from non-existent file."""
        with pytest.raises(MCPConfigurationError, match="Configuration file not found"):
            load_config("/nonexistent/path/config.toml")

    def test_load_config_invalid_toml(self):
        """Test loading config from invalid TOML file."""
        config_content = """
[composer
name = "test-server"  # Missing closing bracket
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            with pytest.raises(MCPConfigurationError, match="Failed to parse TOML"):
                load_config(config_path)
        finally:
            os.unlink(config_path)

    def test_load_config_invalid_schema(self):
        """Test loading config with invalid schema."""
        config_content = """
[composer]
name = "test-server"
port = "not_a_number"  # Should be integer
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            with pytest.raises(MCPConfigurationError, match="Invalid configuration"):
                load_config(config_path)
        finally:
            os.unlink(config_path)

    def test_load_config_from_dict(self):
        """Test loading config from dictionary."""
        config_dict = {
            "composer": {
                "name": "test-server",
                "port": 8080
            },
            "transport": {
                "stdio_enabled": True,
                "sse_enabled": True
            }
        }
        config = load_config_from_dict(config_dict)
        assert config.composer.name == "test-server"
        assert config.composer.port == 8080
        assert config.transport.stdio_enabled is True

    def test_env_var_substitution(self):
        """Test environment variable substitution."""
        # Set test environment variables
        os.environ['TEST_SERVER_NAME'] = 'env-test-server'
        os.environ['TEST_API_KEY'] = 'secret123'
        
        config_content = """
[composer]
name = "${TEST_SERVER_NAME}"
port = 8080

[authentication]
enabled = true
providers = ["api_key"]

[authentication.api_key]
header_name = "X-API-Key"
keys = ["${TEST_API_KEY}"]
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            config = load_config(config_path)
            # Note: Environment variable substitution happens in the loader
            # The config will have the raw values initially
            assert config.composer.name == "env-test-server"
            assert config.authentication.api_key.keys[0] == "secret123"
        finally:
            os.unlink(config_path)
            del os.environ['TEST_SERVER_NAME']
            del os.environ['TEST_API_KEY']

    def test_env_var_not_found(self):
        """Test environment variable substitution when var not found."""
        config_content = """
[composer]
name = "${NONEXISTENT_VAR}"
port = 8080
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            config = load_config(config_path)
            # Should keep original if not found
            assert config.composer.name == "${NONEXISTENT_VAR}"
        finally:
            os.unlink(config_path)

    def test_find_config_file_in_current_dir(self):
        """Test finding config file in current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "mcp_compose.toml"
            config_path.write_text("[composer]\nname = 'test'")
            
            found_path = find_config_file(start_dir=tmpdir)
            assert found_path == config_path

    def test_find_config_file_in_parent_dir(self):
        """Test finding config file in parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "mcp_compose.toml"
            config_path.write_text("[composer]\nname = 'test'")
            
            # Create subdirectory
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            
            found_path = find_config_file(start_dir=subdir)
            assert found_path == config_path

    def test_find_config_file_not_found(self):
        """Test finding config file when it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            found_path = find_config_file(start_dir=tmpdir)
            assert found_path is None

    def test_validate_config_file_valid(self):
        """Test validating a valid config file."""
        config_content = """
[composer]
name = "test-server"
port = 8080
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            is_valid, error = validate_config_file(config_path)
            assert is_valid is True
            assert error is None
        finally:
            os.unlink(config_path)

    def test_validate_config_file_invalid(self):
        """Test validating an invalid config file."""
        config_content = """
[composer]
port = "not_a_number"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            is_valid, error = validate_config_file(config_path)
            assert is_valid is False
            assert error is not None
            assert "Invalid configuration" in error
        finally:
            os.unlink(config_path)


class TestComplexConfigurations:
    """Test complex configuration scenarios."""

    def test_full_config_with_all_sections(self):
        """Test loading a config with all sections populated."""
        config_dict = {
            "composer": {
                "name": "full-server",
                "conflict_resolution": "custom",
                "log_level": "DEBUG",
                "port": 9000
            },
            "transport": {
                "stdio_enabled": True,
                "sse_enabled": True,
                "sse_path": "/stream",
                "sse_cors_enabled": True
            },
            "authentication": {
                "enabled": True,
                "providers": ["api_key", "jwt"],
                "default_provider": "api_key",
                "api_key": {
                    "header_name": "X-API-Key",
                    "keys": ["key1", "key2"]
                },
                "jwt": {
                    "secret": "jwt_secret",
                    "algorithm": "HS256",
                    "issuer": "test-issuer"
                }
            },
            "authorization": {
                "enabled": True,
                "model": "rbac",
                "roles": [
                    {"name": "admin", "permissions": ["*"]},
                    {"name": "user", "permissions": ["tools:execute"]}
                ],
                "rate_limiting": {
                    "enabled": True,
                    "default_limit": 100,
                    "per_role_limits": {"admin": 1000, "user": 50}
                }
            },
            "servers": {
                "embedded": {
                    "servers": [
                        {
                            "name": "jupyter-server",
                            "package": "jupyter_mcp",
                            "enabled": True
                        }
                    ]
                },
                "proxied": {
                    "stdio": [
                        {
                            "name": "weather-server",
                            "command": ["python", "weather.py"],
                            "restart_policy": "always",
                            "health_check_enabled": True,
                            "health_check_method": "ping"
                        }
                    ],
                    "sse": [
                        {
                            "name": "remote-server",
                            "url": "https://example.com/sse",
                            "mode": "proxy"
                        }
                    ]
                }
            },
            "tool_manager": {
                "conflict_resolution": "prefix",
                "aliases": {"old_tool": "new_tool"},
                "versioning": {
                    "enabled": True,
                    "allow_multiple_versions": True
                }
            },
            "api": {
                "enabled": True,
                "path_prefix": "/api/v2",
                "cors_enabled": True,
                "cors_origins": ["http://localhost:3000"]
            },
            "ui": {
                "enabled": True,
                "framework": "react",
                "mode": "embedded"
            },
            "monitoring": {
                "enabled": True,
                "metrics": {
                    "enabled": True,
                    "provider": "prometheus"
                },
                "logging": {
                    "level": "INFO",
                    "format": "json"
                },
                "tracing": {
                    "enabled": False
                }
            }
        }
        
        config = load_config_from_dict(config_dict)
        
        # Verify all sections loaded correctly
        assert config.composer.name == "full-server"
        assert config.transport.sse_path == "/stream"
        assert config.authentication.enabled is True
        assert len(config.authentication.providers) == 2
        assert config.authorization.enabled is True
        assert len(config.authorization.roles) == 2
        assert len(config.servers.embedded.servers) == 1
        assert len(config.servers.proxied.stdio) == 1
        assert len(config.servers.proxied.sse) == 1
        assert config.tool_manager.aliases == {"old_tool": "new_tool"}
        assert config.api.path_prefix == "/api/v2"
        assert config.ui.framework == "react"
        assert config.monitoring.enabled is True

    def test_minimal_config(self):
        """Test loading a minimal config with defaults."""
        config_dict = {
            "composer": {
                "name": "minimal-server"
            }
        }
        
        config = load_config_from_dict(config_dict)
        
        # Verify defaults are applied
        assert config.composer.name == "minimal-server"
        assert config.composer.port == 8080  # Default
        assert config.transport.stdio_enabled is True  # Default
        assert config.authentication.enabled is False  # Default
        assert len(config.servers.embedded.servers) == 0  # Empty
        assert config.api.enabled is True  # Default
