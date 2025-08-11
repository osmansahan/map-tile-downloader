#!/usr/bin/env python3
"""
Quick metadata status checker for TileMapDownloader.

This script provides a quick overview of metadata health across all regions.
"""

import json
from pathlib import Path
from typing import Dict, Any


class MetadataStatusChecker:
    def __init__(self):
        self.project_root = Path.cwd()
        self.config_path = self.project_root / 'config.json'
        self.metadata_dir = self.project_root / 'map_tiles' / 'metadata' / 'regions'
        
        self.config_data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load config.json file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}")
            return {}
    
    def _load_metadata_file(self, region_name: str) -> Dict[str, Any]:
        """Load metadata file for a region"""
        metadata_file = self.metadata_dir / f"{region_name}.json"
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def check_status(self):
        """Check metadata status for all regions"""
        print("=== Metadata Status Report ===\n")
        
        config_regions = self.config_data.get('regions', {})
        metadata_files = list(self.metadata_dir.glob('*.json'))
        
        print(f"Config regions: {len(config_regions)}")
        print(f"Metadata files: {len(metadata_files)}")
        print()
        
        # Check config regions
        print("Config Regions:")
        for region_name, region_data in config_regions.items():
            bbox = region_data.get('bbox', [])
            min_zoom = region_data.get('min_zoom', 'N/A')
            max_zoom = region_data.get('max_zoom', 'N/A')
            
            metadata = self._load_metadata_file(region_name)
            status = "OK" if metadata else "X"
            
            print(f"  {status} {region_name}: bbox={bbox}, zoom={min_zoom}-{max_zoom}")
        
        print()
        
        # Check metadata files
        print("Metadata Files:")
        for metadata_file in sorted(metadata_files):
            region_name = metadata_file.stem
            metadata = self._load_metadata_file(region_name)
            
            if metadata:
                bbox = metadata.get('bbox', [])
                layers = metadata.get('layers', {})
                raster_count = len(layers.get('raster', {}))
                vector_count = len(layers.get('vector', {}))
                
                status = "OK" if region_name in config_regions else "?"
                print(f"  {status} {region_name}: bbox={bbox}, layers={raster_count}r/{vector_count}v")
            else:
                print(f"  X {region_name}: Error reading file")
        
        print()
        
        # Summary
        missing_metadata = [name for name in config_regions if not self._load_metadata_file(name)]
        orphaned_metadata = [f.stem for f in metadata_files if f.stem not in config_regions and not f.stem.startswith('bbox_')]
        
        if missing_metadata:
            print(f"Missing metadata files: {missing_metadata}")
        
        if orphaned_metadata:
            print(f"Orphaned metadata files: {orphaned_metadata}")
        
        if not missing_metadata and not orphaned_metadata:
            print("All metadata files are properly synchronized!")


def main():
    """Main function"""
    checker = MetadataStatusChecker()
    checker.check_status()


if __name__ == "__main__":
    main()
