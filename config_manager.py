"""Configuration management for queuectl."""
import logging
from typing import Dict, Any
from storage import Storage

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages system configuration."""
    
    def __init__(self, storage: Storage):
        """Initialize config manager.
        
        Args:
            storage: Storage instance
        """
        self.storage = storage
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.storage.get_config()
    
    def get(self, key: str) -> Any:
        """Get a specific config value.
        
        Args:
            key: Configuration key
        
        Returns:
            Configuration value
        """
        config = self.get_config()
        return config.get(key)
    
    def set(self, key: str, value: Any):
        """Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        # Validate key and value
        if key == "max_retries":
            if not isinstance(value, int) or value < 0:
                raise ValueError("max_retries must be a non-negative integer")
        elif key == "backoff_base":
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValueError("backoff_base must be a positive number")
        elif key == "worker_count":
            if not isinstance(value, int) or value < 1:
                raise ValueError("worker_count must be a positive integer")
        else:
            raise ValueError(f"Unknown configuration key: {key}")
        
        self.storage.update_config({key: value})
        logger.info(f"Set {key} = {value}")
    
    def format_config(self) -> str:
        """Format configuration for display."""
        config = self.get_config()
        lines = []
        for key, value in sorted(config.items()):
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)



