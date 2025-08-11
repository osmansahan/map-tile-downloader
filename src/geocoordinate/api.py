import json
from typing import Dict, List
from .coordinate_finder import FastCoordinateFinder
from .interfaces import CoordinateResult, SearchSuggestion

class CoordinateAPI:
    """Main coordinate API class"""
    
    def __init__(self, data_dir: str = "data"):
        self.finder = FastCoordinateFinder(data_dir)
    
    def find_coordinates(self, query: str, region_type: str = "auto") -> Dict:
        """Find coordinates and return in JSON format"""
        try:
            result = self.finder.find_coordinates(query, region_type)
            
            if result.success:
                return {
                    "success": True,
                    "region_type": result.region_type,
                    "requested_regions": result.requested_regions,
                    "found_regions": result.found_regions,
                    "not_found": result.not_found,
                    "coordinates": {
                        "bounding_box": result.bounding_box,
                        "center": result.center,
                        "polygon": result.polygon,
                        "is_contiguous": result.is_contiguous
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.error,
                    "region_type": result.region_type,
                    "requested_regions": result.requested_regions,
                    "found_regions": result.found_regions,
                    "not_found": result.not_found
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"API error: {str(e)}"
            }
    
    def search_suggestions(self, partial: str, limit: int = 10) -> List[Dict]:
        """Get search suggestions"""
        try:
            suggestions = self.finder.search_suggestions(partial, limit)
            return [
                {
                    "name": s.name,
                    "name_en": s.name_en,
                    "type": s.type,
                    "id": s.id
                }
                for s in suggestions
            ]
        except Exception as e:
            return []
    
    def get_region_list(self, region_type: str = "province", language: str = "tr") -> List[Dict]:
        """Get region list"""
        try:
            return self.finder.get_region_list(region_type, language)
        except Exception as e:
            return []
    
    def get_performance_info(self) -> Dict:
        """Get performance information"""
        try:
            return self.finder.get_performance_info()
        except Exception as e:
            return {"error": str(e)}
    
    def health_check(self) -> Dict:
        """System health check"""
        try:
            # Test metadata loading
            metadata = self.finder.data_loader.load_metadata()
            
            return {
                "status": "healthy",
                "metadata_loaded": True,
                "search_index_ready": self.finder.search_index is not None,
                "timestamp": "2024-01-01T00:00:00Z"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z"
            }

# Usage example
if __name__ == "__main__":
    api = CoordinateAPI()
    
    print("=== SOLID PRINCIPLES COMPLIANT COORDINATE API ===\n")
    
    # Health check
    print("1. System health check:")
    health = api.health_check()
    print(json.dumps(health, indent=2, ensure_ascii=False))
    print()
    
    # Performance info
    print("2. Performance info:")
    perf = api.get_performance_info()
    print(json.dumps(perf, indent=2, ensure_ascii=False))
    print()
    
    # Coordinate search
    print("3. 'Aydın' coordinates:")
    result = api.find_coordinates("Aydın")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()
    
    # Multiple regions
    print("4. 'İstanbul, Ankara' coordinates:")
    result = api.find_coordinates("İstanbul, Ankara")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()
    
    # Search suggestions
    print("5. Suggestions containing 'an':")
    suggestions = api.search_suggestions("an", 5)
    print(json.dumps(suggestions, indent=2, ensure_ascii=False))
    print()
    
    # Region list
    print("6. First 5 provinces:")
    provinces = api.get_region_list("province", "tr")[:5]
    print(json.dumps(provinces, indent=2, ensure_ascii=False)) 