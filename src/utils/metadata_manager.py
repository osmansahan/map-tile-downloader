import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import re
import sys

# Geocoordinate API import
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from geocoordinate.api import get_region_data
except ImportError:
    def get_region_data(region_name):
        """Fallback function if geocoordinate API not available"""
        return None


@dataclass
class TileLayerInfo:
    """Tile layer info"""
    name: str
    type: str  # 'raster' or 'vector'
    min_zoom: int
    max_zoom: int
    tile_count: int
    total_size: int
    last_updated: str
    available_zooms: List[int]


@dataclass
class RegionInfo:
    """Region info"""
    name: str
    bbox: List[float]
    center: List[float]  # [lng, lat] from geocoordinate API
    layers: Dict[str, Dict[str, TileLayerInfo]]  # type -> {name -> TileLayerInfo}
    last_updated: str


class MetadataManager:
    """Map tiles metadata manager - ultra fast"""
    
    def __init__(self, map_tiles_dir: str = "map_tiles"):
        # Use absolute path
        current_dir = Path.cwd()
        self.map_tiles_dir = current_dir / map_tiles_dir
        self.metadata_dir = self.map_tiles_dir / "metadata"
        
        # Create directories
        try:
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Metadata dizini oluşturma hatası: {e}")
            # Fallback: create under src
            self.metadata_dir = current_dir / "src" / "metadata"
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Separate file per region
        self.regions_dir = self.metadata_dir / "regions"
        try:
            self.regions_dir.mkdir(exist_ok=True)
        except Exception as e:
            print(f"Regions dizini oluşturma hatası: {e}")
        
        # Cache
        self._region_cache: Dict[str, RegionInfo] = {}
        self._cache_timestamp: Dict[str, float] = {}
        self._cache_ttl = 600  # 10 dakika cache
    
    def get_region_info(self, region_name: str) -> Optional[RegionInfo]:
        """Get region info - ultra fast"""
        current_time = time.time()
        
        # Cache check
        if (region_name in self._region_cache and 
            current_time - self._cache_timestamp.get(region_name, 0) < self._cache_ttl):
            return self._region_cache[region_name]
        
        # Read region file
        region_file = self.regions_dir / f"{region_name}.json"
        
        try:
            if region_file.exists():
                with open(region_file, 'r', encoding='utf-8') as f:
                    region_data = json.load(f)
                
                # Convert to RegionInfo object
                layers = {}
                for layer_type, layer_dict in region_data.get('layers', {}).items():
                    layers[layer_type] = {}
                    for layer_name, layer_info in layer_dict.items():
                        layers[layer_type][layer_name] = TileLayerInfo(**layer_info)
                
                region_info = RegionInfo(
                    name=region_data['name'],
                    bbox=region_data['bbox'],
                    center=region_data.get('center', [0, 0]),  # fallback to [0,0] if not found
                    layers=layers,
                    last_updated=region_data['last_updated']
                )
                
                # Save to cache
                self._region_cache[region_name] = region_info
                self._cache_timestamp[region_name] = current_time
                
                return region_info
                
        except Exception as e:
            print(f"Region info yükleme hatası: {e}")
        
        return None
    
    def list_regions(self) -> List[str]:
        """List all regions - ultra fast"""
        try:
            # Regions dizinindeki tüm .json dosyalarını bul
            region_files = list(self.regions_dir.glob("*.json"))
            regions = [f.stem for f in region_files]  # .json uzantısını kaldır
            return regions
        except Exception as e:
            print(f"Region listesi yükleme hatası: {e}")
            return []
    
    def save_region_info(self, region_name: str, region_info: RegionInfo):
        """Save region info"""
        try:
            region_file = self.regions_dir / f"{region_name}.json"
            
            # Convert RegionInfo to dict
            data = {
                'name': region_info.name,
                'bbox': region_info.bbox,
                'center': region_info.center,
                'last_updated': region_info.last_updated,
                'layers': {}
            }
            
            for layer_type, layer_dict in region_info.layers.items():
                data['layers'][layer_type] = {}
                for layer_name, layer_info in layer_dict.items():
                    data['layers'][layer_type][layer_name] = asdict(layer_info)
            
            # Write to file
            with open(region_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Update cache
            self._region_cache[region_name] = region_info
            self._cache_timestamp[region_name] = time.time()
            
            print(f"Region info kaydedildi: {region_file}")
            
        except Exception as e:
            print(f"Region info kaydetme hatası: {e}")

    def ensure_geocoordinate_data(self, region_name: str):
        """Add geocoordinate data to metadata for a region"""
        try:
            # Get existing region info
            region_info = self.get_region_info(region_name)
            
            # If center missing or [0,0], fetch from geocoordinate API
            needs_geocoord = (
                region_info is None or 
                not hasattr(region_info, 'center') or 
                region_info.center == [0, 0] or
                not region_info.center
            )
            
            if needs_geocoord:
                print(f"[INFO] Getting geocoordinate data for: {region_name}")
                geocoord_data = get_region_data(region_name)
                
                if geocoord_data and 'center' in geocoord_data:
                    center = geocoord_data['center']
                    bbox = geocoord_data.get('bbox', [0, 0, 0, 0])
                    
                    print(f"[SUCCESS] Got geocoordinate data: center={center}, bbox={bbox}")
                    
                    # Update existing region info or create new
                    if region_info:
                        region_info.center = center
                        region_info.bbox = bbox
                    else:
                        region_info = RegionInfo(
                            name=region_name,
                            bbox=bbox,
                            center=center,
                            layers={},
                            last_updated=datetime.now().isoformat()
                        )
                    
                    # Save
                    self.save_region_info(region_name, region_info)
                    return center, bbox
                else:
                    print(f"[WARNING] No geocoordinate data found for: {region_name}")
            else:
                print(f"[INFO] Geocoordinate data already exists for: {region_name}")
                return region_info.center, region_info.bbox
                
        except Exception as e:
            print(f"[ERROR] Failed to get geocoordinate data for {region_name}: {e}")
        
        return None, None
    
    def update_region_metadata(self, region_name: str, bbox: List[float] = None):
        """Update region metadata"""
        region_info = self.get_region_info(region_name)
        
        if region_info:
            if bbox:
                region_info.bbox = bbox
            region_info.last_updated = datetime.now().isoformat()
        else:
            # Create new region
            # center required: compute from bbox if present, else [0,0]
            if bbox and len(bbox) == 4:
                try:
                    center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
                except Exception:
                    center = [0, 0]
            else:
                center = [0, 0]
            region_info = RegionInfo(
                name=region_name,
                bbox=bbox or [0, 0, 1, 1],
                center=center,
                layers={'raster': {}, 'vector': {}},
                last_updated=datetime.now().isoformat()
            )
        
        self.save_region_info(region_name, region_info)
        return region_info
    
    def add_layer_info(self, region_name: str, layer_name: str, layer_type: str, 
                      min_zoom: int, max_zoom: int, tile_count: int, 
                      total_size: int, available_zooms: List[int]):
        """Add or update layer info"""
        region_info = self.update_region_metadata(region_name)
        
        # Build layer info
        layer_info = TileLayerInfo(
            name=layer_name,
            type=layer_type,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            tile_count=tile_count,
            total_size=total_size,
            last_updated=datetime.now().isoformat(),
            available_zooms=sorted(available_zooms)
        )
        
        # Add/update layer
        region_info.layers[layer_type][layer_name] = layer_info
        
        # Save
        self.save_region_info(region_name, region_info)
        
        print(f"Layer bilgileri eklendi: {region_name}/{layer_type}/{layer_name}")
        return layer_info
    
    def get_layer_info(self, region_name: str, layer_name: str, layer_type: str) -> Optional[TileLayerInfo]:
        """Get layer info"""
        region_info = self.get_region_info(region_name)
        if region_info and layer_type in region_info.layers:
            return region_info.layers[layer_type].get(layer_name)
        return None
    
    def list_layers(self, region_name: str) -> Dict[str, List[str]]:
        """List layers in a region"""
        region_info = self.get_region_info(region_name)
        if region_info:
            return {
                'raster': list(region_info.layers.get('raster', {}).keys()),
                'vector': list(region_info.layers.get('vector', {}).keys())
            }
        return {'raster': [], 'vector': []}
    
    def remove_layer(self, region_name: str, layer_name: str, layer_type: str):
        """Remove a layer from metadata"""
        region_info = self.get_region_info(region_name)
        
        if region_info and layer_type in region_info.layers:
            if layer_name in region_info.layers[layer_type]:
                del region_info.layers[layer_type][layer_name]
                region_info.last_updated = datetime.now().isoformat()
                self.save_region_info(region_name, region_info)
                print(f"Layer kaldırıldı: {region_name}/{layer_type}/{layer_name}")
    
    def remove_region(self, region_name: str):
        """Remove a region from metadata"""
        region_file = self.regions_dir / f"{region_name}.json"
        if region_file.exists():
            region_file.unlink()
            if region_name in self._region_cache:
                del self._region_cache[region_name]
                del self._cache_timestamp[region_name]
            print(f"Region kaldırıldı: {region_name}")
    
    def scan_existing_regions(self):
        """Scan existing regions and update metadata"""
        print("Mevcut region'lar taranıyor...")
        
        if not self.map_tiles_dir.exists():
            print("Map tiles dizini bulunamadı")
            return
        
        # Read bbox values from config.json
        config_bboxes = self._load_config_bboxes()
        
        for item in self.map_tiles_dir.iterdir():
            if item.is_dir() and item.name != 'metadata':
                region_name = item.name
                print(f"Region taranıyor: {region_name}")
                
                # Use bbox from config if available; else None
                bbox = config_bboxes.get(region_name)
                if bbox:
                    print(f"  Config'den bbox alındı: {bbox}")
                else:
                    print(f"  Config'de bbox bulunamadı, varsayılan kullanılacak")
                
                # Region'ı güncelle
                region_info = self.update_region_metadata(region_name, bbox)
                
                # Scan raster layers
                raster_dir = item / 'raster'
                if raster_dir.exists():
                    for style_dir in raster_dir.iterdir():
                        if style_dir.is_dir():
                            self._scan_layer_directory(region_name, style_dir.name, 'raster')
                
                # Scan vector layers
                vector_dir = item / 'vector'
                if vector_dir.exists():
                    for style_dir in vector_dir.iterdir():
                        if style_dir.is_dir():
                            self._scan_layer_directory(region_name, style_dir.name, 'vector')
        
        print("Region tarama tamamlandı")
    
    def _scan_layer_directory(self, region_name: str, layer_name: str, layer_type: str):
        """Scan layer directory and update info"""
        layer_path = self.map_tiles_dir / region_name / layer_type / layer_name
        
        if not layer_path.exists():
            return
        
        # Zoom seviyelerini bul
        available_zooms = []
        tile_count = 0
        total_size = 0
        
        for zoom_dir in layer_path.iterdir():
            if zoom_dir.is_dir() and zoom_dir.name.isdigit():
                zoom_level = int(zoom_dir.name)
                available_zooms.append(zoom_level)
                
                # Count tiles
                for x_dir in zoom_dir.iterdir():
                    if x_dir.is_dir() and x_dir.name.isdigit():
                        for tile_file in x_dir.iterdir():
                            if tile_file.is_file():
                                tile_count += 1
                                total_size += tile_file.stat().st_size
        
        if available_zooms:
            min_zoom = min(available_zooms)
            max_zoom = max(available_zooms)
            
            # Update layer info
            self.add_layer_info(
                region_name=region_name,
                layer_name=layer_name,
                layer_type=layer_type,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                tile_count=tile_count,
                total_size=total_size,
                available_zooms=available_zooms
            )
    
    def get_metadata_summary(self) -> Dict[str, Any]:
        """Metadata summary"""
        total_regions = 0
        total_layers = 0
        total_tiles = 0
        total_size = 0
        
        for region_name in self._region_cache.keys():
            region_info = self._region_cache[region_name]
            total_regions += 1
            for layer_type, layers in region_info.layers.items():
                total_layers += len(layers)
                for layer_info in layers.values():
                    total_tiles += layer_info.tile_count
                    total_size += layer_info.total_size
        
        return {
            'total_regions': total_regions,
            'total_layers': total_layers,
            'total_tiles': total_tiles,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'last_updated': datetime.now().isoformat()
        }
    
    def _load_config_bboxes(self) -> Dict[str, List[float]]:
        """Load region bbox info from config.json"""
        config_bboxes = {}
        
        try:
            config_path = Path.cwd() / 'config.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                if 'regions' in config_data:
                    for region_name, region_data in config_data['regions'].items():
                        if 'bbox' in region_data and len(region_data['bbox']) == 4:
                            config_bboxes[region_name] = region_data['bbox']
                            print(f"Config'den bbox yüklendi: {region_name} -> {region_data['bbox']}")
                
                print(f"Toplam {len(config_bboxes)} region bbox'ı yüklendi")
            else:
                print("Config.json dosyası bulunamadı")
                
        except Exception as e:
            print(f"Config.json okuma hatası: {e}")
        
        return config_bboxes


# Global metadata manager instance
metadata_manager = MetadataManager() 