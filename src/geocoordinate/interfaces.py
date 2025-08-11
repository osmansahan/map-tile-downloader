from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class CoordinateResult:
    """Coordinate search result data class"""
    success: bool
    region_type: str
    requested_regions: List[str]
    found_regions: List[str]
    not_found: List[str]
    bounding_box: Dict
    center: Dict
    polygon: Dict
    is_contiguous: bool
    error: Optional[str] = None

@dataclass
class SearchSuggestion:
    """Search suggestion data class"""
    name: str
    name_en: str
    type: str
    id: Optional[int] = None

class IDataLoader(ABC):
    """Data loading interface"""
    
    @abstractmethod
    def load_provinces(self) -> any:
        """Load province data"""
        pass
    
    @abstractmethod
    def load_districts(self) -> any:
        """Load district data"""
        pass
    
    @abstractmethod
    def load_metadata(self) -> Dict:
        """Load metadata"""
        pass

class ICoordinateFinder(ABC):
    """Coordinate finding interface"""
    
    @abstractmethod
    def find_coordinates(self, query: str, region_type: str = "auto") -> CoordinateResult:
        """Find coordinates"""
        pass
    
    @abstractmethod
    def search_suggestions(self, partial: str, limit: int = 10) -> List[SearchSuggestion]:
        """Get search suggestions"""
        pass
    
    @abstractmethod
    def get_region_list(self, region_type: str = "province", language: str = "tr") -> List[Dict]:
        """Get region list"""
        pass

class IGeometryProcessor(ABC):
    """Geometry processing interface"""
    
    @abstractmethod
    def extract_polygon_coordinates(self, geometry) -> Dict:
        """Extract polygon coordinates from geometry"""
        pass
    
    @abstractmethod
    def check_contiguity(self, geometries: List) -> bool:
        """Check if geometries are contiguous"""
        pass
    
    @abstractmethod
    def calculate_bounds(self, geometry) -> Dict:
        """Calculate geometry bounds"""
        pass

class IQueryParser(ABC):
    """Query parsing interface"""
    
    @abstractmethod
    def parse_query(self, query: str) -> List[str]:
        """Parse query"""
        pass
    
    @abstractmethod
    def detect_region_type(self, regions: List[str], metadata: Dict) -> str:
        """Detect region type"""
        pass

class ISearchIndex(ABC):
    """Search index interface"""
    
    @abstractmethod
    def find_region(self, name: str, region_type: str) -> Optional[Dict]:
        """Find region"""
        pass
    
    @abstractmethod
    def search_suggestions(self, partial: str, region_type: str = None) -> List[SearchSuggestion]:
        """Get search suggestions"""
        pass 