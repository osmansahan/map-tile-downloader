from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import os


@dataclass
class LocalSource:
    """Data model for local tile source (MBTiles, etc.)"""
    name: str
    path: str
    source_type: str  # 'mbtiles', 'xyz', etc.
    tile_type: str  # 'raster' or 'vector'
    bounds: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    min_zoom: int
    max_zoom: int
    description: str = ""
    
    def get_name(self) -> str:
        """Get source name"""
        return self.name
    
    def get_path(self) -> str:
        """Get source file path"""
        return self.path
    
    def get_source_type(self) -> str:
        """Get source type - returns 'local' for local sources"""
        return 'local'
    
    def get_tile_type(self) -> str:
        """Get tile type"""
        return self.tile_type
    
    def get_bounds(self) -> List[float]:
        """Get source bounds"""
        return self.bounds.copy()
    
    def get_zoom_range(self) -> Tuple[int, int]:
        """Get zoom range"""
        return (self.min_zoom, self.max_zoom)
    
    def validate_bounds(self, bbox: List[float]) -> bool:
        """Validate if bbox is within source bounds"""
        if len(bbox) != 4 or len(self.bounds) != 4:
            return False
        
        min_lon, min_lat, max_lon, max_lat = bbox
        src_min_lon, src_min_lat, src_max_lon, src_max_lat = self.bounds
        
        return (min_lon >= src_min_lon and max_lon <= src_max_lon and
                min_lat >= src_min_lat and max_lat <= src_max_lat)
    
    def is_available(self) -> bool:
        """Check if source file exists"""
        return os.path.exists(self.path) and os.path.isfile(self.path)
    
    def get_file_size(self) -> Optional[int]:
        """Get source file size in bytes"""
        if self.is_available():
            return os.path.getsize(self.path)
        return None
