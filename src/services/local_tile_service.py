import os
from typing import Dict, Any, List, Tuple, Optional
from shapely.geometry import shape, box
from shapely.prepared import prep
from interfaces.tile_source import ITileSource, ITileExtractor
from adapters.mbtiles_adapter import MBTilesAdapter



class LocalTileService:
    """Service for handling local tile sources (MBTiles, etc.)"""
    
    def __init__(self):
        self.sources: Dict[str, ITileSource] = {}
        self.extractors: Dict[str, ITileExtractor] = {}
    
    def register_source(self, source_config: Dict[str, Any]) -> bool:
        """Register a local source"""
        try:
            source_type = source_config.get('source_type', '')  # Changed from 'type' to 'source_type'
            source_name = source_config.get('name', '')
            
            if source_type == 'mbtiles':
                adapter = MBTilesAdapter(source_config)
                if adapter.initialize():
                    self.sources[source_name] = adapter
                    self.extractors[source_name] = adapter
                    return True
                else:
                    print(f"Failed to initialize MBTiles source: {source_name}")
                    return False
            else:
                print(f"Unsupported source type: {source_type}")
                return False
                
        except Exception as e:
            print(f"Failed to register source: {e}")
            return False
    
    def get_source(self, source_name: str) -> Optional[ITileSource]:
        """Get a registered source"""
        return self.sources.get(source_name)
    
    def get_extractor(self, source_name: str) -> Optional[ITileExtractor]:
        """Get a registered extractor"""
        return self.extractors.get(source_name)
    
    def list_sources(self) -> List[str]:
        """List all registered sources"""
        return list(self.sources.keys())
    
    def validate_source(self, source_name: str) -> bool:
        """Validate if source exists and is available"""
        source = self.get_source(source_name)
        return source is not None and source.is_available()
    
    def extract_tiles(self, source_name: str, bbox: List[float], 
                     zoom: int, output_dir: str, region_name: str) -> Dict[str, Any]:
        """Extract tiles from local source"""
        result = {
            'success': False,
            'tiles_extracted': 0,
            'errors': [],
            'output_path': ''
        }
        
        try:
            extractor = self.get_extractor(source_name)
            if not extractor:
                result['errors'].append(f"Source not found: {source_name}")
                return result
            
            if not extractor.validate_source():
                result['errors'].append(f"Source not available: {source_name}")
                return result
            
            if not extractor.validate_bounds(bbox):
                source_bounds = extractor.get_bounds()
                result['errors'].append(f"Bbox {bbox} is outside source bounds {source_bounds}. Use --list-sources to see valid coordinate ranges for {source_name}.")
                return result
            
            # Extract tiles
            tiles = extractor.extract_tiles(bbox, zoom)
            if not tiles:
                result['errors'].append("No tiles found for given bbox and zoom")
                return result
            
            # Get tile type from source to determine file extension and path
            source = self.get_source(source_name)
            tile_type = source.get_tile_type() if source else 'raster'
            extension = 'pbf' if tile_type == 'vector' else 'png'
            
            # Create output directory with tile type classification (like online sources)
            output_path = os.path.join(output_dir, region_name, tile_type, source_name, str(zoom))
            os.makedirs(output_path, exist_ok=True)
            
            # Write tiles
            tiles_written = 0
            for x, y, tile_data in tiles:
                tile_path = os.path.join(output_path, str(x), f"{y}.{extension}")
                os.makedirs(os.path.dirname(tile_path), exist_ok=True)
                
                with open(tile_path, 'wb') as f:
                    f.write(tile_data)
                tiles_written += 1
            
            result['success'] = True
            result['tiles_extracted'] = tiles_written
            result['output_path'] = output_path
            
        except Exception as e:
            result['errors'].append(f"Extraction failed: {e}")
        
        return result

    # extract_tiles_for_polygon removed from usage; keep for compatibility if referenced elsewhere (not used)
    def extract_tiles_for_polygon(self, source_name: str, polygon_geojson: dict,
                                  zoom: int, output_dir: str, region_name: str) -> Dict[str, Any]:
        """Extract tiles for a polygon from local source (MBTiles)."""
        result = {
            'success': False,
            'tiles_extracted': 0,
            'errors': [],
            'output_path': ''
        }

        try:
            extractor = self.get_extractor(source_name)
            if not extractor:
                result['errors'].append(f"Source not found: {source_name}")
                return result

            if not extractor.validate_source():
                result['errors'].append(f"Source not available: {source_name}")
                return result

            # Bounds hint from polygon
            poly = shape(polygon_geojson)
            poly = poly.buffer(0) if not poly.is_valid else poly
            min_lon, min_lat, max_lon, max_lat = poly.bounds
            bbox_hint = [min_lon, min_lat, max_lon, max_lat]

            if not extractor.validate_bounds(bbox_hint):
                source_bounds = extractor.get_bounds()
                result['errors'].append(
                    f"Polygon bbox {bbox_hint} is outside source bounds {source_bounds}. Use --list-sources to check bounds."
                )
                return result

            # Reuse extractor's bbox path then filter by polygon
            tiles = extractor.extract_tiles(bbox_hint, zoom)
            if not tiles:
                result['errors'].append("No tiles found for given polygon and zoom")
                return result

            prepared = prep(poly)

            # Get tile type and output path
            source = self.get_source(source_name)
            tile_type = source.get_tile_type() if source else 'raster'
            extension = 'pbf' if tile_type == 'vector' else 'png'
            output_path = os.path.join(output_dir, region_name, tile_type, source_name, str(zoom))
            os.makedirs(output_path, exist_ok=True)

            # Write only tiles intersecting polygon (post-filter)
            tiles_written = 0
            for x, y, tile_data in tiles:
                from utils.tile_calculator import TileCalculator
                tb = TileCalculator.tile_bounds(zoom, x, y)
                tile_poly = box(tb[0], tb[1], tb[2], tb[3])
                if not prepared.intersects(tile_poly):
                    continue
                tile_path = os.path.join(output_path, str(x), f"{y}.{extension}")
                os.makedirs(os.path.dirname(tile_path), exist_ok=True)
                with open(tile_path, 'wb') as f:
                    f.write(tile_data)
                tiles_written += 1

            result['success'] = True
            result['tiles_extracted'] = tiles_written
            result['output_path'] = output_path

        except Exception as e:
            result['errors'].append(f"Extraction failed: {e}")

        return result
    
    def get_tile_count(self, source_name: str, bbox: List[float], zoom: int) -> int:
        """Get tile count for given source, bbox and zoom"""
        extractor = self.get_extractor(source_name)
        if extractor:
            return extractor.get_tile_count(bbox, zoom)
        return 0
    
    def get_source_info(self, source_name: str) -> Dict[str, Any]:
        """Get source information"""
        source = self.get_source(source_name)
        if not source:
            return {}
        
        return {
            'name': source.get_name(),
            'type': source.get_source_type(),
            'tile_type': source.get_tile_type(),
            'bounds': source.get_bounds(),
            'zoom_range': source.get_zoom_range(),
            'available': source.is_available()
        }
