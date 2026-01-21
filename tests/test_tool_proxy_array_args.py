"""
Tests for array argument handling in tool proxy.

These tests verify that array-based arguments are correctly passed to downstream
servers when using STDIO transport, rather than being converted to space-separated
strings.
"""

import pytest
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

from mcp_compose.tool_proxy import fix_tool_argument_model


class MockFnMetadata:
    """Mock function metadata for testing."""
    def __init__(self):
        self.arg_model = None


class MockTool:
    """Mock Tool object for testing."""
    def __init__(self, name: str):
        self.name = name
        self.fn_metadata = MockFnMetadata()
        self.parameters = {}


class TestFixToolArgumentModel:
    """Test cases for fix_tool_argument_model function."""

    def test_fix_array_of_strings(self):
        """Test that array of strings is correctly typed."""
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of packages to install"
                }
            },
            "required": ["packages"]
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        # Verify the arg_model was created
        assert tool.fn_metadata.arg_model is not None
        
        # Verify the model accepts a list of strings
        model_instance = tool.fn_metadata.arg_model(packages=["faker", "flask"])
        assert model_instance.packages == ["faker", "flask"]
        
        # Verify the model schema has correct type
        schema = tool.fn_metadata.arg_model.model_json_schema()
        assert schema["properties"]["packages"]["type"] == "array"
        assert schema["properties"]["packages"]["items"]["type"] == "string"

    def test_fix_array_of_integers(self):
        """Test that array of integers is correctly typed."""
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {
                "numbers": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of numbers"
                }
            },
            "required": ["numbers"]
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        model_instance = tool.fn_metadata.arg_model(numbers=[1, 2, 3])
        assert model_instance.numbers == [1, 2, 3]

    def test_fix_array_of_objects(self):
        """Test that array of objects is correctly typed."""
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of objects"
                }
            },
            "required": ["items"]
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        model_instance = tool.fn_metadata.arg_model(items=[{"key": "value"}])
        assert model_instance.items == [{"key": "value"}]

    def test_fix_optional_array(self):
        """Test that optional array is correctly typed."""
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of packages"
                }
            },
            "required": []  # Not required
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        # Should have a default value of None for optional fields
        # When not provided, it defaults to None
        model_instance = tool.fn_metadata.arg_model()
        assert model_instance.packages is None
        
        # Should also accept list
        model_instance = tool.fn_metadata.arg_model(packages=["faker"])
        assert model_instance.packages == ["faker"]

    def test_fix_anyof_array_or_null(self):
        """Test that anyOf array|null is correctly typed."""
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {
                "packages": {
                    "anyOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "null"}
                    ],
                    "description": "Optional list of packages"
                }
            },
            "required": []
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        # Should accept None
        model_instance = tool.fn_metadata.arg_model(packages=None)
        assert model_instance.packages is None
        
        # Should also accept list
        model_instance = tool.fn_metadata.arg_model(packages=["faker", "flask"])
        assert model_instance.packages == ["faker", "flask"]

    def test_fix_mixed_types(self):
        """Test schema with multiple field types."""
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "packages": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "options": {"type": "object"},
                "enabled": {"type": "boolean"}
            },
            "required": ["name", "packages"]
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        model_instance = tool.fn_metadata.arg_model(
            name="test",
            count=5,
            packages=["a", "b"],
            options={"key": "value"},
            enabled=True
        )
        assert model_instance.name == "test"
        assert model_instance.count == 5
        assert model_instance.packages == ["a", "b"]
        assert model_instance.options == {"key": "value"}
        assert model_instance.enabled is True

    def test_fix_empty_schema(self):
        """Test that empty schema doesn't cause errors."""
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Should not raise an error
        fix_tool_argument_model(tool, input_schema)
        
        # arg_model should be created (even if empty)
        assert tool.fn_metadata.arg_model is not None

    def test_array_not_converted_to_string(self):
        """
        Critical test: Verify arrays are NOT converted to space-separated strings.
        
        This is the main issue reported: packages=['faker', 'flask'] was being
        converted to packages='faker flask'.
        """
        tool = MockTool("install_packages")
        input_schema = {
            "type": "object",
            "properties": {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of package names to install"
                }
            },
            "required": ["packages"]
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        # Create instance with list
        model_instance = tool.fn_metadata.arg_model(packages=["faker", "flask"])
        
        # Verify it's still a list, NOT a string
        assert isinstance(model_instance.packages, list), \
            f"Expected list, got {type(model_instance.packages)}: {model_instance.packages}"
        assert model_instance.packages == ["faker", "flask"]
        assert model_instance.packages != "faker flask"  # This was the bug


class TestArrayArgumentSerialization:
    """Test that array arguments are properly serialized for JSON-RPC."""

    def test_list_serializable_to_json(self):
        """Test that the model's dict output is JSON-serializable with arrays."""
        import json
        
        tool = MockTool("test_tool")
        input_schema = {
            "type": "object",
            "properties": {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["packages"]
        }
        
        fix_tool_argument_model(tool, input_schema)
        
        model_instance = tool.fn_metadata.arg_model(packages=["faker", "flask"])
        
        # Convert to dict (as would happen in tool call)
        data = model_instance.model_dump()
        
        # Should be JSON serializable
        json_str = json.dumps(data)
        
        # Should deserialize back to list
        parsed = json.loads(json_str)
        assert parsed["packages"] == ["faker", "flask"]
