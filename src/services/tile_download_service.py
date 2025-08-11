import time
import os
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from interfaces.tile_server import ITileDownloader
from models.tile_server import TileServer
from utils.file_utils import FileUtils
from exceptions.tile_downloader_exceptions import DownloadError, ServerError


class TileDownloadService(ITileDownloader):
    """Service for downloading map tiles"""
    
    def __init__(self, max_workers: int = 15, retry_attempts: int = 3, timeout: int = 30):
        self.max_workers = max_workers
        self.retry_attempts = retry_attempts
        self.timeout = timeout
    
    def create_session(self) -> requests.Session:
        """Create optimized session for downloads"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def download_tile(self, zoom: int, x: int, y: int, output_path: str, 
                     server: TileServer) -> bool:
        """Download a single tile"""
        tile_url = server.get_tile_url(zoom, x, y)
        
        # Skip only if file exists and is non-empty
        if FileUtils.file_exists(output_path) and FileUtils.get_file_size(output_path) > 0:
            return True
        
        for attempt in range(self.retry_attempts):
            try:
                if attempt > 0:
                    time.sleep(0.5 * attempt)
                
                session = self.create_session()
                response = session.get(tile_url, headers=server.get_headers(), 
                                     timeout=self.timeout)
                response.raise_for_status()
                
                content = response.content
                # Reject empty content to avoid creating zero-byte tiles
                if not content or len(content) == 0:
                    raise DownloadError(f"Empty content received for tile {zoom}/{x}/{y} from {tile_url}")

                with open(output_path, 'wb') as f:
                    f.write(content)
                
                return True
                
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    raise DownloadError(f"Failed to download tile {zoom}/{x}/{y}: {e}")
                time.sleep(1.0)
        
        return False
    
    def download_tiles_batch(self, tiles: List[Tuple[int, int, int]], 
                           output_dir: str, region_name: str, 
                           servers: List[TileServer],
                           tile_postprocess=None) -> Dict[str, Any]:
        """Download multiple tiles using multiple servers.
        tile_postprocess: optional callable (bytes, z, x, y, server)->bytes for per-tile post-processing (e.g., raster mask).
        """
        results = {
            'total': len(tiles),
            'downloaded': 0,
            'failed': 0,
            'errors': []
        }
        
        # Separate vector and raster servers
        vector_servers = [s for s in servers if s.get_tile_type() == 'vector']
        raster_servers = [s for s in servers if s.get_tile_type() != 'vector']
        
        def download_single_tile(tile_info: Tuple[int, int, int]) -> str:
            zoom, x, y = tile_info
            
            # Try vector servers first
            if vector_servers:
                for server in vector_servers:
                    try:
                        extension = 'pbf'
                        tile_path = FileUtils.get_tile_path(
                            output_dir, region_name, 'vector', server.get_name(),
                            zoom, x, y, extension
                        )
                        
                        if self.download_tile(zoom, x, y, tile_path, server):
                            return f"Downloaded: vector/{server.get_name()}/{zoom}/{x}/{y}.{extension}"
                    except Exception as e:
                        continue
            
            # Try raster servers as fallback
            if raster_servers:
                for server in raster_servers:
                    try:
                        extension = 'png'
                        # Use actual server name instead of hardcoded CartoDB_Light
                        tile_path = FileUtils.get_tile_path(
                            output_dir, region_name, 'raster', server.get_name(),
                            zoom, x, y, extension
                        )
                        
                        if FileUtils.file_exists(tile_path) and FileUtils.get_file_size(tile_path) > 0:
                            return f"Downloaded: raster/{server.get_name()}/{zoom}/{x}/{y}.{extension}"
                        
                        # Download to memory if postprocess is needed
                        if tile_postprocess is not None:
                            session = self.create_session()
                            response = session.get(server.get_tile_url(zoom, x, y), headers=server.get_headers(), timeout=self.timeout)
                            response.raise_for_status()
                            content = response.content
                            try:
                                content = tile_postprocess(content, zoom, x, y, server)
                            except Exception:
                                # If postprocess fails, keep original
                                pass
                            # Reject empty content
                            if not content or len(content) == 0:
                                raise DownloadError(f"Empty content received for tile {zoom}/{x}/{y} from {server.get_name()}")
                            os.makedirs(os.path.dirname(tile_path), exist_ok=True)
                            with open(tile_path, 'wb') as f:
                                f.write(content)
                            return f"Downloaded: raster/{server.get_name()}/{zoom}/{x}/{y}.{extension}"
                        else:
                            if self.download_tile(zoom, x, y, tile_path, server):
                                return f"Downloaded: raster/{server.get_name()}/{zoom}/{x}/{y}.{extension}"
                    except Exception as e:
                        continue
            
            return f"Failed: {zoom}/{x}/{y}"
        
        # Download tiles using thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(download_single_tile, tile) for tile in tiles]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if "Downloaded:" in result:
                        results['downloaded'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(result)
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(str(e))
        
        return results 