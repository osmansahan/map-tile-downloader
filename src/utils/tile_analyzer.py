from typing import List, Tuple, Dict, Any
from utils.tile_calculator import TileCalculator


class TileAnalyzer:
    """Utility class for analyzing tile requirements and existing tiles"""
    
    @staticmethod
    def analyze_region_tiles(bbox: List[float], zoom: int) -> Dict[str, Any]:
        """Analyze tile requirements for a region at specific zoom level"""
        min_x, max_y = TileCalculator.deg2num(bbox[1], bbox[0], zoom)
        max_x, min_y = TileCalculator.deg2num(bbox[3], bbox[2], zoom)
        
        x_range = list(range(min_x, max_x + 1))
        y_range = list(range(min_y, max_y + 1))
        total_tiles = len(x_range) * len(y_range)
        
        return {
            'zoom': zoom,
            'x_range': {'min': min_x, 'max': max_x, 'count': len(x_range)},
            'y_range': {'min': min_y, 'max': max_y, 'count': len(y_range)},
            'total_tiles': total_tiles,
            'x_coordinates': x_range,
            'y_coordinates': y_range
        }
    
    @staticmethod
    def compare_bbox_tiles(config_bbox: List[float], index_bbox: List[float], 
                          zoom: int) -> Dict[str, Any]:
        """Compare tile requirements between config and index bboxes"""
        config_analysis = TileAnalyzer.analyze_region_tiles(config_bbox, zoom)
        index_analysis = TileAnalyzer.analyze_region_tiles(index_bbox, zoom)
        
        # Check for missing tiles
        config_y_range = set(config_analysis['y_coordinates'])
        index_y_range = set(index_analysis['y_coordinates'])
        missing_y_tiles = index_y_range - config_y_range
        
        return {
            'config_analysis': config_analysis,
            'index_analysis': index_analysis,
            'missing_y_tiles': sorted(list(missing_y_tiles)),
            'has_missing_tiles': len(missing_y_tiles) > 0,
            'compatibility': len(missing_y_tiles) == 0
        }
    
    @staticmethod
    def analyze_existing_tiles(existing_x_range: List[int], existing_y_range: List[int],
                             required_x_range: List[int], required_y_range: List[int]) -> Dict[str, Any]:
        """Analyze existing tiles against required tiles"""
        existing_x_set = set(existing_x_range)
        existing_y_set = set(existing_y_range)
        required_x_set = set(required_x_range)
        required_y_set = set(required_y_range)
        
        missing_x = required_x_set - existing_x_set
        missing_y = required_y_set - existing_y_set
        
        return {
            'existing_x_count': len(existing_x_set),
            'existing_y_count': len(existing_y_set),
            'required_x_count': len(required_x_set),
            'required_y_count': len(required_y_set),
            'missing_x_tiles': sorted(list(missing_x)),
            'missing_y_tiles': sorted(list(missing_y)),
            'coverage_percentage': {
                'x': (len(existing_x_set) / len(required_x_set)) * 100 if required_x_set else 0,
                'y': (len(existing_y_set) / len(required_y_set)) * 100 if required_y_set else 0
            },
            'is_complete': len(missing_x) == 0 and len(missing_y) == 0
        } 