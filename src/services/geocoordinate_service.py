import os
import sys
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for geocoordinate import
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from geocoordinate.api import CoordinateAPI


class GeoCoordinateService:
    """Service for getting bounding box coordinates from place names using GeoCoordinate API"""
    
    def __init__(self, data_dir: str = "geocoordinate_data"):
        """Initialize GeoCoordinate service
        
        Args:
            data_dir: Directory containing GeoCoordinate data files
        """
        self.data_dir = data_dir
        self._api = None
        self._initialize_api()
    
    def _initialize_api(self) -> bool:
        """Initialize the GeoCoordinate API"""
        try:
            if not os.path.exists(self.data_dir):
                print(f"GeoCoordinate data directory not found: {self.data_dir}")
                return False
            
            # Check required files (accept Parquet or GeoJSON)
            def _any_exists(options):
                return any(os.path.exists(os.path.join(self.data_dir, opt)) for opt in options)

            # metadata is required
            if not _any_exists(["metadata_original.json"]):
                print(f"Required GeoCoordinate data file not found: {os.path.join(self.data_dir, 'metadata_original.json')}")
                return False

            # provinces: parquet or geojson
            if not _any_exists(["provinces.parquet", "provinces_original.geojson"]):
                print("Required provinces data not found (expected one of: provinces.parquet, provinces_original.geojson)")
                return False

            # districts: parquet or geojson
            if not _any_exists(["districts.parquet", "districts_original.geojson"]):
                print("Required districts data not found (expected one of: districts.parquet, districts_original.geojson)")
                return False

            # countries: optional; accept parquet/fgb/geojson
            if not _any_exists(["countries.parquet", "countries.fgb", "countries_original_merged.geojson"]):
                print("Warning: No country polygons found (countries.parquet/fgb/geojson missing). Country-level polygons will be limited (index-only).")
            
            self._api = CoordinateAPI(self.data_dir)
            return True
            
        except Exception as e:
            print(f"Failed to initialize GeoCoordinate API: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if GeoCoordinate service is available"""
        return self._api is not None
    
    def get_bbox_from_place(self, place_name: str, region_type: str = "auto") -> Optional[List[float]]:
        """Get bounding box coordinates from place name
        
        Args:
            place_name: Name of the place (e.g., "Marmara", "Germany", "Istanbul")
            region_type: Type of region ("auto", "province", "district", "country")
            
        Returns:
            List of coordinates [min_lon, min_lat, max_lon, max_lat] or None if not found
        """
        if not self.is_available():
            print("GeoCoordinate service is not available")
            return None
        
        try:
            result = self._api.find_coordinates(place_name, region_type)
            
            if result['success'] and result['coordinates']:
                bounds = result['coordinates']['bounding_box']['bounds']
                bbox = [
                    bounds['min_lon'],
                    bounds['min_lat'], 
                    bounds['max_lon'],
                    bounds['max_lat']
                ]
                
                print(f"Found coordinates for '{place_name}':")
                print(f"  Region type: {result['region_type']}")
                print(f"  Found regions: {result['found_regions']}")
                print(f"  Bounding box: {bbox}")
                print(f"  Center: {result['coordinates']['center']}")
                
                return bbox
            else:
                error_msg = result.get('error', 'Unknown error')
                print(f"Could not find coordinates for '{place_name}': {error_msg}")
                
                if result.get('not_found'):
                    print(f"Regions not found: {result['not_found']}")
                
                return None
                
        except Exception as e:
            print(f"Error getting coordinates for '{place_name}': {e}")
            return None

    def get_polygon_for_place(self, place_name: str, region_type: str = "auto") -> Optional[dict]:
        """Get polygon GeoJSON for a place. Returns a GeoJSON geometry dict or None."""
        if not self.is_available():
            print("GeoCoordinate service is not available")
            return None
        try:
            result = self._api.find_coordinates(place_name, region_type)
            if result.get('success') and result.get('coordinates', {}).get('polygon'):
                return result['coordinates']['polygon']
            return None
        except Exception as e:
            print(f"Error getting polygon for '{place_name}': {e}")
            return None
    
    def search_suggestions(self, partial_name: str, limit: int = 10) -> List[Dict]:
        """Get search suggestions for partial place name
        
        Args:
            partial_name: Partial place name
            limit: Maximum number of suggestions
            
        Returns:
            List of suggestion dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            return self._api.search_suggestions(partial_name, limit)
        except Exception as e:
            print(f"Error getting suggestions for '{partial_name}': {e}")
            return []
    
    def get_region_list(self, region_type: str = "province", language: str = "tr") -> List[Dict]:
        """Get list of available regions
        
        Args:
            region_type: Type of region ("province", "district", "country")
            language: Language code ("tr", "en")
            
        Returns:
            List of region dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            return self._api.get_region_list(region_type, language)
        except Exception as e:
            print(f"Error getting region list: {e}")
            return []
    
    def health_check(self) -> Dict:
        """Perform health check on GeoCoordinate service"""
        if not self.is_available():
            return {
                "status": "unavailable",
                "error": "GeoCoordinate API not initialized"
            }
        
        try:
            return self._api.health_check()
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
