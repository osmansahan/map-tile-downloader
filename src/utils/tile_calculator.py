import math
from typing import List, Tuple, Optional
from shapely.geometry import box, shape
from shapely.prepared import prep


class TileCalculator:
    """Utility class for tile coordinate calculations"""
    
    @staticmethod
    def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
        """Convert lat/lon to tile coordinates"""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return xtile, ytile
    
    @staticmethod
    def get_tiles_for_bbox(bbox: List[float], min_zoom: int, max_zoom: int) -> List[Tuple[int, int, int]]:
        """Get all tile coordinates for given bbox and zoom range"""
        tiles = []
        min_lon, min_lat, max_lon, max_lat = bbox
        
        for zoom in range(min_zoom, max_zoom + 1):
            min_x, max_y = TileCalculator.deg2num(min_lat, min_lon, zoom)
            max_x, min_y = TileCalculator.deg2num(max_lat, max_lon, zoom)
            
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    tiles.append((zoom, x, y))
        
        return tiles

    @staticmethod
    def tile_bounds(zoom: int, x: int, y: int) -> List[float]:
        """Return geographic bounds [minLon, minLat, maxLon, maxLat] for XYZ tile."""
        n = 2 ** zoom
        lon_min = x / n * 360.0 - 180.0
        lon_max = (x + 1) / n * 360.0 - 180.0

        def y_to_lat(y_val: int) -> float:
            import math
            return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y_val / n))))

        lat_max = y_to_lat(y)
        lat_min = y_to_lat(y + 1)
        return [lon_min, lat_min, lon_max, lat_max]

    @staticmethod
    def get_tiles_for_polygon(polygon_geojson: dict, min_zoom: int, max_zoom: int, bbox_hint: Optional[List[float]] = None) -> List[Tuple[int, int, int]]:
        """Generate tiles intersecting a polygon (GeoJSON geometry dict). Uses bbox hint if provided to limit candidates."""
        # Build shapely geometry
        poly = shape(polygon_geojson)
        poly = poly.buffer(0) if not poly.is_valid else poly
        prepared = prep(poly)

        # If no bbox hint, compute from polygon bounds
        if bbox_hint is None:
            min_lon, min_lat, max_lon, max_lat = poly.bounds
            bbox_hint = [min_lon, min_lat, max_lon, max_lat]

        # Candidate tiles by bbox
        candidate_tiles = TileCalculator.get_tiles_for_bbox(bbox_hint, min_zoom, max_zoom)

        # Filter by polygon intersection
        filtered: List[Tuple[int, int, int]] = []
        for z, x, y in candidate_tiles:
            tb = TileCalculator.tile_bounds(z, x, y)
            tile_poly = box(tb[0], tb[1], tb[2], tb[3])
            if prepared.intersects(tile_poly):
                filtered.append((z, x, y))

        return filtered
    
    @staticmethod
    def calculate_tile_count(bbox: List[float], min_zoom: int, max_zoom: int) -> int:
        """Calculate total number of tiles for given bbox and zoom range"""
        tiles = TileCalculator.get_tiles_for_bbox(bbox, min_zoom, max_zoom)
        return len(tiles) 