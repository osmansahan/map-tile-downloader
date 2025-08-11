#!/usr/bin/env python3
"""
Metadata validation and correction script for TileMapDownloader.

This script checks for inconsistencies between:
1. config.json region definitions and metadata files
2. Actual downloaded tiles and metadata
3. Bbox coordinates in metadata vs config.json
4. Zoom level ranges in metadata vs config.json

It then corrects any found inconsistencies.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime


class MetadataValidator:
    def __init__(self):
        self.project_root = Path.cwd()
        self.config_path = self.project_root / 'config.json'
        self.metadata_dir = self.project_root / 'map_tiles' / 'metadata' / 'regions'
        self.tiles_dir = self.project_root / 'map_tiles'
        
        self.config_data = self._load_config()
        self.issues_found = []
        self.fixes_applied = []
    
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
        except Exception as e:
            print(f"Error loading metadata for {region_name}: {e}")
            return {}
    
    def _save_metadata_file(self, region_name: str, metadata: Dict[str, Any]):
        """Save metadata file for a region"""
        metadata_file = self.metadata_dir / f"{region_name}.json"
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"Updated metadata for {region_name}")
        except Exception as e:
            print(f"Error saving metadata for {region_name}: {e}")
    
    def _scan_actual_tiles(self, region_name: str) -> Dict[str, Any]:
        """Scan actual downloaded tiles for a region"""
        region_tiles_dir = self.tiles_dir / region_name
        if not region_tiles_dir.exists():
            return {}
        
        actual_data = {
            'raster': {},
            'vector': {}
        }
        
        for tile_type_dir in region_tiles_dir.iterdir():
            if tile_type_dir.is_dir() and tile_type_dir.name in ['raster', 'vector']:
                for server_dir in tile_type_dir.iterdir():
                    if server_dir.is_dir():
                        server_name = server_dir.name
                        available_zooms = []
                        tile_count = 0
                        total_size = 0
                        
                        for zoom_dir in server_dir.iterdir():
                            if zoom_dir.is_dir() and zoom_dir.name.isdigit():
                                zoom_level = int(zoom_dir.name)
                                available_zooms.append(zoom_level)
                                
                                for x_dir in zoom_dir.iterdir():
                                    if x_dir.is_dir() and x_dir.name.isdigit():
                                        for tile_file in x_dir.iterdir():
                                            if tile_file.is_file():
                                                tile_count += 1
                                                total_size += tile_file.stat().st_size
                        
                        if available_zooms:
                            actual_data[tile_type_dir.name][server_name] = {
                                'available_zooms': sorted(available_zooms),
                                'tile_count': tile_count,
                                'total_size': total_size,
                                'min_zoom': min(available_zooms),
                                'max_zoom': max(available_zooms)
                            }
        
        return actual_data
    
    def _extract_bbox_from_filename(self, filename: str) -> List[float]:
        """Extract bbox coordinates from filename like 'bbox_30.500_37.000_37.000_41.000.json'"""
        match = re.match(r'bbox_([\d.]+)_([\d.]+)_([\d.]+)_([\d.]+)\.json', filename)
        if match:
            return [float(match.group(1)), float(match.group(2)), 
                   float(match.group(3)), float(match.group(4))]
        return [0, 0, 1, 1]
    
    def validate_bbox_consistency(self):
        """Validate bbox consistency between config.json and metadata files"""
        print("\n=== Validating Bbox Consistency ===")
        
        for region_name in self.config_data.get('regions', {}):
            config_bbox = self.config_data['regions'][region_name].get('bbox', [])
            metadata = self._load_metadata_file(region_name)
            
            if not metadata:
                self.issues_found.append(f"Missing metadata file for {region_name}")
                continue
            
            metadata_bbox = metadata.get('bbox', [])
            
            if config_bbox != metadata_bbox:
                self.issues_found.append(
                    f"Bbox mismatch for {region_name}: config={config_bbox}, metadata={metadata_bbox}"
                )
                # Fix the bbox
                metadata['bbox'] = config_bbox
                self._save_metadata_file(region_name, metadata)
                self.fixes_applied.append(f"Fixed bbox for {region_name}: {config_bbox}")
        
        # Check for orphaned bbox files
        for metadata_file in self.metadata_dir.glob('*.json'):
            region_name = metadata_file.stem
            
            if region_name.startswith('bbox_'):
                # This is a bbox file, check if it has correct coordinates
                metadata = self._load_metadata_file(region_name)
                expected_bbox = self._extract_bbox_from_filename(metadata_file.name)
                actual_bbox = metadata.get('bbox', [])
                
                if actual_bbox != expected_bbox:
                    self.issues_found.append(
                        f"Bbox file {region_name} has incorrect coordinates: "
                        f"expected={expected_bbox}, actual={actual_bbox}"
                    )
                    # Fix the bbox
                    metadata['bbox'] = expected_bbox
                    self._save_metadata_file(region_name, metadata)
                    self.fixes_applied.append(f"Fixed bbox for {region_name}: {expected_bbox}")
    
    def validate_zoom_consistency(self):
        """Validate zoom level consistency between config.json and actual tiles"""
        print("\n=== Validating Zoom Level Consistency ===")
        
        for region_name in self.config_data.get('regions', {}):
            config_region = self.config_data['regions'][region_name]
            config_min_zoom = config_region.get('min_zoom', 0)
            config_max_zoom = config_region.get('max_zoom', 15)
            
            metadata = self._load_metadata_file(region_name)
            if not metadata:
                continue
            
            actual_tiles = self._scan_actual_tiles(region_name)
            
            for tile_type in ['raster', 'vector']:
                for server_name, server_data in metadata.get('layers', {}).get(tile_type, {}).items():
                    metadata_zooms = server_data.get('available_zooms', [])
                    actual_zooms = actual_tiles.get(tile_type, {}).get(server_name, {}).get('available_zooms', [])
                    
                    # Check if metadata zooms match actual tiles
                    if metadata_zooms != actual_zooms:
                        self.issues_found.append(
                            f"Zoom mismatch for {region_name}/{tile_type}/{server_name}: "
                            f"metadata={metadata_zooms}, actual={actual_zooms}"
                        )
                        
                        # Update metadata with actual zoom data
                        if actual_zooms:
                            server_data['available_zooms'] = actual_zooms
                            server_data['min_zoom'] = min(actual_zooms)
                            server_data['max_zoom'] = max(actual_zooms)
                            server_data['tile_count'] = actual_tiles[tile_type][server_name]['tile_count']
                            server_data['total_size'] = actual_tiles[tile_type][server_name]['total_size']
                            server_data['last_updated'] = datetime.now().isoformat()
                            
                            self._save_metadata_file(region_name, metadata)
                            self.fixes_applied.append(
                                f"Updated zoom data for {region_name}/{tile_type}/{server_name}"
                            )
    
    def validate_metadata_completeness(self):
        """Validate that metadata files are complete and up-to-date"""
        print("\n=== Validating Metadata Completeness ===")
        
        for region_name in self.config_data.get('regions', {}):
            metadata = self._load_metadata_file(region_name)
            if not metadata:
                self.issues_found.append(f"Missing metadata file for {region_name}")
                continue
            
            # Check if metadata has required fields
            required_fields = ['name', 'bbox', 'last_updated', 'layers']
            for field in required_fields:
                if field not in metadata:
                    self.issues_found.append(f"Missing field '{field}' in {region_name} metadata")
            
            # Check if layers structure is correct
            layers = metadata.get('layers', {})
            if 'raster' not in layers:
                layers['raster'] = {}
            if 'vector' not in layers:
                layers['vector'] = {}
            
            # Update last_updated timestamp
            metadata['last_updated'] = datetime.now().isoformat()
            self._save_metadata_file(region_name, metadata)
    
    def remove_orphaned_metadata(self):
        """Remove metadata files for regions that don't exist in config.json"""
        print("\n=== Checking for Orphaned Metadata Files ===")
        
        config_regions = set(self.config_data.get('regions', {}).keys())
        
        for metadata_file in self.metadata_dir.glob('*.json'):
            region_name = metadata_file.stem
            
            # Skip bbox files as they might be valid
            if region_name.startswith('bbox_'):
                continue
            
            if region_name not in config_regions:
                print(f"Found orphaned metadata file: {region_name}")
                # Ask user if they want to delete it
                response = input(f"Delete orphaned metadata file {region_name}? (y/N): ")
                if response.lower() == 'y':
                    metadata_file.unlink()
                    print(f"Deleted orphaned metadata file: {region_name}")
    
    def run_validation(self):
        """Run all validation checks"""
        print("Starting metadata validation and correction...")
        
        self.validate_bbox_consistency()
        self.validate_zoom_consistency()
        self.validate_metadata_completeness()
        self.remove_orphaned_metadata()
        
        # Print summary
        print("\n=== Validation Summary ===")
        if self.issues_found:
            print(f"Found {len(self.issues_found)} issues:")
            for issue in self.issues_found:
                print(f"  - {issue}")
        else:
            print("No issues found!")
        
        if self.fixes_applied:
            print(f"\nApplied {len(self.fixes_applied)} fixes:")
            for fix in self.fixes_applied:
                print(f"  {fix}")
        else:
            print("\nNo fixes were needed.")


def main():
    """Main function"""
    validator = MetadataValidator()
    validator.run_validation()


if __name__ == "__main__":
    main()
