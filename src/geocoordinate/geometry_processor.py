from typing import List, Dict
from .interfaces import IGeometryProcessor

class ShapelyGeometryProcessor(IGeometryProcessor):
    """Shapely geometry processor"""
    
    def extract_polygon_coordinates(self, geometry) -> Dict:
        """Extract polygon coordinates from geometry (optimized)"""
        try:
            if geometry.geom_type == 'Polygon':
                coords = list(geometry.exterior.coords)
                return {
                    "type": "Polygon",
                    "coordinates": [[[coord[0], coord[1]] for coord in coords]]
                }
            elif geometry.geom_type == 'MultiPolygon':
                polygons = []
                for polygon in geometry.geoms:
                    coords = list(polygon.exterior.coords)
                    exterior = [[coord[0], coord[1]] for coord in coords]
                    # GeoJSON MultiPolygon requires array of polygons, each polygon: [ [exterior], [hole1], ... ]
                    polygons.append([exterior])
                return {
                    "type": "MultiPolygon",
                    "coordinates": polygons
                }
            else:
                return {"type": "Unknown", "coordinates": []}
        except Exception as e:
            return {"type": "Error", "error": str(e), "coordinates": []}
    
    def check_contiguity(self, geometries: List) -> bool:
        """Check if geometries are contiguous (optimized)"""
        if len(geometries) <= 1:
            return True
        
        # Quick check: are all geometries connected?
        combined = geometries[0]
        for geom in geometries[1:]:
            if not combined.intersects(geom):
                return False
            combined = combined.union(geom)
        return True
    
    def calculate_bounds(self, geometry) -> Dict:
        """Calculate geometry bounds"""
        bounds = geometry.bounds  # (minx, miny, maxx, maxy)
        
        return {
            "northwest": {"lat": bounds[3], "lon": bounds[0]},
            "northeast": {"lat": bounds[3], "lon": bounds[2]},
            "southwest": {"lat": bounds[1], "lon": bounds[0]},
            "southeast": {"lat": bounds[1], "lon": bounds[2]},
            "bounds": {
                "min_lon": bounds[0],
                "min_lat": bounds[1],
                "max_lon": bounds[2],
                "max_lat": bounds[3]
            },
            "center": {
                "lat": (bounds[1] + bounds[3]) / 2,
                "lon": (bounds[0] + bounds[2]) / 2
            }
        }
    
    def simplify_geometry(self, geometry, tolerance: float = 0.001) -> any:
        """Simplify geometry for performance"""
        try:
            return geometry.simplify(tolerance, preserve_topology=True)
        except:
            return geometry
    
    def get_coordinate_count(self, geometry) -> int:
        """Get coordinate count in geometry"""
        try:
            if geometry.geom_type == 'Polygon':
                return len(list(geometry.exterior.coords))
            elif geometry.geom_type == 'MultiPolygon':
                count = 0
                for polygon in geometry.geoms:
                    count += len(list(polygon.exterior.coords))
                return count
            else:
                return 0
        except:
            return 0 