from typing import List, Dict
from .interfaces import ICoordinateFinder, CoordinateResult, SearchSuggestion
from .data_loader import GeoJSONDataLoader
from .geometry_processor import ShapelyGeometryProcessor
from .query_parser import QueryParser
from .search_index import MetadataSearchIndex

class FastCoordinateFinder(ICoordinateFinder):
    """Fast coordinate finder (SOLID principles compliant)"""
    
    def __init__(self, data_dir: str = "data"):
        # Dependency Injection
        self.data_loader = GeoJSONDataLoader(data_dir)
        self.geometry_processor = ShapelyGeometryProcessor()
        self.query_parser = QueryParser()
        self.search_index = None  # Lazy loading
        
        # Cache
        self._provinces_data = None
        self._districts_data = None
        self._countries_data = None
    
    def _get_search_index(self) -> MetadataSearchIndex:
        """Get search index with lazy loading"""
        if self.search_index is None:
            metadata = self.data_loader.load_metadata()
            self.search_index = MetadataSearchIndex(metadata)
        return self.search_index
    
    def _get_provinces_data(self):
        """Get provinces data with lazy loading"""
        if self._provinces_data is None:
            self._provinces_data = self.data_loader.load_provinces()
        return self._provinces_data
    
    def _get_districts_data(self):
        """Get districts data with lazy loading"""
        if self._districts_data is None:
            self._districts_data = self.data_loader.load_districts()
        return self._districts_data
    
    def _get_countries_data(self):
        """Get countries data with lazy loading"""
        if self._countries_data is None:
            self._countries_data = self.data_loader.load_countries()
        return self._countries_data
    
    def find_coordinates(self, query: str, region_type: str = "auto") -> CoordinateResult:
        """Find coordinates (optimized)"""
        try:
            # Query validation
            if not self.query_parser.validate_query(query):
                return CoordinateResult(
                    success=False,
                    region_type="",
                    requested_regions=[],
                    found_regions=[],
                    not_found=[],
                    bounding_box={},
                    center={},
                    polygon={},
                    is_contiguous=False,
                    error="Invalid query"
                )
            
            # Query parsing
            regions = self.query_parser.parse_query(query)
            if not regions:
                return CoordinateResult(
                    success=False,
                    region_type="",
                    requested_regions=[],
                    found_regions=[],
                    not_found=[],
                    bounding_box={},
                    center={},
                    polygon={},
                    is_contiguous=False,
                    error="Query could not be parsed"
                )
            
            # Region type detection
            if region_type == "auto":
                metadata = self.data_loader.load_metadata()
                region_type = self.query_parser.detect_region_type(regions, metadata)
            
            # Find regions
            found_regions, not_found = self._find_regions(regions, region_type)
            
            if not found_regions:
                return CoordinateResult(
                    success=False,
                    region_type=region_type,
                    requested_regions=regions,
                    found_regions=[],
                    not_found=not_found,
                    bounding_box={},
                    center={},
                    polygon={},
                    is_contiguous=False,
                    error=f"No regions found: {regions}"
                )
            
            # Combine geometries
            combined_geometry = self._combine_geometries(found_regions)
            
            # Calculate results
            bounds = self.geometry_processor.calculate_bounds(combined_geometry)
            polygon_coords = self.geometry_processor.extract_polygon_coordinates(combined_geometry)
            is_contiguous = self.geometry_processor.check_contiguity([r.geometry for r in found_regions])
            
            # Get the correct name column based on region type
            if region_type == "country":
                found_region_names = [r["adm0_name"] for r in found_regions]
            else:
                found_region_names = [r["feature_name"] for r in found_regions]
            
            return CoordinateResult(
                success=True,
                region_type=region_type,
                requested_regions=regions,
                found_regions=found_region_names,
                not_found=not_found,
                bounding_box=bounds,
                center=bounds["center"],
                polygon=polygon_coords,
                is_contiguous=is_contiguous
            )
            
        except Exception as e:
            return CoordinateResult(
                success=False,
                region_type="",
                requested_regions=[],
                found_regions=[],
                not_found=[],
                bounding_box={},
                center={},
                polygon={},
                is_contiguous=False,
                error=f"Coordinate finding error: {str(e)}"
            )
    
    def _find_regions(self, regions: List[str], region_type: str) -> tuple:
        """Find regions"""
        found_regions = []
        not_found = []
        
        search_index = self._get_search_index()
        
        if region_type == "province":
            data = self._get_provinces_data()
            name_column = "feature_name"
        elif region_type == "district":
            data = self._get_districts_data()
            name_column = "feature_name"
        elif region_type == "country":
            data = self._get_countries_data()
            name_column = "adm0_name"
        else:
            return [], regions
        
        for name in regions:
            name_lower = name.lower()
            
            # For countries, do direct search since there's no search index
            if region_type == "country":
                mask = data[name_column].str.lower() == name_lower
                if mask.any():
                    found_regions.append(data[mask].iloc[0])
                else:
                    not_found.append(name)
                continue
            
            # For provinces and districts, use search index first
            region_info = search_index.find_region(name_lower, region_type)
            if region_info:
                region_id = region_info["id"]
                mask = data.iloc[:, 0] == region_id
                if mask.any():
                    found_regions.append(data[mask].iloc[0])
                    continue
            
            # Then direct search
            mask = data[name_column].str.lower() == name_lower
            if mask.any():
                found_regions.append(data[mask].iloc[0])
            else:
                not_found.append(name)
        
        return found_regions, not_found
    
    def _combine_geometries(self, regions) -> any:
        """Combine geometries"""
        if not regions:
            return None
        
        combined = regions[0].geometry
        for region in regions[1:]:
            combined = combined.union(region.geometry)
        
        return combined
    
    def search_suggestions(self, partial: str, limit: int = 10) -> List[SearchSuggestion]:
        """Get search suggestions"""
        try:
            search_index = self._get_search_index()
            suggestions = search_index.search_suggestions(partial)
            return suggestions[:limit]
        except Exception as e:
            return []
    
    def get_region_list(self, region_type: str = "province", language: str = "tr") -> List[Dict]:
        """Get region list"""
        try:
            search_index = self._get_search_index()
            regions = search_index.get_all_regions(region_type)
            
            # Language selection
            if language == "en":
                for region in regions:
                    region["name"] = region["name_en"]
            
            return sorted(regions, key=lambda x: x["name"])
        except Exception as e:
            return []
    
    def get_performance_info(self) -> Dict:
        """Get performance information"""
        try:
            data_info = self.data_loader.get_data_info()
            search_index = self._get_search_index()
            
            return {
                "data_info": data_info,
                "search_index": {
                    "provinces_count": search_index.get_region_count("province"),
                    "districts_count": search_index.get_region_count("district"),
                    "countries_count": search_index.get_region_count("country")
                },
                "cache_status": {
                    "provinces_loaded": self._provinces_data is not None,
                    "districts_loaded": self._districts_data is not None,
                    "countries_loaded": self._countries_data is not None,
                    "search_index_loaded": self.search_index is not None
                }
            }
        except Exception as e:
            return {"error": str(e)} 