# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Test suite for CLI functionality.
"""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from mcp_compose import MCPServerInfo
from mcp_compose.cli import (
    compose_command,
    create_parser,
    discover_command,
    main,
    print_discovery_results,
    print_summary,
)


class TestCLI:
    """Test cases for CLI functionality."""

    def test_create_parser(self):
        """Test argument parser creation."""
        parser = create_parser()

        # Test help doesn't crash
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_parser_compose_command(self):
        """Test compose command parsing."""
        parser = create_parser()

        # Test basic compose command
        args = parser.parse_args(["compose"])
        assert args.command == "compose"
        assert args.name == "composed-mcp-server"
        assert args.conflict_resolution == "prefix"

    def test_parser_compose_command_with_options(self):
        """Test compose command with options."""
        parser = create_parser()

        args = parser.parse_args(
            [
                "compose",
                "--name",
                "my-server",
                "--conflict-resolution",
                "override",
                "--include",
                "server1",
                "server2",
                "--exclude",
                "server3",
                "--output",
                "output.json",
                "--output-format",
                "json",
            ]
        )

        assert args.command == "compose"
        assert args.name == "my-server"
        assert args.conflict_resolution == "override"
        assert args.include == ["server1", "server2"]
        assert args.exclude == ["server3"]
        assert args.output == "output.json"
        assert args.output_format == "json"

    def test_parser_discover_command(self):
        """Test discover command parsing."""
        parser = create_parser()

        args = parser.parse_args(["discover"])
        assert args.command == "discover"

    def test_parser_discover_command_with_options(self):
        """Test discover command with options."""
        parser = create_parser()

        args = parser.parse_args(
            [
                "discover",
                "--pyproject",
                "custom/pyproject.toml",
                "--output-format",
                "json",
            ]
        )

        assert args.command == "discover"
        assert args.pyproject == "custom/pyproject.toml"
        assert args.output_format == "json"

    @patch("mcp_compose.cli.MCPServerComposer")
    def test_compose_command_success(self, mock_composer_class):
        """Test successful compose command execution."""
        # Mock composer instance
        mock_composer = Mock()
        mock_composer.compose_from_pyproject.return_value = Mock()
        mock_composer.get_composition_summary.return_value = {
            "composed_server_name": "test-server",
            "conflict_resolution_strategy": "prefix",
            "total_tools": 5,
            "total_prompts": 2,
            "total_resources": 1,
            "source_servers": 2,
            "conflicts_resolved": 0,
            "conflict_details": [],
            "component_sources": {},
        }
        mock_composer_class.return_value = mock_composer

        # Create mock args
        args = Mock()
        args.name = "test-server"
        args.conflict_resolution = "prefix"
        args.pyproject = None
        args.include = None
        args.exclude = None
        args.output = None
        args.output_format = "text"

        result = compose_command(args)

        assert result == 0
        mock_composer.compose_from_pyproject.assert_called_once()

    @patch("mcp_compose.cli.MCPServerComposer")
    def test_compose_command_with_output(self, mock_composer_class):
        """Test compose command with output file."""
        mock_composer = Mock()
        mock_composer.compose_from_pyproject.return_value = Mock()
        mock_composer.get_composition_summary.return_value = {
            "composed_server_name": "test-server",
            "conflict_resolution_strategy": "prefix",
            "total_tools": 5,
            "total_prompts": 2,
            "total_resources": 1,
            "source_servers": 2,
            "conflicts_resolved": 0,
            "conflict_details": [],
            "component_sources": {},
        }
        mock_composer_class.return_value = mock_composer

        args = Mock()
        args.name = "test-server"
        args.conflict_resolution = "prefix"
        args.pyproject = None
        args.include = None
        args.exclude = None
        args.output_format = "text"

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            args.output = tmp_file.name

            result = compose_command(args)

            assert result == 0
            # Check that file was created
            assert Path(tmp_file.name).exists()

    @patch("mcp_compose.cli.MCPServerDiscovery")
    def test_discover_command_success(self, mock_discovery_class):
        """Test successful discover command execution."""
        # Mock discovery instance
        mock_discovery = Mock()
        mock_discovery.discover_from_pyproject.return_value = {
            "test-server": MCPServerInfo(
                package_name="test-server",
                version="1.0.0",
                tools={"tool1": Mock(), "tool2": Mock()},
                prompts={"prompt1": Mock()},
                resources={},
            )
        }
        mock_discovery_class.return_value = mock_discovery

        args = Mock()
        args.pyproject = None
        args.output_format = "text"

        result = discover_command(args)

        assert result == 0
        mock_discovery.discover_from_pyproject.assert_called_once()

    @patch("mcp_compose.cli.MCPServerDiscovery")
    def test_discover_command_json_output(self, mock_discovery_class):
        """Test discover command with JSON output."""
        mock_discovery = Mock()
        mock_discovery.discover_from_pyproject.return_value = {
            "test-server": MCPServerInfo(
                package_name="test-server",
                version="1.0.0",
                tools={"tool1": Mock(), "tool2": Mock()},
                prompts={"prompt1": Mock()},
                resources={},
            )
        }
        mock_discovery_class.return_value = mock_discovery

        args = Mock()
        args.pyproject = None
        args.output_format = "json"

        # Capture stdout
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = discover_command(args)
            output = mock_stdout.getvalue()

        assert result == 0
        # Should be valid JSON
        parsed = json.loads(output)
        assert "test-server" in parsed

    def test_print_summary(self):
        """Test summary printing."""
        summary = {
            "composed_server_name": "test-server",
            "conflict_resolution_strategy": "prefix",
            "total_tools": 5,
            "total_prompts": 2,
            "total_resources": 1,
            "source_servers": 2,
            "conflicts_resolved": 1,
            "conflict_details": [
                {
                    "type": "prefix",
                    "component_type": "tool",
                    "original_name": "test_tool",
                    "resolved_name": "server1_test_tool",
                    "server_name": "server1",
                }
            ],
        }

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_summary(summary)
            output = mock_stdout.getvalue()

        assert "test-server" in output
        assert "Tools: 5" in output
        assert "Conflicts Resolved: 1" in output

    def test_print_discovery_results_empty(self):
        """Test discovery results printing with no servers."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_discovery_results({})
            output = mock_stdout.getvalue()

        assert "No MCP servers discovered" in output

    def test_print_discovery_results_with_servers(self):
        """Test discovery results printing with servers."""
        discovered = {
            "test-server": MCPServerInfo(
                package_name="test-server",
                version="1.0.0",
                tools={"tool1": Mock(), "tool2": Mock()},
                prompts={"prompt1": Mock()},
                resources={},
            )
        }

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_discovery_results(discovered)
            output = mock_stdout.getvalue()

        assert "test-server" in output
        assert "Tools: 2" in output
        assert "Prompts: 1" in output

    @patch("mcp_compose.cli.create_parser")
    def test_main_no_command(self, mock_create_parser):
        """Test main function with no command."""
        mock_parser = Mock()
        mock_parser.parse_args.return_value = Mock(command=None, verbose=False)
        mock_create_parser.return_value = mock_parser

        result = main()

        assert result == 1
        mock_parser.print_help.assert_called_once()

    @patch("mcp_compose.cli.compose_command")
    @patch("mcp_compose.cli.create_parser")
    def test_main_compose_command(self, mock_create_parser, mock_compose):
        """Test main function with compose command."""
        mock_args = Mock(command="compose", verbose=False)
        mock_parser = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_compose.return_value = 0

        result = main()

        assert result == 0
        mock_compose.assert_called_once_with(mock_args)

    @patch("mcp_compose.cli.discover_command")
    @patch("mcp_compose.cli.create_parser")
    def test_main_discover_command(self, mock_create_parser, mock_discover):
        """Test main function with discover command."""
        mock_args = Mock(command="discover", verbose=False)
        mock_parser = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_discover.return_value = 0

        result = main()

        assert result == 0
        mock_discover.assert_called_once_with(mock_args)


if __name__ == "__main__":
    pytest.main([__file__])
