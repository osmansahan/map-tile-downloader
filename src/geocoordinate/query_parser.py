from typing import List, Dict
from .interfaces import IQueryParser

class QueryParser(IQueryParser):
    """Query parser"""
    
    def __init__(self):
        self.separators = [',', ';', ' ve ', ' and ', '\n', '\t']
    
    def parse_query(self, query: str) -> List[str]:
        """Parse query into regions"""
        if not query or not query.strip():
            return []
        
        regions = [query.strip()]
        
        for sep in self.separators:
            new_regions = []
            for region in regions:
                new_regions.extend([r.strip() for r in region.split(sep) if r.strip()])
            regions = new_regions
        
        return regions
    
    def detect_region_type(self, regions: List[str], metadata: Dict) -> str:
        """Detect region type"""
        if not regions:
            return "province"  # Default
        
        first_region = regions[0].lower()
        
        # First check districts (more specific)
        if "search_indexes" in metadata and "districts" in metadata["search_indexes"]:
            if first_region in metadata["search_indexes"]["districts"]:
                return "district"
        
        # Then check provinces
        if "search_indexes" in metadata and "provinces" in metadata["search_indexes"]:
            if first_region in metadata["search_indexes"]["provinces"]:
                return "province"
        
        # Then check countries
        if "search_indexes" in metadata and "countries" in metadata["search_indexes"]:
            if first_region in metadata["search_indexes"]["countries"]:
                return "country"
        
        # Since countries don't have search_indexes, check if it's a potential country name
        # by checking against known country patterns or fallback to country type for non-Turkish names
        country_keywords = ['algeria', 'cezayir', 'morocco', 'fas', 'egypt', 'mısır', 'libya', 'libya', 
                          'tunisia', 'tunus', 'sudan', 'sudan', 'ethiopia', 'etiyopya', 'nigeria', 'nijerya']
        
        if first_region in country_keywords:
            return "country"
        
        # Check if the region name doesn't look like Turkish province/district names
        # Turkish provinces are usually well-known, so if it's not in search_indexes, 
        # it might be a country name
        if len(first_region) > 4 and first_region not in ['istanbul', 'ankara', 'izmir', 'bursa', 'antalya']:
            # Try country type as fallback for unknown regions
            return "country"
        
        # Default to province
        return "province"
    
    def normalize_query(self, query: str) -> str:
        """Normalize query"""
        return query.strip().lower()
    
    def validate_query(self, query: str) -> bool:
        """Validate query"""
        if not query or not query.strip():
            return False
        
        # Minimum length check
        if len(query.strip()) < 2:
            return False
        
        return True 