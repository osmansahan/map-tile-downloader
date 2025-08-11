from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
from interfaces.tile_source import ITileSource


class BaseAdapter(ABC):
    """Base adapter class for all tile sources"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('name', 'unknown')
        self.source_type = config.get('type', 'unknown')
        self.tile_type = config.get('tile_type', 'raster')
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the adapter"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate adapter configuration"""
        pass
    
    def get_name(self) -> str:
        """Get adapter name"""
        return self.name
    
    def get_source_type(self) -> str:
        """Get source type"""
        return self.source_type
    
    def get_tile_type(self) -> str:
        """Get tile type"""
        return self.tile_type
    
    def get_config(self) -> Dict[str, Any]:
        """Get adapter configuration"""
        return self.config.copy()
