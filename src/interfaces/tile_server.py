from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple


class ITileServer(ABC):
    """Interface for tile server implementations"""
    
    @abstractmethod
    def get_tile_url(self, zoom: int, x: int, y: int) -> str:
        """Generate tile URL for given coordinates"""
        pass
    
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get request headers for this server"""
        pass
    
    @abstractmethod
    def get_tile_type(self) -> str:
        """Get tile type (raster/vector)"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get server name"""
        pass


class ITileDownloader(ABC):
    """Interface for tile downloader implementations"""
    
    @abstractmethod
    def download_tile(self, zoom: int, x: int, y: int, output_path: str) -> bool:
        """Download a single tile"""
        pass
    
    @abstractmethod
    def download_tiles_batch(self, tiles: list, output_dir: str) -> Dict[str, Any]:
        """Download multiple tiles"""
        pass


class IConfigLoader(ABC):
    """Interface for configuration loading"""
    
    @abstractmethod
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file"""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration"""
        pass 