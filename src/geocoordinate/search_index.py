from typing import List, Dict, Optional
from .interfaces import ISearchIndex, SearchSuggestion

class MetadataSearchIndex(ISearchIndex):
    """Metadata-based search index"""
    
    def __init__(self, metadata: Dict):
        self.metadata = metadata
        self._provinces_index = metadata.get("search_indexes", {}).get("provinces", {})
        self._districts_index = metadata.get("search_indexes", {}).get("districts", {})
        self._countries_index = metadata.get("search_indexes", {}).get("countries", {})
    
    def find_region(self, name: str, region_type: str) -> Optional[Dict]:
        """Find region"""
        name_lower = name.lower()
        
        if region_type == "province":
            return self._provinces_index.get(name_lower)
        elif region_type == "district":
            return self._districts_index.get(name_lower)
        elif region_type == "country":
            return self._countries_index.get(name_lower)
        
        return None
    
    def search_suggestions(self, partial: str, region_type: str = None) -> List[SearchSuggestion]:
        """Get search suggestions"""
        suggestions = []
        partial_lower = partial.lower()
        
        if region_type is None or region_type == "province":
            for name, info in self._provinces_index.items():
                if partial_lower in name:
                    suggestions.append(SearchSuggestion(
                        name=info["name_tr"],
                        name_en=info["name_en"],
                        type="province",
                        id=info["id"]
                    ))
        
        if region_type is None or region_type == "district":
            for name, info in self._districts_index.items():
                if partial_lower in name:
                    suggestions.append(SearchSuggestion(
                        name=info["name_tr"],
                        name_en=info["name_en"],
                        type="district",
                        id=info["id"]
                    ))
        
        if region_type is None or region_type == "country":
            for name, info in self._countries_index.items():
                if partial_lower in name:
                    suggestions.append(SearchSuggestion(
                        name=info["name_tr"],
                        name_en=info["name_en"],
                        type="country",
                        id=info["id"]
                    ))
        
        # Return first 10 suggestions
        return suggestions[:10]
    
    def get_all_regions(self, region_type: str = "province") -> List[Dict]:
        """Get all regions"""
        if region_type == "province":
            return [
                {
                    "name": info["name_tr"],
                    "name_en": info["name_en"],
                    "id": info["id"]
                }
                for info in self._provinces_index.values()
            ]
        elif region_type == "district":
            return [
                {
                    "name": info["name_tr"],
                    "name_en": info["name_en"],
                    "id": info["id"]
                }
                for info in self._districts_index.values()
            ]
        elif region_type == "country":
            return [
                {
                    "name": info["name_tr"],
                    "name_en": info["name_en"],
                    "id": info["id"]
                }
                for info in self._countries_index.values()
            ]
        
        return []
    
    def get_region_count(self, region_type: str = "province") -> int:
        """Get region count"""
        if region_type == "province":
            return len(self._provinces_index)
        elif region_type == "district":
            return len(self._districts_index)
        elif region_type == "country":
            return len(self._countries_index)
        
        return 0 