import os
from typing import List, Tuple


class FileUtils:
    """Utility class for file operations"""
    
    @staticmethod
    def ensure_directory_exists(directory_path: str) -> None:
        """Create directory if it doesn't exist"""
        os.makedirs(directory_path, exist_ok=True)
    
    @staticmethod
    def get_tile_path(output_dir: str, region_name: str, tile_type: str, 
                     style_name: str, zoom: int, x: int, y: int, extension: str) -> str:
        """Generate tile file path"""
        tile_dir = os.path.join(output_dir, region_name, tile_type, style_name, str(zoom), str(x))
        FileUtils.ensure_directory_exists(tile_dir)
        return os.path.join(tile_dir, f"{y}.{extension}")
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Check if file exists"""
        return os.path.exists(file_path)
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """Get file size in bytes"""
        return os.path.getsize(file_path) if os.path.exists(file_path) else 0
    
    @staticmethod
    def count_existing_tiles(tiles: List[Tuple[int, int, int]], output_dir: str, 
                           region_name: str, tile_type: str, style_name: str, 
                           extension: str) -> int:
        """Count existing tiles"""
        existing_count = 0
        for zoom, x, y in tiles:
            tile_path = FileUtils.get_tile_path(output_dir, region_name, tile_type, 
                                              style_name, zoom, x, y, extension)
            if FileUtils.file_exists(tile_path):
                existing_count += 1
        return existing_count 