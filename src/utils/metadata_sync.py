import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
import logging
from collections import defaultdict

class MetadataSynchronizer:
    """
    Comprehensive metadata synchronization system for TileMapDownloader.
    
    This class handles:
    1. Auditing existing metadata against filesystem structure
    2. Synchronizing metadata with actual tile directories
    3. Handling special cases like turkiye region structure
    4. Calculating accurate tile counts and sizes
    5. Cleaning up orphaned metadata entries
    """
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.map_tiles_dir = self.base_dir / "map_tiles"
        self.metadata_dir = self.map_tiles_dir / "metadata" / "regions"
        
        # Ensure directories exist
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Load config for bbox info
        self.config_data = self._load_config()
        
        # Statistics tracking
        self.sync_stats = {
            'regions_synced': 0,
            'layers_added': 0,
            'layers_updated': 0,
            'layers_removed': 0,
            'total_tiles_counted': 0,
            'total_size_calculated': 0,
            'errors': []
        }
    
    def _setup_logging(self):
        """Setup logging for sync operations"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('MetadataSync')
    
    def _load_config(self) -> Dict[str, Any]:
        """Load config.json for bbox information"""
        config_path = self.base_dir / "config.json"
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load config.json: {e}")
        return {}
    
    def sync_all_metadata(self) -> Dict[str, Any]:
        """
        Main synchronization method.
        Performs complete metadata sync for all regions.
        """
        self.logger.info("Starting comprehensive metadata synchronization...")
        
        # Reset stats
        self.sync_stats = {
            'regions_synced': 0,
            'layers_added': 0,
            'layers_updated': 0,
            'layers_removed': 0,
            'total_tiles_counted': 0,
            'total_size_calculated': 0,
            'errors': [],
            'start_time': datetime.now().isoformat()
        }
        
        try:
            # Step 1: Get all regions from filesystem
            filesystem_regions = self._discover_filesystem_regions()
            self.logger.info(f"Discovered {len(filesystem_regions)} regions in filesystem")
            
            # Step 2: Get all regions from existing metadata
            metadata_regions = self._discover_metadata_regions()
            self.logger.info(f"Found {len(metadata_regions)} regions in metadata")
            
            # Step 3: Sync each filesystem region
            for region_name in filesystem_regions:
                try:
                    self._sync_region(region_name)
                    self.sync_stats['regions_synced'] += 1
                except Exception as e:
                    error_msg = f"Failed to sync region {region_name}: {e}"
                    self.logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            # Step 4: Remove orphaned metadata (regions that no longer exist in filesystem)
            orphaned_regions = metadata_regions - filesystem_regions
            for region_name in orphaned_regions:
                try:
                    self._remove_orphaned_region_metadata(region_name)
                except Exception as e:
                    error_msg = f"Failed to remove orphaned metadata for {region_name}: {e}"
                    self.logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            # Step 5: Generate summary
            self.sync_stats['end_time'] = datetime.now().isoformat()
            self.sync_stats['success'] = True
            
            self.logger.info("Metadata synchronization completed successfully")
            self._log_sync_summary()
            
        except Exception as e:
            self.sync_stats['end_time'] = datetime.now().isoformat()
            self.sync_stats['success'] = False
            self.sync_stats['errors'].append(f"Critical sync error: {e}")
            self.logger.error(f"Critical sync error: {e}")
        
        return self.sync_stats
    
    def _discover_filesystem_regions(self) -> Set[str]:
        """Discover all regions present in the filesystem"""
        regions = set()
        
        if not self.map_tiles_dir.exists():
            self.logger.warning("map_tiles directory does not exist")
            return regions
        
        for item in self.map_tiles_dir.iterdir():
            if (item.is_dir() and 
                item.name != 'metadata' and 
                not item.name.startswith('.')):
                
                # Verify it has tile directories (raster or vector subdirs)
                has_tiles = self._has_tile_structure(item)
                if has_tiles:
                    regions.add(item.name)
                else:
                    self.logger.debug(f"Skipping {item.name} - no tile structure found")
        
        return regions
    
    def _has_tile_structure(self, region_path: Path) -> bool:
        """Check if region directory has proper tile structure"""
        # Check for raster or vector subdirectories
        raster_dir = region_path / "raster"
        vector_dir = region_path / "vector"
        
        has_raster = raster_dir.exists() and any(raster_dir.iterdir())
        has_vector = vector_dir.exists() and any(vector_dir.iterdir())
        
        # Special case: turkiye has direct zoom folders in raster
        if region_path.name == "turkiye":
            direct_raster = raster_dir.exists() and any(
                item.is_dir() and item.name.isdigit() 
                for item in raster_dir.iterdir()
            )
            return direct_raster or has_vector
        
        return has_raster or has_vector
    
    def _discover_metadata_regions(self) -> Set[str]:
        """Discover all regions present in metadata files"""
        regions = set()
        
        if not self.metadata_dir.exists():
            return regions
        
        for metadata_file in self.metadata_dir.glob("*.json"):
            regions.add(metadata_file.stem)
        
        return regions
    
    def _sync_region(self, region_name: str):
        """Synchronize metadata for a specific region"""
        self.logger.info(f"Syncing region: {region_name}")
        
        region_path = self.map_tiles_dir / region_name
        if not region_path.exists():
            self.logger.warning(f"Region path does not exist: {region_path}")
            return
        
        # Load existing metadata
        existing_metadata = self._load_region_metadata(region_name)
        
        # Scan filesystem for actual layers
        filesystem_layers = self._scan_region_filesystem(region_name)
        
        # Build new metadata structure
        new_metadata = self._build_region_metadata(
            region_name, filesystem_layers, existing_metadata
        )
        
        # Compare and update
        changes = self._compare_metadata(existing_metadata, new_metadata)
        if changes['has_changes']:
            self._save_region_metadata(region_name, new_metadata)
            self.logger.info(f"Region {region_name} metadata updated: {changes}")
        else:
            self.logger.info(f"Region {region_name} metadata is up-to-date")
    
    def _load_region_metadata(self, region_name: str) -> Optional[Dict[str, Any]]:
        """Load existing metadata for a region"""
        metadata_file = self.metadata_dir / f"{region_name}.json"
        
        try:
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load metadata for {region_name}: {e}")
        
        return None
    
    def _scan_region_filesystem(self, region_name: str) -> Dict[str, Dict[str, Any]]:
        """Scan filesystem structure for a region and return layer information"""
        region_path = self.map_tiles_dir / region_name
        layers = {'raster': {}, 'vector': {}}
        
        # Handle special case: turkiye region
        if region_name == "turkiye":
            return self._scan_turkiye_special_structure(region_path)
        
        # Standard structure: region/raster|vector/layer_name/zoom/x/y.ext
        for tile_type in ['raster', 'vector']:
            type_dir = region_path / tile_type
            if type_dir.exists():
                for layer_dir in type_dir.iterdir():
                    if layer_dir.is_dir():
                        layer_info = self._scan_layer_directory(layer_dir, tile_type)
                        if layer_info:
                            layers[tile_type][layer_dir.name] = layer_info
        
        return layers
    
    def _scan_turkiye_special_structure(self, region_path: Path) -> Dict[str, Dict[str, Any]]:
        """Handle turkiye's special structure: region/raster/zoom/x/y.ext"""
        layers = {'raster': {}, 'vector': {}}
        
        raster_dir = region_path / "raster"
        if raster_dir.exists():
            # In turkiye, zoom folders are directly under raster/
            available_zooms = []
            tile_count = 0
            total_size = 0
            
            for zoom_dir in raster_dir.iterdir():
                if zoom_dir.is_dir() and zoom_dir.name.isdigit():
                    zoom_level = int(zoom_dir.name)
                    available_zooms.append(zoom_level)
                    
                    # Count tiles in this zoom level
                    zoom_tile_count, zoom_size = self._count_tiles_in_zoom(zoom_dir)
                    tile_count += zoom_tile_count
                    total_size += zoom_size
            
            if available_zooms:
                layers['raster']['turkiye_raster'] = {
                    'name': 'turkiye_raster',
                    'type': 'raster',
                    'min_zoom': min(available_zooms),
                    'max_zoom': max(available_zooms),
                    'tile_count': tile_count,
                    'total_size': total_size,
                    'available_zooms': sorted(available_zooms),
                    'last_updated': datetime.now().isoformat()
                }
        
        # Handle vector if it exists (standard structure)
        vector_dir = region_path / "vector"
        if vector_dir.exists():
            for layer_dir in vector_dir.iterdir():
                if layer_dir.is_dir():
                    layer_info = self._scan_layer_directory(layer_dir, 'vector')
                    if layer_info:
                        layers['vector'][layer_dir.name] = layer_info
        
        return layers
    
    def _scan_layer_directory(self, layer_path: Path, tile_type: str) -> Optional[Dict[str, Any]]:
        """Scan a layer directory and return layer information"""
        if not layer_path.exists():
            return None
        
        available_zooms = []
        tile_count = 0
        total_size = 0
        
        for zoom_dir in layer_path.iterdir():
            if zoom_dir.is_dir() and zoom_dir.name.isdigit():
                zoom_level = int(zoom_dir.name)
                available_zooms.append(zoom_level)
                
                # Count tiles in this zoom level
                zoom_tile_count, zoom_size = self._count_tiles_in_zoom(zoom_dir)
                tile_count += zoom_tile_count
                total_size += zoom_size
        
        if not available_zooms:
            return None
        
        return {
            'name': layer_path.name,
            'type': tile_type,
            'min_zoom': min(available_zooms),
            'max_zoom': max(available_zooms),
            'tile_count': tile_count,
            'total_size': total_size,
            'available_zooms': sorted(available_zooms),
            'last_updated': datetime.now().isoformat()
        }
    
    def _count_tiles_in_zoom(self, zoom_dir: Path) -> Tuple[int, int]:
        """Count tiles and calculate total size for a zoom directory"""
        tile_count = 0
        total_size = 0
        
        try:
            for x_dir in zoom_dir.iterdir():
                if x_dir.is_dir() and x_dir.name.isdigit():
                    for tile_file in x_dir.iterdir():
                        if tile_file.is_file() and not tile_file.name.startswith('.'):
                            tile_count += 1
                            try:
                                total_size += tile_file.stat().st_size
                            except OSError:
                                pass  # File might be inaccessible
        except Exception as e:
            self.logger.warning(f"Error counting tiles in {zoom_dir}: {e}")
        
        return tile_count, total_size
    
    def _build_region_metadata(self, region_name: str, filesystem_layers: Dict[str, Dict[str, Any]], 
                              existing_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build complete metadata structure for a region"""
        
        # Get bbox from config or existing metadata
        bbox = None
        if existing_metadata and 'bbox' in existing_metadata:
            bbox = existing_metadata['bbox']
        elif 'regions' in self.config_data and region_name in self.config_data['regions']:
            bbox = self.config_data['regions'][region_name].get('bbox')
        
        # Default bbox if none found
        if not bbox:
            bbox = [0.0, 0.0, 1.0, 1.0]
            self.logger.warning(f"No bbox found for {region_name}, using default")
        
        return {
            'name': region_name,
            'bbox': bbox,
            'last_updated': datetime.now().isoformat(),
            'layers': filesystem_layers
        }
    
    def _compare_metadata(self, existing: Optional[Dict[str, Any]], 
                         new: Dict[str, Any]) -> Dict[str, Any]:
        """Compare existing and new metadata to detect changes"""
        changes = {
            'has_changes': False,
            'layers_added': [],
            'layers_updated': [],
            'layers_removed': [],
            'bbox_changed': False
        }
        
        if not existing:
            changes['has_changes'] = True
            return changes
        
        # Check bbox changes
        if existing.get('bbox') != new.get('bbox'):
            changes['bbox_changed'] = True
            changes['has_changes'] = True
        
        # Compare layers
        existing_layers = existing.get('layers', {'raster': {}, 'vector': {}})
        new_layers = new.get('layers', {'raster': {}, 'vector': {}})
        
        for tile_type in ['raster', 'vector']:
            existing_type_layers = existing_layers.get(tile_type, {})
            new_type_layers = new_layers.get(tile_type, {})
            
            # Find added layers
            for layer_name in new_type_layers:
                if layer_name not in existing_type_layers:
                    changes['layers_added'].append(f"{tile_type}/{layer_name}")
                    changes['has_changes'] = True
                    self.sync_stats['layers_added'] += 1
            
            # Find removed layers
            for layer_name in existing_type_layers:
                if layer_name not in new_type_layers:
                    changes['layers_removed'].append(f"{tile_type}/{layer_name}")
                    changes['has_changes'] = True
                    self.sync_stats['layers_removed'] += 1
            
            # Find updated layers
            for layer_name in new_type_layers:
                if layer_name in existing_type_layers:
                    existing_layer = existing_type_layers[layer_name]
                    new_layer = new_type_layers[layer_name]
                    
                    # Compare key fields
                    key_fields = ['tile_count', 'total_size', 'available_zooms', 'min_zoom', 'max_zoom']
                    for field in key_fields:
                        if existing_layer.get(field) != new_layer.get(field):
                            changes['layers_updated'].append(f"{tile_type}/{layer_name}")
                            changes['has_changes'] = True
                            self.sync_stats['layers_updated'] += 1
                            break
        
        return changes
    
    def _save_region_metadata(self, region_name: str, metadata: Dict[str, Any]):
        """Save metadata for a region"""
        metadata_file = self.metadata_dir / f"{region_name}.json"
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved metadata for region: {region_name}")
            
            # Update stats
            for tile_type, layers in metadata.get('layers', {}).items():
                for layer_info in layers.values():
                    self.sync_stats['total_tiles_counted'] += layer_info.get('tile_count', 0)
                    self.sync_stats['total_size_calculated'] += layer_info.get('total_size', 0)
            
        except Exception as e:
            error_msg = f"Failed to save metadata for {region_name}: {e}"
            self.logger.error(error_msg)
            self.sync_stats['errors'].append(error_msg)
    
    def _remove_orphaned_region_metadata(self, region_name: str):
        """Remove metadata for regions that no longer exist in filesystem"""
        metadata_file = self.metadata_dir / f"{region_name}.json"
        
        if metadata_file.exists():
            try:
                metadata_file.unlink()
                self.logger.info(f"Removed orphaned metadata for region: {region_name}")
            except Exception as e:
                error_msg = f"Failed to remove orphaned metadata for {region_name}: {e}"
                self.logger.error(error_msg)
                self.sync_stats['errors'].append(error_msg)
    
    def _log_sync_summary(self):
        """Log a summary of the synchronization process"""
        stats = self.sync_stats
        
        self.logger.info("=" * 60)
        self.logger.info("METADATA SYNCHRONIZATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Regions synced: {stats['regions_synced']}")
        self.logger.info(f"Layers added: {stats['layers_added']}")
        self.logger.info(f"Layers updated: {stats['layers_updated']}")
        self.logger.info(f"Layers removed: {stats['layers_removed']}")
        self.logger.info(f"Total tiles counted: {stats['total_tiles_counted']:,}")
        self.logger.info(f"Total size calculated: {stats['total_size_calculated'] / (1024*1024):.2f} MB")
        
        if stats['errors']:
            self.logger.info(f"Errors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                self.logger.error(f"  - {error}")
        else:
            self.logger.info("No errors encountered")
        
        self.logger.info("=" * 60)
    
    def audit_metadata_consistency(self) -> Dict[str, Any]:
        """
        Audit existing metadata for consistency issues.
        Returns a report of inconsistencies found.
        """
        self.logger.info("Starting metadata consistency audit...")
        
        audit_report = {
            'timestamp': datetime.now().isoformat(),
            'regions_audited': 0,
            'inconsistencies': {
                'missing_layers': [],
                'extra_layers': [],
                'incorrect_counts': [],
                'missing_zoom_levels': [],
                'bbox_issues': []
            },
            'recommendations': []
        }
        
        # Get all regions
        filesystem_regions = self._discover_filesystem_regions()
        metadata_regions = self._discover_metadata_regions()
        
        # Check each region
        for region_name in filesystem_regions.union(metadata_regions):
            region_issues = self._audit_region_consistency(region_name)
            audit_report['regions_audited'] += 1
            
            for issue_type, issues in region_issues.items():
                if issues:
                    audit_report['inconsistencies'][issue_type].extend(issues)
        
        # Generate recommendations
        if any(audit_report['inconsistencies'].values()):
            audit_report['recommendations'].append("Run sync_all_metadata() to fix inconsistencies")
        
        self.logger.info(f"Audit completed. Found issues in {len([r for issues in audit_report['inconsistencies'].values() for r in issues])} areas")
        
        return audit_report
    
    def _audit_region_consistency(self, region_name: str) -> Dict[str, List[str]]:
        """Audit consistency for a specific region"""
        issues = {
            'missing_layers': [],
            'extra_layers': [],
            'incorrect_counts': [],
            'missing_zoom_levels': [],
            'bbox_issues': []
        }
        
        filesystem_regions = self._discover_filesystem_regions()
        metadata_regions = self._discover_metadata_regions()
        
        # Check if region exists in filesystem but not metadata
        if region_name in filesystem_regions and region_name not in metadata_regions:
            issues['missing_layers'].append(f"Region {region_name} exists in filesystem but has no metadata")
            return issues
        
        # Check if region exists in metadata but not filesystem
        if region_name not in filesystem_regions and region_name in metadata_regions:
            issues['extra_layers'].append(f"Region {region_name} has metadata but does not exist in filesystem")
            return issues
        
        # If region exists in both, compare layers
        both_regions = filesystem_regions.intersection(metadata_regions)
        if region_name in both_regions:
            filesystem_layers = self._scan_region_filesystem(region_name)
            metadata = self._load_region_metadata(region_name)
            
            if metadata:
                metadata_layers = metadata.get('layers', {'raster': {}, 'vector': {}})
                
                for tile_type in ['raster', 'vector']:
                    fs_layers = set(filesystem_layers.get(tile_type, {}).keys())
                    md_layers = set(metadata_layers.get(tile_type, {}).keys())
                    
                    # Missing layers in metadata
                    missing = fs_layers - md_layers
                    for layer in missing:
                        issues['missing_layers'].append(f"{region_name}/{tile_type}/{layer}")
                    
                    # Extra layers in metadata
                    extra = md_layers - fs_layers
                    for layer in extra:
                        issues['extra_layers'].append(f"{region_name}/{tile_type}/{layer}")
                    
                    # Check counts for existing layers
                    for layer in fs_layers.intersection(md_layers):
                        fs_info = filesystem_layers[tile_type][layer]
                        md_info = metadata_layers[tile_type][layer]
                        
                        if fs_info['tile_count'] != md_info.get('tile_count', 0):
                            issues['incorrect_counts'].append(
                                f"{region_name}/{tile_type}/{layer}: "
                                f"filesystem={fs_info['tile_count']} vs metadata={md_info.get('tile_count', 0)}"
                            )
        
        return issues


def sync_metadata_on_startup(base_dir: str = ".") -> Dict[str, Any]:
    """
    Convenience function to run metadata sync on server startup.
    
    Args:
        base_dir: Base directory of the project
        
    Returns:
        Dictionary containing sync results and statistics
    """
    synchronizer = MetadataSynchronizer(base_dir)
    return synchronizer.sync_all_metadata()


def audit_metadata_consistency(base_dir: str = ".") -> Dict[str, Any]:
    """
    Convenience function to audit metadata consistency.
    
    Args:
        base_dir: Base directory of the project
        
    Returns:
        Dictionary containing audit report
    """
    synchronizer = MetadataSynchronizer(base_dir)
    return synchronizer.audit_metadata_consistency()


if __name__ == "__main__":
    # Run sync if called directly
    import sys
    
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Run audit first
    print("Running metadata consistency audit...")
    audit_report = audit_metadata_consistency(base_dir)
    
    if any(audit_report['inconsistencies'].values()):
        print("Inconsistencies found. Running synchronization...")
        sync_results = sync_metadata_on_startup(base_dir)
        print(f"Sync completed. {sync_results['regions_synced']} regions processed.")
    else:
        print("No inconsistencies found. Metadata is in sync.")