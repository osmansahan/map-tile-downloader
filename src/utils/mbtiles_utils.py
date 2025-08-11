import sqlite3
import math
import os
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path


class MBTilesUtils:
    """Utility class for MBTiles operations"""
    
    @staticmethod
    def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """Convert lat/lon to tile coordinates"""
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        xtile = int((lon + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return xtile, ytile
    
    @staticmethod
    def bbox_to_tile_range(bbox: List[float], zoom: int) -> Tuple[int, int, int, int]:
        """Convert bounding box to tile range"""
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Get tile coordinates for corners
        min_x, max_y = MBTilesUtils.lat_lon_to_tile(min_lat, min_lon, zoom)
        max_x, min_y = MBTilesUtils.lat_lon_to_tile(max_lat, max_lon, zoom)
        
        return min_x, max_x, min_y, max_y
    
    @staticmethod
    def validate_mbtiles_file(file_path: str) -> bool:
        """Validate if file is a valid MBTiles database"""
        if not os.path.exists(file_path):
            return False
        
        try:
            with sqlite3.connect(file_path) as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Check for standard MBTiles format (tiles + metadata)
                if 'tiles' in tables and 'metadata' in tables:
                    return True
                
                # Check for TMS format (images + map + metadata)
                if 'images' in tables and 'map' in tables and 'metadata' in tables:
                    return True
                
                # Check for OMTM format (omtm + metadata)
                if 'omtm' in tables and 'metadata' in tables:
                    return True
                
                return False
                
        except Exception:
            return False
    
    @staticmethod
    def get_mbtiles_metadata(file_path: str) -> Dict[str, Any]:
        """Get MBTiles metadata"""
        metadata = {}
        
        try:
            with sqlite3.connect(file_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, value FROM metadata")
                
                for row in cursor.fetchall():
                    metadata[row[0]] = row[1]
                
                return metadata
        except Exception as e:
            raise ValueError(f"Failed to read MBTiles metadata: {e}")
    
    @staticmethod
    def get_mbtiles_bounds(file_path: str) -> Optional[List[float]]:
        """Get MBTiles bounds from metadata"""
        try:
            metadata = MBTilesUtils.get_mbtiles_metadata(file_path)
            bounds_str = metadata.get('bounds')
            
            if bounds_str:
                bounds = [float(x) for x in bounds_str.split(',')]
                if len(bounds) == 4:
                    return bounds
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def get_mbtiles_zoom_range(file_path: str) -> Optional[Tuple[int, int]]:
        """Get MBTiles zoom range from metadata"""
        try:
            metadata = MBTilesUtils.get_mbtiles_metadata(file_path)
            min_zoom = metadata.get('minzoom')
            max_zoom = metadata.get('maxzoom')
            
            if min_zoom is not None and max_zoom is not None:
                return (int(min_zoom), int(max_zoom))
            
            return None
        except Exception:
            return None
