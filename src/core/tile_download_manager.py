import argparse
from typing import Dict, Any, List, Optional
from services.config_service import ConfigService
from services.tile_download_service import TileDownloadService
from services.local_tile_service import LocalTileService
from services.geocoordinate_service import GeoCoordinateService
from services.source_factory import SourceFactory
from utils.tile_calculator import TileCalculator
from utils.file_utils import FileUtils
from utils.metadata_manager import metadata_manager
from exceptions.tile_downloader_exceptions import ConfigurationError, DownloadError
from pathlib import Path


class TileDownloadManager:
    """Main manager class for tile downloading operations"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_service = ConfigService()
        self.config = self.config_service.load_config(config_path)
        self.download_service = TileDownloadService(
            max_workers=self.config['max_workers_per_server'],
            retry_attempts=self.config['retry_attempts'],
            timeout=self.config['timeout']
        )
        self.local_tile_service = LocalTileService()
        self.geocoordinate_service = GeoCoordinateService()
        self._initialize_local_sources()
    
    def _initialize_local_sources(self):
        """Initialize local sources from configuration"""
        local_sources = self.config_service.get_local_sources(self.config)
        for source in local_sources:
            source_config = {
                'name': source.name,
                'type': 'local',
                'path': source.path,
                'source_type': source.source_type,
                'tile_type': source.tile_type,
                'bounds': source.bounds,
                'min_zoom': source.min_zoom,
                'max_zoom': source.max_zoom
            }
            success = self.local_tile_service.register_source(source_config)
            if not success:
                print(f"Warning: Failed to register local source: {source.name}")
    
    def list_regions(self) -> None:
        """List available regions"""
        print("Available regions:")
        for name, region_data in self.config['regions'].items():
            description = region_data.get('description', 'No description')
            print(f"  {name}: {description}")
    
    def list_sources(self) -> None:
        """List available sources (both online and local)"""
        print("Available sources:")
        
        # Online sources
        online_sources = self.config_service.get_enabled_servers(self.config)
        if online_sources:
            print("  Online sources:")
            for source in online_sources:
                print(f"    {source.get_name()} ({source.get_tile_type()})")
        
        # Local sources - check registered sources in local_tile_service
        local_sources = self.config_service.get_local_sources(self.config)
        if local_sources:
            print("  Local sources:")
            for source in local_sources:
                # Check if source is registered in local_tile_service
                registered_source = self.local_tile_service.get_source(source.name)
                if registered_source and registered_source.is_available():
                    status = "OK"
                else:
                    status = "X"
                    
                # Get bounds and zoom range info
                bounds = source.get_bounds()
                min_zoom, max_zoom = source.get_zoom_range()
                bounds_str = f"[{bounds[0]:.1f}, {bounds[1]:.1f}, {bounds[2]:.1f}, {bounds[3]:.1f}]" if bounds else "No bounds"
                
                print(f"    {status} {source.get_name()} ({source.get_tile_type()})")
                print(f"        Path: {source.path}")
                print(f"        Bounds: {bounds_str} (lon_min, lat_min, lon_max, lat_max)")
                print(f"        Zoom: {min_zoom}-{max_zoom}")
                print(f"        Description: {source.description}")
                print()
    
    def download_region(self, region_name: str, min_zoom: Optional[int] = None, 
                       max_zoom: Optional[int] = None, 
                       server_filter: Optional[List[str]] = None,
                       source_filter: Optional[List[str]] = None) -> bool:
        """Download tiles for a specific region"""
        try:
            region = self.config_service.get_region(self.config, region_name)
            
            # Get online sources
            enabled_sources = self.config_service.get_enabled_sources(self.config)
            
            # Apply server filter if provided (for online sources)
            if server_filter:
                enabled_sources = [s for s in enabled_sources if s.get_name() in server_filter]
            
            # Get local sources
            local_sources_list = self.config_service.get_local_sources(self.config)
            filtered_local_sources = []
            
            # Apply source filter if provided (for local sources)
            if source_filter:
                for source_name in source_filter:
                    # Find local source by name
                    for local_source in local_sources_list:
                        if local_source.get_name() == source_name:
                            filtered_local_sources.append(local_source)
                            break
            else:
                # If no source filter, include all local sources
                filtered_local_sources = local_sources_list
            
            # Combine sources based on filters
            all_sources = []
            
            # If only source filter (local), use only local sources
            if source_filter and not server_filter:
                all_sources = filtered_local_sources
            # If only server filter (online), use only online sources  
            elif server_filter and not source_filter:
                all_sources = enabled_sources
            # If both filters, combine both
            elif server_filter and source_filter:
                all_sources = enabled_sources + filtered_local_sources
            # If no filters, use all available sources
            else:
                all_sources = enabled_sources + filtered_local_sources
            
            # Use provided zoom levels or defaults
            min_zoom = min_zoom or region.min_zoom
            max_zoom = max_zoom or region.max_zoom
            
            return self._download_area(
                region_name=region.name,
                bbox=region.bbox,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                sources=all_sources
            )
            
        except Exception as e:
            print(f"Error downloading region {region_name}: {e}")
            return False
    
    def download_bbox(self, bbox: List[float], min_zoom: int, max_zoom: int,
                     server_filter: Optional[List[str]] = None,
                     source_filter: Optional[List[str]] = None,
                     region_name: Optional[str] = None) -> bool:
        """Download tiles for a custom bounding box"""
        try:
            # Get online sources
            enabled_sources = self.config_service.get_enabled_sources(self.config)
            
            # Apply server filter if provided (for online sources)
            if server_filter:
                enabled_sources = [s for s in enabled_sources if s.get_name() in server_filter]
            
            # Get local sources
            local_sources_list = self.config_service.get_local_sources(self.config)
            filtered_local_sources = []
            
            # Apply source filter if provided (for local sources)
            if source_filter:
                for source_name in source_filter:
                    # Find local source by name
                    for local_source in local_sources_list:
                        if local_source.get_name() == source_name:
                            filtered_local_sources.append(local_source)
                            break
            else:
                # If no source filter, include all local sources
                filtered_local_sources = local_sources_list
            
            # Combine sources based on filters
            all_sources = []
            
            # If only source filter (local), use only local sources
            if source_filter and not server_filter:
                all_sources = filtered_local_sources
            # If only server filter (online), use only online sources  
            elif server_filter and not source_filter:
                all_sources = enabled_sources
            # If both filters, combine both
            elif server_filter and source_filter:
                all_sources = enabled_sources + filtered_local_sources
            # If no filters, use all available sources
            else:
                all_sources = enabled_sources + filtered_local_sources
            
            # Generate folder name for bbox
            if region_name is None:
                min_lon, min_lat, max_lon, max_lat = bbox
                region_name = f"bbox_{min_lon:.3f}_{min_lat:.3f}_{max_lon:.3f}_{max_lat:.3f}"
            
            return self._download_area(
                region_name=region_name,
                bbox=bbox,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                sources=all_sources
            )
            
        except Exception as e:
            print(f"Error downloading bbox {bbox}: {e}")
            return False
    
    def _download_area(self, region_name: str, bbox: List[float], 
                      min_zoom: int, max_zoom: int, 
                      sources: List) -> bool:
        """Download tiles for a specific area"""
        print(f"=== Downloading {region_name.upper()} ===")
        print(f"Bounding Box: {bbox}")
        print(f"Zoom Levels: {min_zoom} to {max_zoom}")
        print(f"Output Directory: {self.config['output_dir']}")
        print(f"Enabled Sources: {', '.join([s.get_name() for s in sources])}")
        print()
        
        # Separate online and local sources
        online_sources = []
        local_sources = []
        
        for source in sources:
            if hasattr(source, 'get_source_type') and source.get_source_type() == 'local':
                local_sources.append(source)
            else:
                online_sources.append(source)
        
        success = True
        
        # Process online sources
        if online_sources:
            print("Processing online sources...")
            success &= self._download_from_online_sources(region_name, bbox, min_zoom, max_zoom, online_sources)
        
        # Process local sources
        if local_sources:
            print("Processing local sources...")
            success &= self._download_from_local_sources(region_name, bbox, min_zoom, max_zoom, local_sources)
        
        # Update metadata after download completes (automatic)
        if success:
            print("\n=== Metadata Güncelleniyor ===")
            self._update_metadata_after_download(region_name, bbox, sources)
        else:
            print("\nİndirme başarısız olduğu için metadata güncellenmedi!")
        
        return success
    
    def _download_from_online_sources(self, region_name: str, bbox: List[float], 
                                    min_zoom: int, max_zoom: int, 
                                    online_sources: List) -> bool:
        """Download tiles from online sources"""
        try:
            # Calculate tiles
            print("Calculating tiles...")
            all_tiles = TileCalculator.get_tiles_for_bbox(bbox, min_zoom, max_zoom)
            total_tiles = len(all_tiles)
            
            if total_tiles == 0:
                print("No tiles to download.")
                return True
            
            print(f"Total tiles to download: {total_tiles}")
            
            # Download tiles using existing service
            result = self.download_service.download_tiles_batch(
                all_tiles, self.config['output_dir'], region_name, online_sources
            )
            
            if result['downloaded'] > 0:
                print(f"Successfully downloaded {result['downloaded']} tiles from online sources")
                return True
            else:
                print("Failed to download tiles from online sources")
                return False
                
        except Exception as e:
            print(f"Error downloading from online sources: {e}")
            return False
    
    def _download_from_local_sources(self, region_name: str, bbox: List[float], 
                                   min_zoom: int, max_zoom: int, 
                                   local_sources: List) -> bool:
        """Download tiles from local sources"""
        try:
            success = True
            
            for source in local_sources:
                source_name = source.get_name()
                print(f"Processing local source: {source_name}")
                
                # Extract tiles for each zoom level
                for zoom in range(min_zoom, max_zoom + 1):
                    result = self.local_tile_service.extract_tiles(
                        source_name, bbox, zoom, self.config['output_dir'], region_name
                    )
                    
                    if result['success']:
                        print(f"  Zoom {zoom}: Extracted {result['tiles_extracted']} tiles")
                    else:
                        print(f"  Zoom {zoom}: Failed - {', '.join(result['errors'])}")
                        success = False
            
            return success
            
        except Exception as e:
            print(f"Error downloading from local sources: {e}")
            return False
    
    def _count_existing_tiles(self, tiles: List, region_name: str, 
                            servers: List) -> int:
        """Count existing tiles across all servers"""
        existing_count = 0
        
        for zoom, x, y in tiles:
            found = False
            for server in servers:
                if server.get_tile_type() == 'vector':
                    extension = 'pbf'
                    tile_type = 'vector'
                    style_name = server.get_name()
                else:
                    extension = 'png'
                    tile_type = 'raster'
                    style_name = server.get_name()
                
                tile_path = FileUtils.get_tile_path(
                    self.config['output_dir'], region_name, tile_type,
                    style_name, zoom, x, y, extension
                )
                
                if FileUtils.file_exists(tile_path):
                    existing_count += 1
                    found = True
                    break
            
            if found:
                continue
        
        return existing_count
    
    def _update_metadata_after_download(self, region_name: str, bbox: List[float], sources: List):
        """Update metadata after download completes"""
        try:
            print("Metadata güncelleme başlatılıyor...")
            
            # Update region metadata
            metadata_manager.update_region_metadata(region_name, bbox)
            
            # Update layer info for each source
            for source in sources:
                layer_name = source.get_name()
                layer_type = source.get_tile_type()
                
                print(f"  Layer taranıyor: {layer_name} ({layer_type})")
                
                # Scan layer directory - build correct path
                layer_path = Path(self.config['output_dir']) / region_name / layer_type / layer_name
                
                if layer_path.exists():
                    # Layer bilgilerini hesapla
                    available_zooms = []
                    tile_count = 0
                    total_size = 0
                    
                    # Zoom seviyelerini bul
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
                        
                        # Layer bilgilerini metadata'ya ekle
                        metadata_manager.add_layer_info(
                            region_name=region_name,
                            layer_name=layer_name,
                            layer_type=layer_type,
                            min_zoom=min_zoom,
                            max_zoom=max_zoom,
                            tile_count=tile_count,
                            total_size=total_size,
                            available_zooms=available_zooms
                        )
                        
                        print(f"  {layer_name} ({layer_type}): {tile_count} tiles, zoom {min_zoom}-{max_zoom}")
                    else:
                        # No tiles found for this layer
                        print(f"  {layer_name} ({layer_type}): Hiç tile bulunamadı")
                else:
                    # Layer directory not found
                    print(f"  {layer_name} ({layer_type}): Layer dizini bulunamadı")
            
            # Metadata update finished
            print("Metadata güncelleme tamamlandı!")
            
        except Exception as e:
            # Metadata update error
            print(f"Metadata güncelleme hatası: {e}")
            import traceback
            traceback.print_exc()

    # =========================
    # Interactive Download Wizard
    # =========================
    def _prompt_choice(self, title: str, options: List[str], allow_back: bool = False) -> Optional[int]:
        """Show numbered options; return selected index (0-based).
        If allow_back=True, 0 means back (returns -1). Otherwise 0 means cancel (returns None).
        """
        try:
            print(f"\n{title}")
            for i, opt in enumerate(options, start=1):
                print(f"  {i}) {opt}")
            if allow_back:
                print("  0) Back")
            else:
                print("  0) Cancel")
            while True:
                raw = input("Your choice: ").strip()
                if raw.isdigit():
                    val = int(raw)
                    if val == 0:
                        return -1 if allow_back else None
                    if 1 <= val <= len(options):
                        return val - 1
                print("Invalid choice, try again.")
        except KeyboardInterrupt:
            return None

    def _prompt_multi_select(self, title: str, options: List[str], allow_all: bool = True, allow_back: bool = True) -> List[int]:
        """Comma-separated multi-select, supports 'all'. 0 = back/cancel.
        If allow_back=True, '0' returns [-1] (back).
        """
        try:
            print(f"\n{title}")
            for i, opt in enumerate(options, start=1):
                print(f"  {i}) {opt}")
            print("  0) Back" if allow_back else "  0) Cancel")
            if allow_all:
                print("  all) Select all")
            while True:
                raw = input("Select (e.g. 1,3,5): ").strip().lower()
                if raw == '0':
                    return [-1] if allow_back else []
                if allow_all and raw in ('all', 'hepsi', 'tum', 'tümü'):
                    return list(range(len(options)))
                parts = [p.strip() for p in raw.split(',') if p.strip()]
                idxs: List[int] = []
                ok = True
                for p in parts:
                    if not p.isdigit():
                        ok = False
                        break
                    val = int(p)
                    if 1 <= val <= len(options):
                        idxs.append(val - 1)
                    else:
                        ok = False
                        break
                if ok and idxs:
                    # Sort uniquely
                    return sorted(list(set(idxs)))
                print("Invalid selection, try again.")
        except KeyboardInterrupt:
            return []

    def _prompt_int(self, prompt: str, default: Optional[int] = None) -> Optional[int]:
        """Ask for integer. Empty returns default, cancel returns None."""
        try:
            while True:
                raw = input(f"{prompt}{' [' + str(default) + ']' if default is not None else ''}: ").strip()
                if raw == '':
                    return default
                if raw.isdigit() or (raw.startswith('-') and raw[1:].isdigit()):
                    return int(raw)
                print("Invalid number, try again.")
        except KeyboardInterrupt:
            return None

    def _prompt_bbox(self, defaults: Optional[List[float]] = None) -> Optional[List[float]]:
        """Ask for bbox [min_lon, min_lat, max_lon, max_lat]."""
        try:
            if defaults and len(defaults) == 4:
                print(f"Default bbox: {defaults}")
            raw = input("Enter BBOX (min_lon min_lat max_lon max_lat) or leave empty: ").strip()
            if raw == '':
                return defaults
            parts = raw.split()
            if len(parts) != 4:
                print("4 values required.")
                return None
            vals = [float(p) for p in parts]
            return vals
        except KeyboardInterrupt:
            return None
        except Exception:
            print("Invalid bbox format.")
            return None

    def _prompt_int_back(self, prompt: str, default: Optional[int] = None) -> tuple[bool, Optional[int]]:
        """Ask for integer. 'b' means back (True, None). Empty returns default."""
        try:
            while True:
                raw = input(f"{prompt}{' [' + str(default) + ']' if default is not None else ''} (back: 'b'): ").strip().lower()
                if raw == 'b':
                    return True, None
                if raw == '':
                    return False, default
                if raw.isdigit() or (raw.startswith('-') and raw[1:].isdigit()):
                    return False, int(raw)
                print("Invalid number, try again.")
        except KeyboardInterrupt:
            return True, None

    def _prompt_bbox_back(self, defaults: Optional[List[float]] = None) -> tuple[bool, Optional[List[float]]]:
        """Ask for BBOX. 'b' means back (True, None). Empty -> defaults."""
        try:
            if defaults and len(defaults) == 4:
                print(f"Default bbox: {defaults}")
            raw = input("BBOX (min_lon min_lat max_lon max_lat) (back: 'b'): ").strip().lower()
            if raw == 'b':
                return True, None
            if raw == '':
                return False, defaults
            parts = raw.split()
            if len(parts) != 4:
                print("4 values required.")
                return False, None
            vals = [float(p) for p in parts]
            return False, vals
        except KeyboardInterrupt:
            return True, None
        except Exception:
            print("Invalid bbox format.")
            return False, None

    def run_interactive_wizard(self) -> None:
        """Step-by-step interactive wizard (supports back)."""
        print("\n=== INTERACTIVE DOWNLOAD WIZARD ===")

        # Durum
        mode: Optional[str] = None  # 'region' | 'place' | 'bbox'
        selected_region: Optional[str] = None
        selected_place: Optional[str] = None
        selected_bbox: Optional[List[float]] = None
        server_filter: Optional[List[str]] = None
        source_filter: Optional[List[str]] = None
        min_zoom_val: int = 10
        max_zoom_val: int = 15
        # polygon/mask removed

        # Listeler
        online_servers = self.config_service.get_enabled_servers(self.config)
        online_names = [s.get_name() for s in online_servers]
        local_sources_objs = self.config_service.get_local_sources(self.config)
        local_names = [s.get_name() for s in local_sources_objs]

        step = 0
        while True:
            # Step 0: Mode selection
            if step == 0:
                choice = self._prompt_choice(
                    "Download mode:",
                    ["By region", "By place (province/district/country)", "By custom BBOX"],
                    allow_back=False
                )
                if choice is None:
                    print("Cancelled.")
                    return
                mode = ['region', 'place', 'bbox'][choice]
                step = 1
                continue

            # Step 1: Target selection
            if step == 1:
                if mode == 'region':
                    region_names = list(self.config.get('regions', {}).keys())
                    if not region_names:
                        print("No regions defined in config.")
                        return
                    ridx = self._prompt_choice("Select a region:", region_names, allow_back=True)
                    if ridx is None:
                        print("Cancelled.")
                        return
                    if ridx == -1:
                        step = 0
                        continue
                    selected_region = region_names[ridx]
                    region = self.config_service.get_region(self.config, selected_region)
                    selected_bbox = region.bbox
                    min_zoom_val, max_zoom_val = region.min_zoom, region.max_zoom
                    print(f"Selected region: {selected_region}  BBOX={selected_bbox}  Zoom={min_zoom_val}-{max_zoom_val}")
                elif mode == 'place':
                    raw = input("Place name (e.g. 'konya', 'istanbul', 'germany') (back: 'b'): ").strip()
                    if raw.lower() == 'b':
                        step = 0
                        continue
                    if not raw:
                        print("Cancelled.")
                        return
                    print(f"Fetching coordinates for '{raw}'...")
                    bbox = self.geocoordinate_service.get_bbox_from_place(raw)
                    if bbox is None:
                        print("Not found. Suggestions:")
                        suggestions = self.geocoordinate_service.search_suggestions(raw, 5) or []
                        if suggestions:
                            opts = [f"{s['name']} ({s['type']})" for s in suggestions]
                            sidx = self._prompt_choice("Pick a suggestion:", opts, allow_back=True)
                            if sidx is None:
                                print("Cancelled.")
                                return
                            if sidx == -1:
                                step = 0
                                continue
                            raw = suggestions[sidx]['name']
                            bbox = self.geocoordinate_service.get_bbox_from_place(raw)
                        if bbox is None:
                            print("Could not resolve coordinates.")
                            step = 0
                            continue
                    selected_place = raw
                    selected_bbox = bbox
                    print(f"BBOX: {selected_bbox}")
                    # Default zoom levels
                    min_zoom_val, max_zoom_val = 10, 15
                else:  # bbox
                    back, bbox = self._prompt_bbox_back()
                    if back:
                        step = 0
                        continue
                    if not bbox:
                        print("Cancelled.")
                        return
                    selected_bbox = bbox
                step = 2
                continue

            # Step 2: Sources (polygon/mask step removed)
            if step == 2:
                if not online_names and not local_names:
                    print("No selectable sources (see config.json -> servers).")
                    return
                k = self._prompt_choice(
                    "Source type:",
                    ["Online servers only", "Local sources (MBTiles) only", "Both (pick)"],
                    allow_back=True
                )
                if k is None:
                    print("Cancelled.")
                    return
                if k == -1:
                    step = 1
                    continue
                server_filter, source_filter = None, None
                if k in (0, 2) and online_names:
                    idxs = self._prompt_multi_select("Online servers:", online_names, allow_all=True, allow_back=True)
                    if idxs == [-1]:
                        step = 1
                        continue
                    server_filter = [online_names[i] for i in idxs] if idxs else None
                if k in (1, 2) and local_names:
                    annotated = []
                    for name in local_names:
                        src = next((s for s in local_sources_objs if s.get_name() == name), None)
                        if src:
                            mz, xz = src.get_zoom_range()
                            b = src.get_bounds()
                            annotated.append(f"{name}  (zoom {mz}-{xz}, bounds [{b[0]:.2f},{b[1]:.2f},{b[2]:.2f},{b[3]:.2f}])")
                        else:
                            annotated.append(name)
                    idxs = self._prompt_multi_select("Local sources:", annotated, allow_all=True, allow_back=True)
                    if idxs == [-1]:
                        step = 1
                        continue
                    source_filter = [local_names[i] for i in idxs] if idxs else None
                step = 3
                continue

            # Step 3: Zooms
            if step == 3:
                # dynamic intersection hint for local sources
                if source_filter:
                    mz_all: List[int] = []
                    xz_all: List[int] = []
                    for name in (source_filter or []):
                        src = next((s for s in local_sources_objs if s.get_name() == name), None)
                        if src:
                            mz_s, xz_s = src.get_zoom_range()
                            mz_all.append(mz_s)
                            xz_all.append(xz_s)
                    if mz_all and xz_all:
                        hint_min = max(mz_all)
                        hint_max = min(xz_all)
                        print(f"Hint: intersection of local zoom limits -> {hint_min}-{hint_max}")
                        min_zoom_val = max(min_zoom_val, hint_min)
                        max_zoom_val = min(max_zoom_val, hint_max)

                back, mz = self._prompt_int_back("Minimum zoom", min_zoom_val)
                if back:
                    step = 2
                    continue
                if mz is None:
                    print("Cancelled.")
                    return
                back, xz = self._prompt_int_back("Maximum zoom", max_zoom_val)
                if back:
                    step = 2
                    continue
                if xz is None:
                    print("Cancelled.")
                    return
                if mz > xz:
                    print("Minimum zoom cannot be greater than maximum zoom.")
                    continue
                # Validate against local source limits
                if source_filter:
                    violations = []
                    for name in (source_filter or []):
                        src = next((s for s in local_sources_objs if s.get_name() == name), None)
                        if src:
                            s_mz, s_xz = src.get_zoom_range()
                            if mz < s_mz or xz > s_xz:
                                violations.append(f"{name} (allowed {s_mz}-{s_xz})")
                    if violations:
                        print("Selected zooms exceed local source limits:\n  - " + "\n  - ".join(violations))
                        continue
                min_zoom_val, max_zoom_val = mz, xz
                step = 4
                continue

            # Step 4: Confirm
            if step == 4:
                print("\nSummary:")
                target = selected_region or selected_place or f"bbox={selected_bbox}"
                print(f"  Target: {target}")
                print(f"  Sources: online={server_filter or 'default/enabled'}, local={source_filter or 'default/enabled'}")
                print(f"  Zoom: {min_zoom_val}-{max_zoom_val}")
                action = self._prompt_choice(
                    "Proceed?",
                    ["Start download", "Change target", "Change sources", "Change zoom"],
                    allow_back=True
                )
                if action is None:
                    print("Cancelled.")
                    return
                if action == -1:
                    step = 3
                    continue
                if action == 0:
                    # Start download -> proceed to final validation/download step
                    step = 5
                    continue
                if action == 1:
                    step = 1
                    continue
                if action == 2:
                    step = 2
                    continue
                if action == 3:
                    step = 3
                    continue

            # Step 5: Final confirm & start
            if step == 5:
                # No extra confirmation loop; start download immediately
                # Bounds validation for local sources vs selected bbox
                if source_filter and selected_bbox:
                    incompatible = []
                    for name in (source_filter or []):
                        src = next((s for s in local_sources_objs if s.get_name() == name), None)
                        if src:
                            b = src.get_bounds()
                            if b and selected_bbox and not (selected_bbox[2] >= b[0] and selected_bbox[0] <= b[2] and selected_bbox[3] >= b[1] and selected_bbox[1] <= b[3]):
                                incompatible.append(name)
                    if incompatible:
                        print("Selected BBOX does not intersect with these local sources:\n  - " + "\n  - ".join(incompatible))
                        step = 2
                        continue

                # Download
                if mode == 'region' and selected_region:
                    ok = self.download_region(selected_region, min_zoom_val, max_zoom_val, server_filter, source_filter)
                else:
                    ok = self.download_bbox(selected_bbox, min_zoom_val, max_zoom_val, server_filter, source_filter, region_name=(selected_place or None))
                print("\nDone." if ok else "\nFailed.")
                return
    
    def run_from_command_line(self) -> None:
        """Run tile download command-line interface"""
        parser = argparse.ArgumentParser(
            description=(
                'Download map tiles (raster and vector) by configured region, automatic place lookup, or custom BBOX.\n'
                '- Supports both online HTTP servers and local MBTiles sources (individually or combined).'
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=(
                'Examples:\n\n'
                '1) Download by region from ONLINE servers only:\n'
                '   python src/tile_downloader.py --region istanbul --servers "CartoDB_Light,OpenMapTiles_Vector"\n\n'
                '2) Download by region from LOCAL MBTiles sources only:\n'
                '   python src/tile_downloader.py --region istanbul --sources "Local_OSM_Turkey,Local_Satellite_Turkey"\n\n'
                '3) Mixed (online + local) by region:\n'
                '   python src/tile_downloader.py --region ankara --servers "CartoDB_Light" --sources "Local_OSM_Turkey"\n\n'
                '4) Custom BBOX (lon/lat order):\n'
                '   python src/tile_downloader.py --bbox 28.5 40.8 29.5 41.2 --min-zoom 10 --max-zoom 12 --servers "CartoDB_Light"\n\n'
                '5) Auto BBOX by place name:\n'
                '   python src/tile_downloader.py --place "germany" --min-zoom 5 --max-zoom 8 --sources "Local_OSM_Turkey"\n\n'
                '6) List configured regions and sources:\n'
                '   python src/tile_downloader.py --list-regions\n'
                '   python src/tile_downloader.py --list-sources\n\n'
                'Notes:\n'
                '- For LOCAL MBTiles, your BBOX must fall within the source bounds (see --list-sources).\n'
                '- Vector tiles are saved as .pbf, raster tiles as .png/.jpg.\n'
                "- Output directory layout: map_tiles/<region>/<raster|vector>/<source_name>/<z>/<x>/<y>.<ext>"
            )
        )
        parser.add_argument('--region', help='Region name to download (e.g., qatar, ankara). Must exist in config.json -> regions.')
        parser.add_argument('--place', help='Auto-detect BBOX from place name (e.g., "marmara", "germany", "istanbul"). Geocoordinate lookup is used.')
        parser.add_argument('--servers', help='Comma-separated ONLINE server names (config.json -> servers, type=http). E.g., "CartoDB_Light,OpenMapTiles_Vector"')
        parser.add_argument('--sources', help='Comma-separated LOCAL source names (config.json -> type=local). E.g., "Local_OSM_Turkey,Local_Satellite_Turkey". See bounds via --list-sources.')
        parser.add_argument('--list-regions', action='store_true', help='List configured regions with descriptions')
        parser.add_argument('--list-sources', action='store_true', help='List all online/local sources with bounds, zoom ranges and descriptions')
        parser.add_argument('--bbox', nargs=4, type=float, metavar=('min_lon', 'min_lat', 'max_lon', 'max_lat'), 
                           help='Custom BBOX (lon/lat). WARNING: BBOX must intersect selected sources! See --list-sources')
        parser.add_argument('--min-zoom', type=int, default=10, help='Minimum zoom level (default: 10)')
        parser.add_argument('--max-zoom', type=int, default=15, help='Maximum zoom level (default: 15)')
        # polygon-mode/mask-raster removed; arguments no longer supported
        parser.add_argument('--interactive', action='store_true', help='Start interactive download wizard (step-by-step)')
        
        args = parser.parse_args()
        
        # List regions if requested
        if args.list_regions:
            self.list_regions()
            return
        
        # List sources if requested
        if args.list_sources:
            self.list_sources()
            return
        
        # Parse server and source filters
        server_filter = None
        source_filter = None
        
        if args.servers:
            server_filter = [s.strip() for s in args.servers.split(',')]
        
        if args.sources:
            source_filter = [s.strip() for s in args.sources.split(',')]
        
        # Interactive wizard
        if args.interactive and not args.region and not args.bbox and not args.place:
            self.run_interactive_wizard()
            return

        # Check if region, bbox, or place is provided (non-interactive fallback)
        if not args.region and not args.bbox and not args.place:
            print("Please provide --region, --bbox, or --place, or use --interactive for the wizard!")
            print("\nConfigured regions:")
            self.list_regions()
            print("\nAvailable sources:")
            self.list_sources()
            print("\nCustom area: --bbox min_lon min_lat max_lon max_lat")
            print("Auto place lookup: --place 'name'  or interactive: --interactive")
            return
        
        # Handle --place parameter (polygon mode removed)
        if args.place:
            if args.region or args.bbox:
                print("Error: --place cannot be used with --region or --bbox")
                return
            
            print(f"Looking up coordinates for place: {args.place}")
            bbox = self.geocoordinate_service.get_bbox_from_place(args.place)
            
            if bbox is None:
                print(f"Could not find coordinates for place: {args.place}")
                
                # Show suggestions
                suggestions = self.geocoordinate_service.search_suggestions(args.place, 5)
                if suggestions:
                    print(f"\nDid you mean one of these?")
                    for suggestion in suggestions:
                        print(f"  - {suggestion['name']} ({suggestion['type']})")
                return
            
            # Use the found bbox for download with place name as region name
            success = self.download_bbox(bbox, args.min_zoom, args.max_zoom, server_filter, source_filter, region_name=args.place)
        else:
            # Download based on region or bbox
            success = False
            if args.region:
                success = self.download_region(args.region, args.min_zoom, args.max_zoom, server_filter, source_filter)
            elif args.bbox:
                success = self.download_bbox(args.bbox, args.min_zoom, args.max_zoom, server_filter, source_filter)
        
        if success:
            print("\nDownload completed successfully!")
        else:
            print("\nDownload failed!") 