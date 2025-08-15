"""
Configuration management for new-printer.

Handles loading and managing configuration from YAML files with sensible defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Configuration manager for new-printer."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_file: Path to custom config file. If None, uses default locations.
        """
        self.config_data = self._load_default_config()
        
        # Load user config if available
        if config_file:
            self._load_config_file(config_file)
        else:
            self._load_user_config()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration values."""
        return {
            "default": {
                "columns": 2,
                "font_size": "11pt",
                "template": "article",
                "output_dir": "~/Downloads",
                "include_images": True,
                "timeout": 120
            },
            "templates": {
                "article": {
                    "description": "Clean article layout",
                    "margins": "2cm",
                    "fontfamily": "times"
                },
                "academic": {
                    "description": "Academic paper style",
                    "margins": "2.5cm",
                    "font_size": "12pt",
                    "fontfamily": "times"
                },
                "magazine": {
                    "description": "Magazine-style layout",
                    "columns": 3,
                    "margins": "1.5cm",
                    "fontfamily": "times"
                }
            },
            "extractors": {
                "primary": "trafilatura",
                "fallback": "readability",
                "timeout": 30,
                "user_agent": "new-printer/1.0.0"
            },
            "pandoc": {
                "pdf_engine": "xelatex",
                "standalone": True,
                "extract_media": True
            }
        }
    
    def _load_user_config(self) -> None:
        """Load user configuration from standard locations."""
        possible_paths = [
            Path.home() / ".new-printer.yml",
            Path.home() / ".new-printer.yaml",
            Path.home() / ".config" / "new-printer" / "config.yml",
            Path.home() / ".config" / "new-printer" / "config.yaml",
            Path("new-printer.yml"),
            Path("new-printer.yaml")
        ]
        
        for config_path in possible_paths:
            if config_path.exists():
                self._load_config_file(str(config_path))
                break
    
    def _load_config_file(self, config_file: str) -> None:
        """
        Load configuration from a YAML file.
        
        Args:
            config_file: Path to the configuration file.
        """
        try:
            config_path = Path(config_file).expanduser()
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        self._merge_config(user_config)
        except Exception as e:
            # Log warning but don't fail - use defaults
            print(f"Warning: Could not load config file {config_file}: {e}")
    
    def _merge_config(self, user_config: Dict[str, Any]) -> None:
        """
        Merge user configuration with defaults.
        
        Args:
            user_config: User configuration dictionary.
        """
        def deep_merge(default: Dict, user: Dict) -> Dict:
            """Recursively merge user config into default config."""
            result = default.copy()
            for key, value in user.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        self.config_data = deep_merge(self.config_data, user_config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'default.columns' or 'extractors.timeout')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config_data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'default.columns')
            value: Value to set
        """
        keys = key.split('.')
        config = self.config_data
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the final key
        config[keys[-1]] = value
    
    def get_template_config(self, template_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific template.
        
        Args:
            template_name: Name of the template
            
        Returns:
            Template configuration dictionary
        """
        templates = self.get('templates', {})
        return templates.get(template_name, {})
    
    def get_default_options(self) -> Dict[str, Any]:
        """
        Get default options for document conversion.
        
        Returns:
            Dictionary of default conversion options
        """
        return self.get('default', {})
    
    def get_extractor_config(self) -> Dict[str, Any]:
        """
        Get extractor configuration.
        
        Returns:
            Dictionary of extractor settings
        """
        return self.get('extractors', {})
    
    def get_pandoc_config(self) -> Dict[str, Any]:
        """
        Get Pandoc configuration.
        
        Returns:
            Dictionary of Pandoc settings
        """
        return self.get('pandoc', {})
    
    def expand_path(self, path: str) -> Path:
        """
        Expand a path, handling ~ and relative paths.
        
        Args:
            path: Path string to expand
            
        Returns:
            Expanded Path object
        """
        return Path(path).expanduser().resolve()


# Global configuration instance
_config = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config 