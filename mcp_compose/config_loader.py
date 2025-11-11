"""
Configuration loader for MCP Compose.

This module handles loading and parsing TOML configuration files.
"""

import sys
from pathlib import Path
from typing import Dict, Optional, Union

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError(
            "tomli package is required for Python < 3.11. "
            "Install it with: pip install tomli"
        )

from .config import MCPComposerConfig
from .exceptions import MCPConfigurationError


def load_config(config_path: Union[str, Path]) -> MCPComposerConfig:
    """
    Load configuration from a TOML file.
    
    Args:
        config_path: Path to the configuration file.
        
    Returns:
        Parsed and validated configuration.
        
    Raises:
        MCPConfigurationError: If configuration file cannot be loaded or is invalid.
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise MCPConfigurationError(
            f"Configuration file not found: {config_path}",
            config_path=str(config_path)
        )
    
    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
    except Exception as e:
        raise MCPConfigurationError(
            f"Failed to parse TOML configuration: {e}",
            config_path=str(config_path)
        ) from e
    
    try:
        config = MCPComposerConfig.model_validate(config_data)
    except Exception as e:
        raise MCPConfigurationError(
            f"Invalid configuration: {e}",
            config_path=str(config_path)
        ) from e
    
    # Substitute environment variables
    config = _substitute_env_vars_in_config(config)
    
    return config


def load_config_from_dict(config_data: Dict) -> MCPComposerConfig:
    """
    Load configuration from a dictionary.
    
    Args:
        config_data: Configuration dictionary.
        
    Returns:
        Parsed and validated configuration.
        
    Raises:
        MCPConfigurationError: If configuration is invalid.
    """
    try:
        config = MCPComposerConfig.model_validate(config_data)
    except Exception as e:
        raise MCPConfigurationError(f"Invalid configuration: {e}") from e
    
    # Substitute environment variables
    config = _substitute_env_vars_in_config(config)
    
    return config


def find_config_file(
    start_dir: Optional[Union[str, Path]] = None,
    filename: str = "mcp_compose.toml"
) -> Optional[Path]:
    """
    Search for configuration file in current directory and parent directories.
    
    Args:
        start_dir: Directory to start searching from. Defaults to current directory.
        filename: Configuration filename to search for.
        
    Returns:
        Path to configuration file if found, None otherwise.
    """
    if start_dir is None:
        start_dir = Path.cwd()
    else:
        start_dir = Path(start_dir)
    
    current = start_dir.resolve()
    
    # Search up to root directory
    while True:
        config_path = current / filename
        if config_path.exists():
            return config_path
        
        parent = current.parent
        if parent == current:
            # Reached root directory
            break
        current = parent
    
    return None


def _substitute_env_vars_in_config(config: MCPComposerConfig) -> MCPComposerConfig:
    """
    Substitute environment variables in configuration.
    
    Args:
        config: Configuration object.
        
    Returns:
        Configuration with substituted environment variables.
    """
    import os
    import re
    
    def substitute_in_dict(obj):
        """Recursively substitute environment variables in dict/list/str."""
        if isinstance(obj, dict):
            return {k: substitute_in_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [substitute_in_dict(item) for item in obj]
        elif isinstance(obj, str):
            # Match ${VAR_NAME} or $VAR_NAME patterns
            pattern = r'\$\{([^}]+)\}|\$([A-Z_][A-Z0-9_]*)'
            
            def replace_match(match: re.Match) -> str:
                var_name = match.group(1) or match.group(2)
                env_value = os.environ.get(var_name)
                if env_value is None:
                    # Keep original if not found
                    return match.group(0)
                return env_value
            
            return re.sub(pattern, replace_match, obj)
        else:
            return obj
    
    # Convert to dict, substitute, and rebuild
    config_dict = config.model_dump()
    substituted_dict = substitute_in_dict(config_dict)
    
    try:
        return MCPComposerConfig.model_validate(substituted_dict)
    except Exception as e:
        raise MCPConfigurationError(
            f"Failed to rebuild configuration after environment variable substitution: {e}"
        ) from e


def validate_config_file(config_path: Union[str, Path]) -> tuple[bool, Optional[str]]:
    """
    Validate a configuration file without loading it.
    
    Args:
        config_path: Path to the configuration file.
        
    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    try:
        load_config(config_path)
        return (True, None)
    except MCPConfigurationError as e:
        return (False, str(e))
    except Exception as e:
        return (False, f"Unexpected error: {e}")
