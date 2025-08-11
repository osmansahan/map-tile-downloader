import sqlite3
import os
from typing import Dict, Any, List, Tuple, Optional
from interfaces.tile_source import ITileSource, ITileExtractor
from adapters.base_adapter import BaseAdapter
from utils.mbtiles_utils import MBTilesUtils



class MBTilesAdapter(BaseAdapter, ITileSource, ITileExtractor):
    """Adapter for MBTiles sources"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.file_path = config.get('path', '')
        self.bounds = config.get('bounds', [])
        self.min_zoom = config.get('min_zoom', 0)
        self.max_zoom = config.get('max_zoom', 22)
        self.connection = None
        self._metadata = None
        self.is_tms = False
    
    def initialize(self) -> bool:
        """Initialize the MBTiles adapter"""
        if not self.validate_config():
            return False
        
        if not MBTilesUtils.validate_mbtiles_file(self.file_path):
            return False
        
        try:
            # Load metadata
            self._metadata = MBTilesUtils.get_mbtiles_metadata(self.file_path)
            
            # Update bounds and zoom range from metadata if not provided
            if not self.bounds:
                self.bounds = MBTilesUtils.get_mbtiles_bounds(self.file_path) or []
            
            if self.min_zoom == 0 and self.max_zoom == 22:
                zoom_range = MBTilesUtils.get_mbtiles_zoom_range(self.file_path)
                if zoom_range:
                    self.min_zoom, self.max_zoom = zoom_range
            
            # Check if this is TMS format
            self.is_tms = self._check_tms_format()
            
            return True
        except Exception as e:
            print(f"Failed to initialize MBTiles adapter: {e}")
            return False
    
    def _check_tms_format(self) -> bool:
        """Check if MBTiles uses TMS coordinate system"""
        try:
            # Check metadata for scheme
            if self._metadata and 'scheme' in self._metadata:
                return self._metadata['scheme'].lower() == 'tms'
            return False
        except:
            return False
    
    def _convert_y_coordinate(self, y: int, zoom: int) -> int:
        """Convert Y coordinate for TMS format"""
        if self.is_tms:
            return (1 << zoom) - 1 - y
        return y
    
    def validate_config(self) -> bool:
        """Validate adapter configuration"""
        if not self.file_path:
            return False
        
        if not os.path.exists(self.file_path):
            return False
        
        # Try to get bounds from metadata if not provided
        if not self.bounds or len(self.bounds) != 4:
            try:
                metadata_bounds = MBTilesUtils.get_mbtiles_bounds(self.file_path)
                if metadata_bounds and len(metadata_bounds) == 4:
                    self.bounds = metadata_bounds
                else:
                    return False
            except Exception as e:
                return False
        
        return True
    
    def get_tile(self, zoom: int, x: int, y: int) -> Optional[bytes]:
        """Get tile data for given coordinates"""
        try:
            with sqlite3.connect(self.file_path) as conn:
                cursor = conn.cursor()
                
                # Check table structure
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                if 'tiles' in tables:
                    # Standard MBTiles format
                    cursor.execute(
                        "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                        (zoom, x, y)
                    )
                elif 'images' in tables and 'map' in tables:
                    # TMS format
                    cursor.execute(
                        """SELECT i.tile_data 
                           FROM images i 
                           JOIN map m ON i.tile_id = m.tile_id 
                           WHERE m.zoom_level = ? AND m.tile_column = ? AND m.tile_row = ?""",
                        (zoom, x, y)
                    )
                elif 'omtm' in tables:
                    # OMTM format
                    cursor.execute(
                        "SELECT tile_data FROM omtm WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                        (zoom, x, y)
                    )
                else:
                    print(f"Unsupported MBTiles format")
                    return None
                
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Failed to get tile {zoom}/{x}/{y}: {e}")
            return None
    
    def extract_tiles(self, bbox: List[float], zoom: int) -> List[Tuple[int, int, bytes]]:
        """Extract tiles for given bbox and zoom level"""
        tiles = []
        
        if not self.validate_bounds(bbox):
            return tiles
        
        try:
            min_x, max_x, min_y, max_y = MBTilesUtils.bbox_to_tile_range(bbox, zoom)
            
            # Convert Y coordinates for TMS format
            if self.is_tms:
                original_min_y = min_y
                min_y = self._convert_y_coordinate(max_y, zoom)
                max_y = self._convert_y_coordinate(original_min_y, zoom)
            
            with sqlite3.connect(self.file_path) as conn:
                cursor = conn.cursor()
                
                # Check table structure
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                if 'tiles' in tables:
                    # Standard MBTiles format
                    cursor.execute(
                        """SELECT tile_column, tile_row, tile_data 
                           FROM tiles 
                           WHERE zoom_level = ? 
                           AND tile_column BETWEEN ? AND ? 
                           AND tile_row BETWEEN ? AND ?""",
                        (zoom, min_x, max_x, min_y, max_y)
                    )
                elif 'images' in tables and 'map' in tables:
                    # TMS format
                    cursor.execute(
                        """SELECT m.tile_column, m.tile_row, i.tile_data 
                           FROM images i 
                           JOIN map m ON i.tile_id = m.tile_id 
                           WHERE m.zoom_level = ? 
                           AND m.tile_column BETWEEN ? AND ? 
                           AND m.tile_row BETWEEN ? AND ?""",
                        (zoom, min_x, max_x, min_y, max_y)
                    )
                elif 'omtm' in tables and 'images' in tables and 'map' in tables:
                    # OMTM format (omtm is metadata, tiles are in images/map)
                    cursor.execute(
                        """SELECT m.tile_column, m.tile_row, i.tile_data 
                           FROM images i 
                           JOIN map m ON i.tile_id = m.tile_id 
                           WHERE m.zoom_level = ? 
                           AND m.tile_column BETWEEN ? AND ? 
                           AND m.tile_row BETWEEN ? AND ?""",
                        (zoom, min_x, max_x, min_y, max_y)
                    )
                else:
                    print(f"Unsupported MBTiles format. Tables found: {tables}")
                    return tiles
                
                for row in cursor.fetchall():
                    x, y, tile_data = row
                    # Normalize to XYZ scheme for filesystem output
                    if self.is_tms:
                        y = self._convert_y_coordinate(y, zoom)
                    tiles.append((x, y, tile_data))
                
                return tiles
        except Exception as e:
            print(f"Failed to extract tiles: {e}")
            return tiles
    
    def get_tile_count(self, bbox: List[float], zoom: int) -> int:
        """Get tile count for given bbox and zoom level"""
        if not self.validate_bounds(bbox):
            return 0
        
        try:
            min_x, max_x, min_y, max_y = MBTilesUtils.bbox_to_tile_range(bbox, zoom)
            
            # Convert Y coordinates for TMS format
            if self.is_tms:
                original_min_y = min_y
                min_y = self._convert_y_coordinate(max_y, zoom)
                max_y = self._convert_y_coordinate(original_min_y, zoom)
            
            with sqlite3.connect(self.file_path) as conn:
                cursor = conn.cursor()
                
                # Check table structure
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                if 'tiles' in tables:
                    # Standard MBTiles format
                    cursor.execute(
                        """SELECT COUNT(*) 
                           FROM tiles 
                           WHERE zoom_level = ? 
                           AND tile_column BETWEEN ? AND ? 
                           AND tile_row BETWEEN ? AND ?""",
                        (zoom, min_x, max_x, min_y, max_y)
                    )
                elif 'images' in tables and 'map' in tables:
                    # TMS format
                    cursor.execute(
                        """SELECT COUNT(*) 
                           FROM images i 
                           JOIN map m ON i.tile_id = m.tile_id 
                           WHERE m.zoom_level = ? 
                           AND m.tile_column BETWEEN ? AND ? 
                           AND m.tile_row BETWEEN ? AND ?""",
                        (zoom, min_x, max_x, min_y, max_y)
                    )
                elif 'omtm' in tables and 'images' in tables and 'map' in tables:
                    # OMTM format (omtm is metadata, tiles are in images/map)
                    cursor.execute(
                        """SELECT COUNT(*) 
                           FROM images i 
                           JOIN map m ON i.tile_id = m.tile_id 
                           WHERE m.zoom_level = ? 
                           AND m.tile_column BETWEEN ? AND ? 
                           AND m.tile_row BETWEEN ? AND ?""",
                        (zoom, min_x, max_x, min_y, max_y)
                    )
                else:
                    return 0
                
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            print(f"Failed to get tile count: {e}")
            return 0
    
    def validate_source(self) -> bool:
        """Validate if source file exists and is accessible"""
        return MBTilesUtils.validate_mbtiles_file(self.file_path)
    
    def get_bounds(self) -> List[float]:
        """Get source bounds"""
        return self.bounds.copy()
    
    def get_zoom_range(self) -> Tuple[int, int]:
        """Get available zoom range"""
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
        """Check if source is available"""
        return self.validate_source()
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get MBTiles metadata"""
        return self._metadata or {}
