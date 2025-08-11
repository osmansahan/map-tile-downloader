#!/usr/bin/env python3
"""
Metadata Update Script
Scan existing regions under map_tiles and update metadata
"""

import sys
import os
from pathlib import Path

# Go to project root directory
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
os.chdir(project_root)

# Add src to path
sys.path.insert(0, os.path.join(project_root, 'src'))

from utils.metadata_manager import metadata_manager

def update_metadata():
    """Scan existing regions and update metadata"""
    print("=== Map Tiles Metadata Updater ===")
    print(f"Çalışma dizini: {os.getcwd()}")
    print(f"Map tiles dizini: {metadata_manager.map_tiles_dir}")
    print()
    
    # Mevcut region'ları tara
    print("Mevcut region'lar taranıyor...")
    metadata_manager.scan_existing_regions()
    
    # Özet bilgileri göster
    print("\n=== Metadata Özeti ===")
    regions = metadata_manager.list_regions()
    print(f"Toplam Region: {len(regions)}")
    
    total_layers = 0
    total_tiles = 0
    total_size = 0
    
    for region_name in regions:
        region_info = metadata_manager.get_region_info(region_name)
        if region_info:
            print(f"\n{region_name}:")
            print(f"  BBOX: {region_info.bbox}")
            print(f"  Son Güncelleme: {region_info.last_updated}")
            
            for layer_type, layers in region_info.layers.items():
                if layers:
                    print(f"  {layer_type.upper()} Layers:")
                    for layer_name, layer_info in layers.items():
                        print(f"    - {layer_name}: {layer_info.tile_count} tiles, zoom {layer_info.min_zoom}-{layer_info.max_zoom}")
                        total_layers += 1
                        total_tiles += layer_info.tile_count
                        total_size += layer_info.total_size
    
    print(f"\nToplam Layer: {total_layers}")
    print(f"Toplam Tile: {total_tiles:,}")
    print(f"Toplam Boyut: {round(total_size / (1024 * 1024), 2)} MB")
    
    print("\nMetadata başarıyla güncellendi!")
    print(f"Metadata dizini: {metadata_manager.regions_dir}")

if __name__ == "__main__":
    update_metadata()
