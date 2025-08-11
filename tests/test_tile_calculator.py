#!/usr/bin/env python3
"""
Tests for TileCalculator utility
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from utils.tile_calculator import TileCalculator


class TestTileCalculator:
    """Test cases for TileCalculator class"""
    
    def test_deg2num(self):
        """Test coordinate conversion"""
        # Test known coordinates
        lat, lon = 40.7128, -74.0060  # New York
        zoom = 10
        
        x, y = TileCalculator.deg2num(lat, lon, zoom)
        
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert x >= 0
        assert y >= 0
    
    def test_get_tiles_for_bbox(self):
        """Test bbox tile calculation"""
        bbox = [28.5, 40.8, 29.5, 41.2]  # Istanbul
        min_zoom = 10
        max_zoom = 12
        
        tiles = TileCalculator.get_tiles_for_bbox(bbox, min_zoom, max_zoom)
        
        assert isinstance(tiles, list)
        assert len(tiles) > 0
        
        for tile in tiles:
            assert len(tile) == 3
            zoom, x, y = tile
            assert min_zoom <= zoom <= max_zoom
            assert isinstance(x, int)
            assert isinstance(y, int)
    
    def test_calculate_tile_count(self):
        """Test tile count calculation"""
        bbox = [28.5, 40.8, 29.5, 41.2]
        min_zoom = 10
        max_zoom = 10
        
        count = TileCalculator.calculate_tile_count(bbox, min_zoom, max_zoom)
        
        assert isinstance(count, int)
        assert count > 0
    
    def test_edge_cases(self):
        """Test edge cases"""
        # Zero zoom
        x, y = TileCalculator.deg2num(0, 0, 0)
        assert x == 0
        assert y == 0
        
        # Maximum zoom
        x, y = TileCalculator.deg2num(0, 0, 20)
        assert x >= 0
        assert y >= 0


if __name__ == "__main__":
    pytest.main([__file__]) 