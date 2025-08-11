from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class TileServer:
    """Data model for tile server configuration"""
    name: str
    url: str
    headers: Dict[str, str]
    tile_type: str  # 'raster' or 'vector'
    
    def get_tile_url(self, zoom: int, x: int, y: int) -> str:
        """Generate tile URL for given coordinates"""
        return self.url.format(z=zoom, x=x, y=y)
    
    def get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return self.headers.copy()
    
    def get_tile_type(self) -> str:
        """Get tile type"""
        return self.tile_type
    
    def get_name(self) -> str:
        """Get server name"""
        return self.name


@dataclass
class Region:
    """Data model for geographic region"""
    name: str
    bbox: list  # [min_lon, min_lat, max_lon, max_lat]
    min_zoom: int
    max_zoom: int
    description: str


@dataclass
class DownloadConfig:
    """Data model for download configuration"""
    output_dir: str
    max_workers_per_server: int
    retry_attempts: int
    timeout: int
    enabled_servers: list
    server_definitions: Dict[str, TileServer] 