from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional, Union
import os


class ITileSource(ABC):
    """Unified interface for all tile sources (HTTP, Local MBTiles, etc.)"""
    
    @abstractmethod
    def get_name(self) -> str:
        """Get source name"""
        pass
    
    @abstractmethod
    def get_source_type(self) -> str:
        """Get source type (http, local, etc.)"""
        pass
    
    @abstractmethod
    def get_tile_type(self) -> str:
        """Get tile type (raster/vector)"""
        pass
    
    @abstractmethod
    def get_tile(self, zoom: int, x: int, y: int) -> Optional[bytes]:
        """Get tile data for given coordinates"""
        pass
    
    @abstractmethod
    def validate_bounds(self, bbox: List[float]) -> bool:
        """Validate if bbox is within source bounds"""
        pass
    
    @abstractmethod
    def get_bounds(self) -> List[float]:
        """Get source bounds [min_lon, min_lat, max_lon, max_lat]"""
        pass
    
    @abstractmethod
    def get_zoom_range(self) -> Tuple[int, int]:
        """Get available zoom range (min_zoom, max_zoom)"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if source is available/accessible"""
        pass


class ITileExtractor(ABC):
    """Interface for tile extraction from local sources"""
    
    @abstractmethod
    def extract_tiles(self, bbox: List[float], zoom: int) -> List[Tuple[int, int, bytes]]:
        """Extract tiles for given bbox and zoom level"""
        pass
    
    @abstractmethod
    def get_tile_count(self, bbox: List[float], zoom: int) -> int:
        """Get tile count for given bbox and zoom level"""
        pass
    
    @abstractmethod
    def validate_source(self) -> bool:
        """Validate if source file exists and is accessible"""
        pass
