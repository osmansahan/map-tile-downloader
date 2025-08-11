"""Logging configuration"""
import logging
import sys
from typing import Dict, Any


class LoggingManager:
    """Manages application logging configuration"""
    
    @staticmethod
    def setup_logging(config: Dict[str, Any]) -> None:
        """Setup logging based on configuration"""
        logging_config = config.get('logging', {})
        
        level = getattr(logging, logging_config.get('level', 'INFO'))
        format_str = logging_config.get('format', 
                                       '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        logging.basicConfig(
            level=level,
            format=format_str,
            stream=sys.stdout
        )
        
        # Set specific loggers
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
