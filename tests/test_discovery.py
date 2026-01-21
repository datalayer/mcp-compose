# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Test suite for MCP Server Discovery.
"""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from mcp_compose.discovery import MCPServerDiscovery, MCPServerInfo
from mcp_compose.exceptions import MCPDiscoveryError, MCPImportError
from mcp_compose.config import EmbeddedServerConfig, MCPComposerConfig, ServersConfig, EmbeddedServersConfig


class TestMCPServerDiscovery:
    """Test cases for MCPServerDiscovery."""

    def test_init(self):
        """Test discovery initialization."""
        discovery = MCPServerDiscovery()
        assert discovery is not None

    def test_parse_pyproject_valid(self):
        """Test parsing valid pyproject.toml content."""
        toml_content = """
        [project]
        dependencies = [
            "jupyter-mcp-server>=1.0.0",
            "earthdata-mcp-server==0.1.0",
            "requests>=2.28.0",
        ]
        
        [project.optional-dependencies]
        dev = [
            "pytest>=7.0.0",
            "ruff>=0.1.0",
        ]
        """
        
        discovery = MCPServerDiscovery()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()
            
            dependencies = discovery._parse_pyproject_dependencies(f.name)
            
        assert "jupyter-mcp-server" in dependencies
        assert "earthdata-mcp-server" in dependencies
        assert "requests" in dependencies
        # Should include main dependencies and optional dev dependencies
        assert len(dependencies) == 5

    def test_parse_pyproject_no_dependencies(self):
        """Test parsing pyproject.toml without dependencies."""
        toml_content = """
        [project]
        name = "test-project"
        version = "1.0.0"
        """
        
        discovery = MCPServerDiscovery()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()
            
            dependencies = discovery._parse_pyproject_dependencies(f.name)
            
        assert len(dependencies) == 0

    def test_parse_pyproject_invalid_file(self):
        """Test parsing invalid pyproject.toml file."""
        discovery = MCPServerDiscovery()
        
        with pytest.raises(MCPDiscoveryError):
            discovery._parse_pyproject_dependencies("/nonexistent/file.toml")

    def test_is_mcp_server_package_true(self):
        """Test MCP server package detection for valid packages."""
        discovery = MCPServerDiscovery()
        
        # Test with known MCP server patterns
        assert discovery._is_mcp_server_package("jupyter-mcp-server")
        assert discovery._is_mcp_server_package("earthdata-mcp-server")
        assert discovery._is_mcp_server_package("some-mcp-server")
        assert discovery._is_mcp_server_package("mcp-server-example")

    def test_is_mcp_server_package_false(self):
        """Test MCP server package detection for non-MCP packages."""
        discovery = MCPServerDiscovery()
        
        # Test with non-MCP packages
        assert not discovery._is_mcp_server_package("requests")
        assert not discovery._is_mcp_server_package("numpy")
        assert not discovery._is_mcp_server_package("fastapi")
        assert not discovery._is_mcp_server_package("pytest")

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_analyze_mcp_server_success(self, mock_import):
        """Test successful MCP server analysis."""
        # Mock the imported module
        mock_server = Mock()
        mock_server._tool_manager._tools = {
            "test_tool": Mock(name="test_tool")
        }
        mock_server._prompt_manager._prompts = {
            "test_prompt": Mock(name="test_prompt")
        }
        mock_server._resource_manager._resources = {
            "test_resource": Mock(name="test_resource")
        }
        
        mock_module = Mock()
        mock_module.app = mock_server
        mock_import.return_value = mock_module
        
        discovery = MCPServerDiscovery()
        info = discovery._analyze_mcp_server("test_package", "1.0.0")
        
        assert info.package_name == "test_package"
        assert info.version == "1.0.0"
        assert "test_tool" in info.tools
        assert "test_prompt" in info.prompts
        assert "test_resource" in info.resources

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_analyze_mcp_server_import_error(self, mock_import):
        """Test MCP server analysis with import error."""
        mock_import.side_effect = ImportError("Module not found")
        
        discovery = MCPServerDiscovery()
        
        with pytest.raises(MCPImportError):
            discovery._analyze_mcp_server("nonexistent_package", "1.0.0")

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_analyze_mcp_server_no_app(self, mock_import):
        """Test MCP server analysis when module has no app attribute."""
        # Create a module-like object that doesn't have any server names
        mock_module = type('MockModule', (), {})()
        mock_import.return_value = mock_module
        
        discovery = MCPServerDiscovery()
        
        with pytest.raises(MCPImportError):
            discovery._analyze_mcp_server("test_package", "1.0.0")

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_analyze_mcp_server_missing_managers(self, mock_import):
        """Test MCP server analysis with missing managers."""
        mock_server = Mock()
        # Don't set the manager attributes
        mock_server._tool_manager = None
        mock_server._prompt_manager = None
        mock_server._resource_manager = None
        
        mock_module = Mock()
        mock_module.app = mock_server
        mock_import.return_value = mock_module
        
        discovery = MCPServerDiscovery()
        info = discovery._analyze_mcp_server("test_package", "1.0.0")
        
        # Should still work with empty collections
        assert info.package_name == "test_package"
        assert info.tools == {}
        assert info.prompts == {}
        assert info.resources == {}

    def test_discover_from_pyproject_integration(self):
        """Test full discovery integration."""
        toml_content = """
        [project]
        dependencies = [
            "requests>=2.28.0",
            "non-mcp-package>=1.0.0",
        ]
        """
        
        discovery = MCPServerDiscovery()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()
            
            # Should not find any MCP servers
            discovered = discovery.discover_from_pyproject(f.name)
            
        assert len(discovered) == 0

    @patch('mcp_compose.discovery.MCPServerDiscovery._analyze_mcp_server')
    @patch('mcp_compose.discovery.MCPServerDiscovery._is_mcp_server_package')
    def test_discover_from_pyproject_with_mcp_servers(self, mock_is_mcp, mock_analyze):
        """Test discovery with actual MCP servers."""
        toml_content = """
        [project]
        dependencies = [
            "jupyter-mcp-server>=1.0.0",
            "requests>=2.28.0",
        ]
        """
        
        # Mock MCP server detection
        mock_is_mcp.side_effect = lambda pkg: pkg == "jupyter-mcp-server"
        
        # Mock server analysis
        mock_info = MCPServerInfo(
            package_name="jupyter-mcp-server",
            version="1.0.0",
            tools={"test_tool": Mock()},
        )
        mock_analyze.return_value = mock_info
        
        discovery = MCPServerDiscovery()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()
            
            discovered = discovery.discover_from_pyproject(f.name)
            
        assert len(discovered) == 1
        assert "jupyter-mcp-server" in discovered
        assert discovered["jupyter-mcp-server"].package_name == "jupyter-mcp-server"

    def test_get_package_version_basic(self):
        """Test basic package version extraction."""
        discovery = MCPServerDiscovery()
        
        # Test simple version specifications
        assert discovery._get_package_version("package>=1.0.0") == ">=1.0.0"
        assert discovery._get_package_version("package==2.1.0") == "==2.1.0"
        assert discovery._get_package_version("package~=1.5") == "~=1.5"
        assert discovery._get_package_version("package") == "latest"

    def test_get_package_version_complex(self):
        """Test complex package version extraction."""
        discovery = MCPServerDiscovery()
        
        # Test complex version specifications
        assert discovery._get_package_version("package>=1.0,<2.0") == ">=1.0,<2.0"
        assert discovery._get_package_version("package[extra]>=1.0.0") == ">=1.0.0"
        assert discovery._get_package_version("package ; python_version >= '3.8'") == "latest"


class TestMCPServerInfo:
    """Test cases for MCPServerInfo."""

    def test_creation_minimal(self):
        """Test MCPServerInfo creation with minimal parameters."""
        info = MCPServerInfo(
            package_name="test-package",
            version="1.0.0"
        )
        
        assert info.package_name == "test-package"
        assert info.version == "1.0.0"
        assert info.tools == {}
        assert info.prompts == {}
        assert info.resources == {}

    def test_creation_full(self):
        """Test MCPServerInfo creation with all parameters."""
        tools = {"tool1": Mock(), "tool2": Mock()}
        prompts = {"prompt1": Mock()}
        resources = {"resource1": Mock(), "resource2": Mock()}
        
        info = MCPServerInfo(
            package_name="full-package",
            version="2.0.0",
            tools=tools,
            prompts=prompts,
            resources=resources,
        )
        
        assert info.package_name == "full-package"
        assert info.version == "2.0.0"
        assert info.tools is tools
        assert info.prompts is prompts
        assert info.resources is resources

    def test_string_representation(self):
        """Test string representation of MCPServerInfo."""
        info = MCPServerInfo(
            package_name="test-package",
            version="1.0.0",
            tools={"tool1": Mock()},
            prompts={"prompt1": Mock()},
        )
        
        str_repr = str(info)
        assert "test-package" in str_repr
        assert "1.0.0" in str_repr


class TestConfigBasedDiscovery:
    """Test cases for config-based discovery."""

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_discover_from_config_with_single_server(self, mock_import):
        """Test discovering servers from configuration with single server."""
        # Mock the imported module
        mock_module = Mock()
        mock_server = Mock()
        mock_module.mcp = mock_server
        mock_import.return_value = mock_module
        
        # Create server config
        server_configs = [
            EmbeddedServerConfig(
                name="test-server",
                package="test_mcp_server",
                enabled=True
            )
        ]
        
        discovery = MCPServerDiscovery()
        servers = discovery.discover_from_config(server_configs)
        
        assert "test-server" in servers
        assert len(servers) == 1
        mock_import.assert_called_once_with("test_mcp_server")

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_discover_from_config_with_full_config(self, mock_import):
        """Test discovering servers from full MCPComposerConfig."""
        # Mock the imported module
        mock_module = Mock()
        mock_server = Mock()
        mock_module.mcp = mock_server
        mock_import.return_value = mock_module
        
        # Create full config
        config = MCPComposerConfig(
            servers=ServersConfig(
                embedded=EmbeddedServersConfig(
                    servers=[
                        EmbeddedServerConfig(
                            name="server1",
                            package="package1",
                            enabled=True
                        ),
                        EmbeddedServerConfig(
                            name="server2",
                            package="package2",
                            enabled=True
                        )
                    ]
                )
            )
        )
        
        discovery = MCPServerDiscovery()
        servers = discovery.discover_from_config(config)
        
        assert "server1" in servers
        assert "server2" in servers
        assert len(servers) == 2

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_discover_from_config_skip_disabled(self, mock_import):
        """Test that disabled servers are skipped."""
        # Mock the imported module
        mock_module = Mock()
        mock_server = Mock()
        mock_module.mcp = mock_server
        mock_import.return_value = mock_module
        
        # Create server config with disabled server
        server_configs = [
            EmbeddedServerConfig(
                name="enabled-server",
                package="enabled_package",
                enabled=True
            ),
            EmbeddedServerConfig(
                name="disabled-server",
                package="disabled_package",
                enabled=False
            )
        ]
        
        discovery = MCPServerDiscovery()
        servers = discovery.discover_from_config(server_configs)
        
        assert "enabled-server" in servers
        assert "disabled-server" not in servers
        assert len(servers) == 1
        mock_import.assert_called_once()  # Only called for enabled server

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_discover_from_config_with_version(self, mock_import):
        """Test discovering server with version constraint."""
        # Mock the imported module
        mock_module = Mock()
        mock_server = Mock()
        mock_module.mcp = mock_server
        mock_import.return_value = mock_module
        
        # Create server config with version
        server_configs = [
            EmbeddedServerConfig(
                name="versioned-server",
                package="versioned_package",
                version=">=1.0.0",
                enabled=True
            )
        ]
        
        discovery = MCPServerDiscovery()
        servers = discovery.discover_from_config(server_configs)
        
        assert "versioned-server" in servers
        assert len(servers) == 1

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_discover_from_config_import_error(self, mock_import):
        """Test error handling when import fails."""
        # Mock import to raise error
        mock_import.side_effect = ImportError("Module not found")
        
        server_configs = [
            EmbeddedServerConfig(
                name="failing-server",
                package="nonexistent_package",
                enabled=True
            )
        ]
        
        discovery = MCPServerDiscovery()
        with pytest.raises(MCPDiscoveryError):
            discovery.discover_from_config(server_configs)

    @patch('mcp_compose.discovery.importlib.import_module')
    def test_discover_from_config_custom_name(self, mock_import):
        """Test that custom server name is used instead of package name."""
        # Mock the imported module
        mock_module = Mock()
        mock_server = Mock()
        mock_module.mcp = mock_server
        mock_import.return_value = mock_module
        
        # Create server config with custom name
        server_configs = [
            EmbeddedServerConfig(
                name="my-custom-name",
                package="actual_package_name",
                enabled=True
            )
        ]
        
        discovery = MCPServerDiscovery()
        servers = discovery.discover_from_config(server_configs)
        
        # Should use the custom name, not package name
        assert "my-custom-name" in servers
        assert "actual_package_name" not in servers


if __name__ == "__main__":
    pytest.main([__file__])
