import http.server
import socketserver
import os
import json
import socket
import time
import sys
import urllib.parse
import math
import sqlite3
import gzip
import zlib
from typing import Dict, Any, List
from functools import lru_cache
from pathlib import Path

# Import our metadata synchronization system
try:
    from src.utils.metadata_sync import sync_metadata_on_startup
except ImportError:
    # Fallback import without src prefix
    try:
        from utils.metadata_sync import sync_metadata_on_startup
    except ImportError:
        print("[WARNING] Could not import metadata synchronization system")
        sync_metadata_on_startup = None


class HTTPServerService:
    """Optimized HTTP server service for TileMapDownloader"""
    
    def __init__(self, port: int = 8080, base_directory: str = "."):
        self.port = port
        self.base_directory = base_directory
        socket.setdefaulttimeout(60)  # Reduced timeout
        # Simple cache for metadata
        self._metadata_cache = None
        self._metadata_cache_time = 0
        self._cache_duration = 300  # 5 minutes
        # Cache for filesystem tile extents per layer
        self._tile_extents_cache: Dict[str, Any] = {}
        self._tile_extents_cache_time: Dict[str, float] = {}
        self._tile_extents_ttl = 120  # seconds
        # Cache for per-zoom tile index (x->list[y])
        self._tile_index_cache: Dict[str, Any] = {}
        self._tile_index_cache_time: Dict[str, float] = {}
        self._tile_index_ttl = 120  # seconds
    
    def create_request_handler(self):
        """Create optimized HTTP request handler"""
        base_dir = self.base_directory
        server_service = self  # Reference to service instance
        
        class OptimizedHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=base_dir, **kwargs)
            
            timeout = 60
            
            def log_error(self, format, *args):
                # Ignore common connection errors to reduce log noise
                ignore_errors = ["Connection aborted", "WinError 10053", "ConnectionResetError"]
                if any(err in str(args) for err in ignore_errors):
                    return
                super().log_error(format, *args)
            
            def log_message(self, format, *args):
                # Only log important messages
                if "GET /" in format or "POST /" in format:
                    super().log_message(format, *args)
            
            def handle_one_request(self):
                try:
                    super().handle_one_request()
                except (ConnectionAbortedError, TimeoutError, socket.timeout, OSError, BrokenPipeError):
                    pass  # Silently handle connection issues
                except Exception as e:
                    error_keywords = ["WinError 10053", "ConnectionResetError", "Connection aborted", "WinError 10054"]
                    if not any(keyword in str(e) for keyword in error_keywords):
                        self.log_error("Request handling error: %s", str(e))
            
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
                super().end_headers()
            
            def do_OPTIONS(self):
                self.send_response(200)
                self.end_headers()
            
            def do_GET(self):
                # Route handling
                if self.path == '/' or self.path == '/index.html':
                    self._serve_index()
                elif self.path == '/list_regions':
                    self._handle_list_regions()
                elif self.path.startswith('/region_map_styles/'):
                    self._handle_region_map_styles()
                elif self.path.startswith('/inspect_mbtiles'):
                    self._handle_inspect_mbtiles()
                elif self.path.startswith('/tile_extents/'):
                    self._handle_tile_extents()
                elif self.path.startswith('/tile_index/'):
                    self._handle_tile_index()
                elif self.path in ['/src/config.json', '/api/config']:
                    self._handle_config()
                elif self.path == '/favicon.ico':
                    self._handle_favicon()
                # MBTiles tile extraction endpoint
                elif '/mbtiles_tile/' in self.path:
                    self._handle_mbtiles_tile()
                # Do not serve directly via MBTiles; all styles come only from map_tiles filesystem.
                else:
                    self._handle_file_request()
            
            def _serve_index(self):
                """Serve main index.html"""
                try:
                    file_path = os.path.join(os.getcwd(), 'src', 'templates', 'index.html')
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            content = f.read()
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Content-Length', str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                    else:
                        self.send_error(404, 'Index file not found')
                except Exception as e:
                    self.send_error(500, f'Error serving index: {str(e)}')
            
            def _handle_list_regions(self):
                """Handle list_regions API endpoint - Only return regions with actual tile data"""
                try:
                    valid_regions = []
                    map_tiles_dir = os.path.join(os.getcwd(), 'map_tiles')
                    
                    # First, get all regions that have tile data directories
                    tile_data_regions = []
                    if os.path.exists(map_tiles_dir):
                        for item in os.listdir(map_tiles_dir):
                            item_path = os.path.join(map_tiles_dir, item)
                            if (os.path.isdir(item_path) and 
                                not item.startswith('.') and 
                                item != 'metadata'):
                                # Verify this region has raster or vector subdirectories
                                has_tiles = False
                                for tile_type in ['raster', 'vector']:
                                    type_dir = os.path.join(item_path, tile_type)
                                    if os.path.exists(type_dir) and os.path.isdir(type_dir):
                                        # Check if there are any server directories
                                        server_dirs = [d for d in os.listdir(type_dir) 
                                                     if os.path.isdir(os.path.join(type_dir, d))]
                                        if server_dirs:
                                            has_tiles = True
                                            break
                                
                                if has_tiles:
                                    tile_data_regions.append(item)
                    
                    print(f"[INFO] Found {len(tile_data_regions)} regions with tile data: {tile_data_regions}")
                    
                    # Get metadata for validation
                    metadata = server_service._get_cached_metadata()
                    
                    # Only include regions that have both tile data AND metadata
                    for region in tile_data_regions:
                        if metadata and region in metadata:
                            valid_regions.append(region)
                            print(f"[INFO] Region '{region}' has both tile data and metadata")
                        else:
                            # Region has tile data but no metadata - still include but warn
                            valid_regions.append(region)
                            print(f"[WARNING] Region '{region}' has tile data but no metadata")
                    
                    # Sort regions for consistent UI
                    valid_regions = sorted(list(set(valid_regions))) if valid_regions else []
                    
                    # Fallback to hardcoded regions if still no regions
                    if not valid_regions:
                        valid_regions = ["ankara", "istanbul", "qatar", "trabzon", "bursa", "turkiye"]
                        print("[WARNING] No valid regions found, using fallback hardcoded regions")
                    
                    response_data = {"regions": valid_regions}
                    print(f"[SUCCESS] Returning {len(valid_regions)} valid regions: {valid_regions}")
                    self._send_json_response(response_data)
                    
                except Exception as e:
                    print(f"[ERROR] Failed to list regions: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fallback response
                    fallback_data = {"regions": ["ankara", "istanbul", "qatar", "trabzon", "bursa", "turkiye"]}
                    self._send_json_response(fallback_data)
            
            def _handle_region_map_styles(self):
                """Handle region_map_styles API endpoint - New format support"""
                try:
                    clean_path = self.path.split('?', 1)[0].split('#', 1)[0]
                    region_name_enc = clean_path.replace('/region_map_styles/', '').strip()
                    region_name = urllib.parse.unquote(region_name_enc)
                except Exception:
                    region_name = self.path.replace('/region_map_styles/', '').strip()
                
                try:
                    print(f"[INFO] Loading map styles for region: {region_name}")
                    metadata = server_service._get_cached_metadata()
                    available_styles = {'raster': {}, 'vector': {}}
                    
                    # NOTE: Viewing pipeline should not consult config.json for bbox.
                    # Single source of truth is metadata. If metadata is missing,
                    # we return no bbox instead of falling back to config.
                    region_bbox = None
                    
                    if metadata and region_name in metadata:
                        region_data = metadata[region_name]
                        print(f"[INFO] Found metadata for region: {region_name}")
                        
                        # New format: layers contains layer_type -> layer_name -> layer_info
                        if 'layers' in region_data:
                            layers_data = region_data['layers']
                            for layer_type in ['raster', 'vector']:
                                if layer_type in layers_data:
                                    type_layers = layers_data[layer_type]
                                    for layer_name, layer_info in type_layers.items():
                                        # Include only offline ones (filesystem or local mbtiles in config)
                                        if server_service._is_offline_layer(region_name, layer_type, layer_name):
                                            available_styles[layer_type][layer_name] = {
                                                'min_zoom': layer_info.get('min_zoom', 10),
                                                'max_zoom': layer_info.get('max_zoom', 15),
                                                'available_zooms': layer_info.get('available_zooms', []),
                                                'tile_count': layer_info.get('tile_count', 0),
                                                'total_size': layer_info.get('total_size', 0),
                                                'last_updated': layer_info.get('last_updated', ''),
                                                'type': layer_info.get('type', layer_type),
                                                'source': 'filesystem' if server_service._has_filesystem_tiles(region_name, layer_type, layer_name) else 'mbtiles'
                                            }
                            
                            print(f"[INFO] Loaded styles from metadata: raster={len(available_styles['raster'])}, vector={len(available_styles['vector'])}")
                    
                    # Add local MBTiles servers from config
                    # IMPORTANT: Do NOT inject local MBTiles servers into styles.
                    # Styles must be derived strictly from filesystem tiles under map_tiles/.
                    
                    # If not present in metadata, scan filesystem
                    if not any(available_styles['raster']) and not any(available_styles['vector']):
                        print(f"[INFO] No metadata found, scanning filesystem for region: {region_name}")
                        map_tiles_dir = os.path.join(os.getcwd(), 'map_tiles', region_name)
                        # Try diacritics-insensitive match if directory not found
                        if not os.path.exists(map_tiles_dir):
                            real_region_dir = server_service._resolve_region_directory_name(region_name)
                            map_tiles_dir = os.path.join(os.getcwd(), 'map_tiles', real_region_dir)
                        
                        if os.path.exists(map_tiles_dir):
                            for layer_type in ['raster', 'vector']:
                                layer_type_dir = os.path.join(map_tiles_dir, layer_type)
                                if os.path.exists(layer_type_dir):
                                    for layer_name in os.listdir(layer_type_dir):
                                        layer_path = os.path.join(layer_type_dir, layer_name)
                                        if os.path.isdir(layer_path):
                                            # Scan for available zoom levels
                                            available_zooms = []
                                            for zoom_dir in os.listdir(layer_path):
                                                if zoom_dir.isdigit():
                                                    available_zooms.append(int(zoom_dir))
                                            
                                            available_zooms.sort()
                                            min_zoom = min(available_zooms) if available_zooms else 10
                                            max_zoom = max(available_zooms) if available_zooms else 15
                                            # Calculate tile_count (skip style if zero)
                                            tile_count = 0
                                            try:
                                                for root, dirs, files in os.walk(layer_path):
                                                    tile_count += sum(1 for fn in files if fn.lower().endswith(('.png', '.jpg', '.jpeg')))
                                            except Exception:
                                                tile_count = 0
                                            if tile_count == 0 and not available_zooms:
                                                continue
                                            
                                            available_styles[layer_type][layer_name] = {
                                                'min_zoom': min_zoom,
                                                'max_zoom': max_zoom,
                                                'available_zooms': available_zooms,
                                                'tile_count': tile_count,
                                                'total_size': 0,
                                                'last_updated': '',
                                                'type': layer_type,
                                                'source': 'filesystem'
                                            }
                            
                            print(f"[INFO] Filesystem scan results: raster={len(available_styles['raster'])}, vector={len(available_styles['vector'])}")
                    
                    # Add region info to response
                    # Prefer bbox from config; if missing, fall back to metadata's bbox
                    metadata_bbox = None
                    try:
                        if metadata and region_name in metadata:
                            region_meta = metadata[region_name]
                            # Metadata format stores bbox at top-level
                            if isinstance(region_meta, dict):
                                metadata_bbox = region_meta.get('bbox')
                    except Exception:
                        metadata_bbox = None

                    effective_bbox = metadata_bbox

                    region_info = {
                        'bbox': effective_bbox,
                        'center': server_service._calculate_bbox_center(effective_bbox) if effective_bbox else None
                    }
                    
                    response_data = {
                        'raster': available_styles['raster'],
                        'vector': available_styles['vector'],
                        'region_info': region_info
                    }
                    
                    # Log final results
                    total_styles = len(available_styles['raster']) + len(available_styles['vector'])
                    print(f"[SUCCESS] Returning {total_styles} styles for {region_name}")
                    if available_styles['raster']:
                        print(f"[INFO] Raster styles: {list(available_styles['raster'].keys())}")
                    if available_styles['vector']:
                        print(f"[INFO] Vector styles: {list(available_styles['vector'].keys())}")
                    if region_bbox:
                        print(f"[INFO] Region bbox: {region_bbox}")
                    
                    self._send_json_response(response_data)
                    
                except Exception as e:
                    print(f"[ERROR] Failed to get region map styles for {region_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Empty fallback without consulting config.json
                    region_bbox = None
                    fallback_response = {
                        'raster': {}, 
                        'vector': {},
                        'region_info': {
                            'bbox': region_bbox,
                            'center': None
                        }
                    }
                    self._send_json_response(fallback_response)
            
            def _handle_config(self):
                """Handle config.json requests"""
                try:
                    config_path = os.path.join(os.getcwd(), 'config.json')
                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config_content = f.read()
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(config_content.encode())
                    else:
                        self.send_error(404, 'Config file not found')
                except Exception as e:
                    self.send_error(500, f'Error reading config: {str(e)}')

            # _handle_region_polygon removed per request: masking moved out of server
            
            def _handle_favicon(self):
                """Handle favicon.ico request"""
                self.send_response(204)  # No content
                self.end_headers()

            def _handle_inspect_mbtiles(self):
                """Inspect an MBTiles file and return vector layer names and metadata"""
                try:
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(self.path)
                    query = parse_qs(parsed.query)
                    server_name = None
                    if 'server' in query:
                        server_name = query['server'][0]
                    elif 'name' in query:
                        server_name = query['name'][0]

                    if not server_name:
                        self.send_error(400, 'Missing server parameter')
                        return

                    # Load config and find server
                    config_path = os.path.join(os.getcwd(), 'config.json')
                    if not os.path.exists(config_path):
                        self.send_error(500, 'Config file not found')
                        return

                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)

                    server_config = None
                    for s in config_data.get('servers', []):
                        if s.get('name') == server_name and s.get('type') == 'local' and s.get('source_type') == 'mbtiles':
                            server_config = s
                            break

                    if not server_config:
                        self.send_error(404, f'Server not found: {server_name}')
                        return

                    mbtiles_path = os.path.join(os.getcwd(), server_config['path'])
                    if not os.path.exists(mbtiles_path):
                        self.send_error(404, f'MBTiles not found: {server_config["path"]}')
                        return

                    # Read metadata table
                    layers = []
                    raw_meta = {}
                    try:
                        with sqlite3.connect(mbtiles_path) as conn:
                            cur = conn.cursor()
                            cur.execute("SELECT name, value FROM metadata")
                            meta_rows = cur.fetchall()
                            meta = {k: v for (k, v) in meta_rows}
                            raw_meta = meta
                            # 'json' may contain vector_layers array
                            vector_layers = None
                            if 'json' in meta:
                                try:
                                    j = json.loads(meta['json'])
                                    if isinstance(j, dict) and 'vector_layers' in j:
                                        vector_layers = j['vector_layers']
                                except Exception:
                                    pass
                            if vector_layers is None and 'vector_layers' in meta:
                                try:
                                    vector_layers = json.loads(meta['vector_layers'])
                                except Exception:
                                    vector_layers = None
                            if isinstance(vector_layers, list):
                                for lyr in vector_layers:
                                    name = None
                                    if isinstance(lyr, dict):
                                        name = lyr.get('id') or lyr.get('name')
                                    if name:
                                        layers.append(name)
                    except Exception as e:
                        print(f"[ERROR] Failed to inspect MBTiles: {e}")

                    response = {
                        'server': server_name,
                        'path': server_config['path'],
                        'tile_type': server_config.get('tile_type'),
                        'layers': layers,
                        'metadata': raw_meta,
                    }
                    self._send_json_response(response)
                except Exception as e:
                    self.send_error(500, f'Error inspecting mbtiles: {str(e)}')

            def _handle_tile_extents(self):
                """Compute per-zoom tile extents for filesystem layers: /tile_extents/<region>/<type>/<server>"""
                try:
                    clean_path = self.path.split('?', 1)[0].split('#', 1)[0]
                    parts = clean_path.strip('/').split('/')
                    if len(parts) < 4:
                        self.send_error(400, 'Invalid tile_extents URL')
                        return
                    _, region_name, layer_type, server_name = parts[:4]
                    # Decode percent-encoded path parts to support diacritics
                    region_name = urllib.parse.unquote(region_name)
                    layer_type = urllib.parse.unquote(layer_type)
                    server_name = urllib.parse.unquote(server_name)

                    # Cache key
                    cache_key = f"{region_name}:{layer_type}:{server_name}"
                    now = time.time()
                    last = server_service._tile_extents_cache_time.get(cache_key)
                    if cache_key in server_service._tile_extents_cache and last and now - last < server_service._tile_extents_ttl:
                        self._send_json_response(server_service._tile_extents_cache[cache_key])
                        return

                    # Scan filesystem
                    base_dir = os.path.join(os.getcwd(), 'map_tiles', server_service._resolve_region_directory_name(region_name), layer_type, server_name)
                    if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
                        self._send_json_response({'available_zooms': [], 'extents': {}, 'tile_count': 0})
                        return

                    total_tiles = 0
                    extents = {}
                    for z_name in os.listdir(base_dir):
                        if not z_name.isdigit():
                            continue
                        z = int(z_name)
                        z_dir = os.path.join(base_dir, z_name)
                        if not os.path.isdir(z_dir):
                            continue
                        min_x = None
                        max_x = None
                        min_y = None
                        max_y = None
                        z_tile_count = 0
                        for x_name in os.listdir(z_dir):
                            if not x_name.isdigit():
                                continue
                            x = int(x_name)
                            x_dir = os.path.join(z_dir, x_name)
                            if not os.path.isdir(x_dir):
                                continue
                            for fn in os.listdir(x_dir):
                                ext = os.path.splitext(fn)[1].lower()
                                if layer_type == 'vector':
                                    if ext not in ('.pbf', '.mvt'):
                                        continue
                                else:
                                    if ext not in ('.png', '.jpg', '.jpeg'):
                                        continue
                                y_name = fn.split('.')[0]
                                if not y_name.isdigit():
                                    continue
                                y = int(y_name)
                                min_x = x if min_x is None else min(min_x, x)
                                max_x = x if max_x is None else max(max_x, x)
                                min_y = y if min_y is None else min(min_y, y)
                                max_y = y if max_y is None else max(max_y, y)
                                z_tile_count += 1
                                total_tiles += 1
                        if z_tile_count > 0:
                            extents[str(z)] = {
                                'minX': min_x,
                                'maxX': max_x,
                                'minY': min_y,
                                'maxY': max_y,
                                'tile_count': z_tile_count
                            }

                    response = {
                        'available_zooms': sorted([int(k) for k in extents.keys()]),
                        'extents': extents,
                        'tile_count': total_tiles
                    }
                    server_service._tile_extents_cache[cache_key] = response
                    server_service._tile_extents_cache_time[cache_key] = now
                    self._send_json_response(response)
                except Exception as e:
                    self.send_error(500, f'Error computing tile extents: {str(e)}')

            def _handle_tile_index(self):
                """Return available tiles for a specific zoom: /tile_index/<region>/<type>/<server>/<z>"""
                try:
                    clean_path = self.path.split('?', 1)[0].split('#', 1)[0]
                    parts = clean_path.strip('/').split('/')
                    if len(parts) < 5:
                        self.send_error(400, 'Invalid tile_index URL')
                        return
                    _, region_name, layer_type, server_name, z_name = parts[:5]
                    # Decode percent-encoded path parts to support diacritics
                    region_name = urllib.parse.unquote(region_name)
                    layer_type = urllib.parse.unquote(layer_type)
                    server_name = urllib.parse.unquote(server_name)
                    if not z_name.isdigit():
                        self.send_error(400, 'Invalid zoom level')
                        return
                    z = int(z_name)

                    cache_key = f"{region_name}:{layer_type}:{server_name}:{z}"
                    now = time.time()
                    last = server_service._tile_index_cache_time.get(cache_key)
                    if cache_key in server_service._tile_index_cache and last and now - last < server_service._tile_index_ttl:
                        self._send_json_response(server_service._tile_index_cache[cache_key])
                        return

                    base_dir = os.path.join(os.getcwd(), 'map_tiles', server_service._resolve_region_directory_name(region_name), layer_type, server_name, str(z))
                    index = {}
                    total = 0
                    if os.path.exists(base_dir) and os.path.isdir(base_dir):
                        for x_name in os.listdir(base_dir):
                            if not x_name.isdigit():
                                continue
                            x = int(x_name)
                            x_dir = os.path.join(base_dir, x_name)
                            if not os.path.isdir(x_dir):
                                continue
                            ys = []
                            for fn in os.listdir(x_dir):
                                ext = os.path.splitext(fn)[1].lower()
                                if layer_type == 'vector':
                                    if ext not in ('.pbf', '.mvt'):
                                        continue
                                else:
                                    if ext not in ('.png', '.jpg', '.jpeg'):
                                        continue
                                y_name = fn.split('.')[0]
                                if y_name.isdigit():
                                    ys.append(int(y_name))
                            if ys:
                                index[str(x)] = sorted(ys)
                                total += len(ys)

                    response = { 'z': z, 'tiles': index, 'tile_count': total }
                    server_service._tile_index_cache[cache_key] = response
                    server_service._tile_index_cache_time[cache_key] = now
                    self._send_json_response(response)
                except Exception as e:
                    self.send_error(500, f'Error computing tile index: {str(e)}')
            
            def _handle_file_request(self):
                """Handle file requests with optimized path resolution"""
                try:
                    # Clean path
                    clean_path = self.path.split('?')[0].split('#')[0]
                    rel_path = clean_path[1:] if clean_path.startswith('/') else clean_path
                    # Decode percent-encoding so filesystem paths with diacritics resolve correctly
                    rel_path = urllib.parse.unquote(rel_path)
                    
                    # Special handling for static assets
                    if clean_path.startswith('/src/static/') or clean_path.startswith('/static/'):
                        if clean_path.startswith('/static/'):
                            file_path = os.path.join(os.getcwd(), 'src', rel_path)
                        else:
                            file_path = os.path.join(os.getcwd(), rel_path)
                    else:
                        file_path = os.path.join(os.getcwd(), rel_path)
                    
                    # Security check
                    if not self._is_safe_path(file_path):
                        self.send_error(403, 'Access denied')
                        return
                    
                    # Serve file if exists
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        self._serve_file(file_path)
                    else:
                        # Fallback: If request matches map tile XYZ pattern, try TMS-inverted Y
                        try:
                            # Accept both patterns:
                            # 1) Static filesystem: map_tiles/REGION/(raster|vector)/SERVER/z/x/y.ext
                            # 2) MBTiles endpoint path: map_tiles/REGION/(raster|vector)/SERVER/mbtiles_tile/z/x/y.ext
                            parts = rel_path.split('/')
                            if parts and parts[0] == 'map_tiles':
                                z_idx = None
                                x_idx = None
                                y_idx = None
                                if len(parts) >= 8 and parts[4] == 'mbtiles_tile':
                                    # mbtiles pattern
                                    z_idx, x_idx, y_idx = 5, 6, 7
                                elif len(parts) >= 7:
                                    # static pattern
                                    z_idx, x_idx, y_idx = 4, 5, 6
                                if z_idx is not None:
                                    z_str, x_str, y_file = parts[z_idx], parts[x_idx], parts[y_idx]
                                    if z_str.isdigit() and x_str.isdigit() and '.' in y_file:
                                        y_str, ext = y_file.split('.', 1)
                                        if y_str.isdigit():
                                            z = int(z_str)
                                            x = int(x_str)
                                            y = int(y_str)
                                            # Compute TMS y and try alternate path
                                            tms_y = (2 ** z) - 1 - y
                                            new_parts = parts.copy()
                                            new_parts[y_idx] = f"{tms_y}.{ext}"
                                            alt_file_path = os.path.join(os.getcwd(), *new_parts)
                                            if self._is_safe_path(alt_file_path) and os.path.exists(alt_file_path) and os.path.isfile(alt_file_path):
                                                self._serve_file(alt_file_path)
                                                return
                                            # Also try alternate raster extensions with TMS y
                                            try:
                                                _, original_ext = os.path.splitext(parts[y_idx])
                                                raster_exts = ['.png', '.jpg', '.jpeg']
                                                for alt_ext in raster_exts:
                                                    if alt_ext.lower() == original_ext.lower():
                                                        continue
                                                    new_parts_alt = parts.copy()
                                                    new_parts_alt[y_idx] = f"{tms_y}{alt_ext}"
                                                    candidate_path = os.path.join(os.getcwd(), *new_parts_alt)
                                                    if self._is_safe_path(candidate_path) and os.path.exists(candidate_path) and os.path.isfile(candidate_path):
                                                        self._serve_file(candidate_path)
                                                        return
                                            except Exception:
                                                pass
                        except Exception:
                            pass

                        # Fallback: If raster extension mismatches (png vs jpg), try alternate extensions
                        try:
                            base, ext = os.path.splitext(file_path)
                            ext_lower = ext.lower()
                            raster_exts = ['.png', '.jpg', '.jpeg']
                            if ext_lower in raster_exts:
                                for alt_ext in raster_exts:
                                    if alt_ext == ext_lower:
                                        continue
                                    candidate = base + alt_ext
                                    if self._is_safe_path(candidate) and os.path.exists(candidate) and os.path.isfile(candidate):
                                        self._serve_file(candidate)
                                        return
                        except Exception:
                            pass

                        self.send_error(404, f'File not found: {clean_path}')
                        
                except Exception as e:
                    self.send_error(500, f'Error: {str(e)}')
            
            def _is_safe_path(self, file_path: str) -> bool:
                """Check if path is safe (prevent directory traversal)"""
                try:
                    canonical_path = os.path.realpath(file_path)
                    base_path = os.path.realpath(os.getcwd())
                    return canonical_path.startswith(base_path)
                except:
                    return False
            
            def _serve_file(self, file_path: str):
                """Serve a file with appropriate headers"""
                try:
                    content_type = self._get_content_type(file_path)
                    
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # For vector tiles served as static files, normalize transport encoding to GZIP and set header
                    is_vector_tile_path = file_path.lower().endswith('.pbf') or file_path.lower().endswith('.mvt')
                    if is_vector_tile_path:
                        try:
                            # Detect original encoding and ensure we serve gzip
                            detected = 'raw'
                            if len(content) >= 2 and content[0:2] == b'\x1f\x8b':
                                detected = 'gzip'
                                # already gzip
                                pass
                            elif len(content) >= 2 and content[0] == 0x78 and content[1] in (0x01, 0x9C, 0xDA):
                                detected = 'zlib'
                                raw = zlib.decompress(content)
                                content = gzip.compress(raw)
                            else:
                                # assume raw pbf -> gzip it
                                content = gzip.compress(content)
                            # Stash detected format for headers
                            self._last_detected_vector_format = detected
                        except Exception:
                            # If normalization fails, fall back to original bytes
                            pass

                    # Pre-compute caching fingerprint for conditional requests
                    etag_value = None
                    try:
                        import hashlib
                        etag_value = hashlib.md5(content).hexdigest()
                    except Exception:
                        etag_value = None

                    # Conditional GET handling (If-None-Match)
                    if etag_value:
                        incoming_etag = self.headers.get('If-None-Match')
                        if incoming_etag:
                            incoming_etag = incoming_etag.strip()
                            # Accept both weak and strong matches
                            if incoming_etag == f'W/"{etag_value}"' or incoming_etag == f'"{etag_value}"' or incoming_etag == etag_value:
                                self.send_response(304)
                                # Mirror cache-related headers so caches keep the entry fresh
                                self.send_header('Cache-Control', 'public, max-age=86400')
                                self.send_header('Vary', 'Accept-Encoding')
                                self.send_header('ETag', f'W/"{etag_value}"')
                                self.end_headers()
                                return

                    self.send_response(200)
                    self.send_header('Content-type', content_type)
                    self.send_header('Content-Length', str(len(content)))
                    # If serving vector tiles (.pbf/.mvt), send strong caching and gzip Content-Encoding
                    try:
                        is_vector_tile = file_path.lower().endswith('.pbf') or file_path.lower().endswith('.mvt')
                        if is_vector_tile:
                            # Strong caching and defensive headers for tiles
                            self.send_header('Cache-Control', 'public, max-age=86400')
                            self.send_header('Vary', 'Accept-Encoding')
                            self.send_header('X-Content-Type-Options', 'nosniff')
                            # ETag for cache revalidation (weak)
                            try:
                                etag = etag_value or ''
                                if etag:
                                    self.send_header('ETag', f'W/"{etag}"')
                            except Exception:
                                pass
                        # Always set gzip since we normalized to gzip above when vector tile
                        if is_vector_tile:
                            self.send_header('Content-Encoding', 'gzip')
                            detected = getattr(self, '_last_detected_vector_format', None)
                            if detected:
                                self.send_header('X-Tile-Detected-Format', detected)
                    except Exception:
                        pass
                    
                    # Cache control for static assets
                    if any(file_path.endswith(ext) for ext in ['.js', '.css']):
                        self.send_header('Cache-Control', 'no-cache')  # Dev mode
                    elif any(file_path.endswith(ext) for ext in ['.png', '.jpg', '.gif']):
                        self.send_header('Cache-Control', 'public, max-age=3600')
                    
                    self.end_headers()
                    self.wfile.write(content)
                    
                except Exception as e:
                    self.send_error(500, f'Error serving file: {str(e)}')
            
            def _send_json_response(self, data: dict):
                """Send JSON response with proper headers"""
                response_json = json.dumps(data)
                response_bytes = response_json.encode('utf-8')
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response_bytes)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(response_bytes)
            
            def _get_content_type(self, file_path: str) -> str:
                """Get content type based on file extension"""
                ext = os.path.splitext(file_path)[1].lower()
                content_types = {
                    '.html': 'text/html',
                    '.js': 'application/javascript',
                    '.css': 'text/css',
                    '.json': 'application/json',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.svg': 'image/svg+xml',
                    '.ico': 'image/x-icon',
                    '.pbf': 'application/vnd.mapbox-vector-tile',
                    '.mvt': 'application/vnd.mapbox-vector-tile',
                }
                return content_types.get(ext, 'application/octet-stream')
            
            def _handle_mbtiles_tile(self):
                """Handle mbtiles tile requests - extract tiles from .mbtiles files"""
                try:
                    # Parse URL pattern: /map_tiles/region/type/server_name/mbtiles_tile/z/x/y.ext
                    # Example: /map_tiles/bursa/raster/Local_Satellite_Turkey/mbtiles_tile/9/296/193.jpeg
                    
                    clean_path = self.path.split('?', 1)[0].split('#', 1)[0]
                    path_parts = [urllib.parse.unquote(p) for p in clean_path.strip('/').split('/')]
                    if len(path_parts) < 7:
                        self.send_error(400, 'Invalid mbtiles tile URL format')
                        return
                    
                    # Extract path components
                    region_name = path_parts[1]
                    tile_type = path_parts[2]  # 'raster' or 'vector'
                    server_name = path_parts[3]
                    # path_parts[4] should be 'mbtiles_tile'
                    z = int(path_parts[5])
                    x = int(path_parts[6])
                    y_with_ext = path_parts[7]
                    
                    # Extract y and extension
                    if '.' in y_with_ext:
                        y = int(y_with_ext.split('.')[0])
                        ext = y_with_ext.split('.')[1]
                    else:
                        y = int(y_with_ext)
                        ext = 'png'  # default
                    
                    print(f"[INFO] MBTiles tile request: {region_name}/{server_name} - {z}/{x}/{y}.{ext}")
                    
                    # Find corresponding mbtiles file from config
                    config_path = os.path.join(os.getcwd(), 'config.json')
                    if not os.path.exists(config_path):
                        self.send_error(500, 'Config file not found')
                        return
                    
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    
                    # Find server config
                    server_config = None
                    for server in config_data.get('servers', []):
                        if server['name'] == server_name and server.get('type') == 'local':
                            server_config = server
                            break
                    
                    if not server_config:
                        self.send_error(404, f'Local server {server_name} not found in config')
                        return
                    
                    # Get mbtiles file path
                    mbtiles_path = os.path.join(os.getcwd(), server_config['path'])
                    if not os.path.exists(mbtiles_path):
                        self.send_error(404, f'MBTiles file not found: {server_config["path"]}')
                        return
                    
                    # Extract tile from mbtiles
                    tile_data = server_service._extract_tile_from_mbtiles(mbtiles_path, z, x, y)
                    if tile_data is None:
                        self.send_error(404, f'Tile {z}/{x}/{y} not found in {server_name}')
                        return
                    
                    # Normalize vector tile transport encoding to GZIP and set header
                    if server_config.get('tile_type') == 'vector' and ext.lower() in ['pbf', 'mvt']:
                        try:
                            detected = 'raw'
                            if len(tile_data) >= 2 and tile_data[0:2] == b'\x1f\x8b':
                                detected = 'gzip'
                                # keep as-is
                                pass
                            elif len(tile_data) >= 2 and tile_data[0] == 0x78 and tile_data[1] in (0x01, 0x9C, 0xDA):
                                detected = 'zlib'
                                raw = zlib.decompress(tile_data)
                                tile_data = gzip.compress(raw)
                            else:
                                # assume raw pbf
                                tile_data = gzip.compress(tile_data)
                            self._last_detected_vector_format = detected
                        except Exception:
                            # Keep original if normalization fails
                            pass

                    # Determine content type based on server tile_type and extension
                    if server_config.get('tile_type') == 'vector':
                        content_type = 'application/vnd.mapbox-vector-tile'
                    else:
                        # Raster tile
                        if ext.lower() in ['jpg', 'jpeg']:
                            content_type = 'image/jpeg'
                        elif ext.lower() == 'png':
                            content_type = 'image/png'
                        else:
                            content_type = 'image/png'  # default
                    
                    # MBTiles: compute ETag and handle conditional GET BEFORE writing headers
                    try:
                        import hashlib
                        etag_value = hashlib.md5(tile_data).hexdigest()
                    except Exception:
                        etag_value = None

                    if etag_value:
                        incoming_etag = self.headers.get('If-None-Match')
                        if incoming_etag:
                            incoming_etag = incoming_etag.strip()
                            if incoming_etag in (f'W/"{etag_value}"', f'"{etag_value}"', etag_value):
                                self.send_response(304)
                                self.send_header('Cache-Control', 'public, max-age=86400')
                                self.send_header('Vary', 'Accept-Encoding')
                                self.send_header('ETag', f'W/"{etag_value}"')
                                self.end_headers()
                                return

                    # Send tile response
                    self.send_response(200)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(tile_data)))

                    # Vector tile specific headers
                    is_vector = server_config.get('tile_type') == 'vector'
                    if is_vector:
                        # Strong caching and defensive headers for tiles
                        self.send_header('Cache-Control', 'public, max-age=86400')
                        self.send_header('Vary', 'Accept-Encoding')
                        self.send_header('X-Content-Type-Options', 'nosniff')
                        if etag_value:
                            self.send_header('ETag', f'W/"{etag_value}"')
                        # Always set gzip since we normalized above
                        self.send_header('Content-Encoding', 'gzip')
                        detected = getattr(self, '_last_detected_vector_format', None)
                        if detected:
                            self.send_header('X-Tile-Detected-Format', detected)

                    self.end_headers()
                    self.wfile.write(tile_data)
                    
                    print(f"[SUCCESS] Served mbtiles tile: {z}/{x}/{y} ({len(tile_data)} bytes)")
                    
                except ValueError as e:
                    self.send_error(400, f'Invalid tile coordinates: {str(e)}')
                except Exception as e:
                    print(f"[ERROR] MBTiles tile error: {e}")
                    import traceback
                    traceback.print_exc()
                    self.send_error(500, f'Error serving mbtiles tile: {str(e)}')
        
        return OptimizedHTTPRequestHandler
    
    def _get_cached_metadata(self):
        """Get cached metadata with TTL check - Yeni format desteği"""
        current_time = time.time()
        
        if (self._metadata_cache is None or 
            current_time - self._metadata_cache_time > self._cache_duration):
            
            try:
                # Yeni format (regions dizini) kontrol et
                regions_dir = os.path.join(os.getcwd(), 'map_tiles', 'metadata', 'regions')
                if os.path.exists(regions_dir):
                    self._metadata_cache = {}
                    region_files = [f for f in os.listdir(regions_dir) if f.endswith('.json')]
                    
                    for region_file in region_files:
                        region_name = region_file.replace('.json', '')
                        region_path = os.path.join(regions_dir, region_file)
                        
                        try:
                            with open(region_path, 'r', encoding='utf-8') as f:
                                region_data = json.load(f)
                                self._metadata_cache[region_name] = region_data
                        except Exception as e:
                            print(f"[WARNING] Failed to load region {region_name}: {e}")
                    
                    print(f"[INFO] Metadata loaded from regions directory: {len(self._metadata_cache)} regions")
                    
                else:
                    # Fallback: Eski format (tiles_metadata.json)
                    metadata_path = os.path.join(os.getcwd(), 'map_tiles', 'metadata', 'tiles_metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            self._metadata_cache = json.load(f)
                            print(f"[INFO] Metadata loaded from tiles_metadata.json: {len(self._metadata_cache)} regions")
                    else:
                        self._metadata_cache = {}
                        print("[WARNING] No metadata found")
                
                self._metadata_cache_time = current_time
                
            except Exception as e:
                print(f"[ERROR] Failed to load metadata: {e}")
                self._metadata_cache = {}
        
        return self._metadata_cache
    
    def _normalize_name(self, name: str) -> str:
        try:
            import unicodedata
            s = unicodedata.normalize('NFD', name)
            s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
        except Exception:
            s = name
        # Turkish-specific mappings
        replacements = {
            'ı': 'i', 'İ': 'i', 'ş': 's', 'Ş': 's', 'ğ': 'g', 'Ğ': 'g',
            'ç': 'c', 'Ç': 'c', 'ö': 'o', 'Ö': 'o', 'ü': 'u', 'Ü': 'u'
        }
        for k, v in replacements.items():
            s = s.replace(k, v)
        return s.lower().strip()

    def _resolve_region_directory_name(self, region_name: str) -> str:
        """Resolve actual region directory name under map_tiles with diacritics-insensitive matching"""
        base_dir = os.path.join(os.getcwd(), 'map_tiles')
        candidate = os.path.join(base_dir, region_name)
        if os.path.exists(candidate):
            return region_name
        try:
            target_norm = self._normalize_name(region_name)
            for entry in os.listdir(base_dir):
                p = os.path.join(base_dir, entry)
                if os.path.isdir(p):
                    if self._normalize_name(entry) == target_norm:
                        return entry
        except Exception:
            pass
        return region_name
    
    def _get_region_bbox_from_config(self, region_name):
        """Get region bbox from config.json"""
        try:
            config_path = os.path.join(os.getcwd(), 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                if 'regions' in config_data and region_name in config_data['regions']:
                    bbox = config_data['regions'][region_name].get('bbox')
                    if bbox and len(bbox) == 4:
                        # Config format: [minLng, minLat, maxLng, maxLat]
                        return bbox
            return None
        except Exception as e:
            print(f"[ERROR] Failed to get bbox for region {region_name}: {e}")
            return None
    
    def _calculate_bbox_center(self, bbox):
        """Calculate center point from bbox [minLng, minLat, maxLng, maxLat]"""
        if not bbox or len(bbox) != 4:
            return None
        
        # Validate bbox values to prevent NaN
        if any(not isinstance(x, (int, float)) or math.isnan(x) for x in bbox):
            print(f"[WARNING] Invalid bbox values: {bbox}")
            return None
        
        center_lng = (bbox[0] + bbox[2]) / 2  # (minLng + maxLng) / 2
        center_lat = (bbox[1] + bbox[3]) / 2  # (minLat + maxLat) / 2
        
        # Validate calculated center
        if math.isnan(center_lng) or math.isnan(center_lat):
            print(f"[WARNING] Calculated center contains NaN: [{center_lng}, {center_lat}] from bbox {bbox}")
            return None
            
        return [center_lng, center_lat]
    
    def _extract_tile_from_mbtiles(self, mbtiles_path: str, z: int, x: int, y: int):
        """Extract a tile from MBTiles database"""
        try:
            with sqlite3.connect(mbtiles_path) as conn:
                cursor = conn.cursor()
                
                # MBTiles uses TMS coordinate system (inverted Y)
                # Convert from XYZ to TMS
                tms_y = (2 ** z) - 1 - y
                
                # Try standard MBTiles format first
                cursor.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                    (z, x, tms_y)
                )
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                
                # Try TMS format (images + map tables)
                cursor.execute(
                    "SELECT tile_id FROM map WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                    (z, x, tms_y)
                )
                tile_id_result = cursor.fetchone()
                
                if tile_id_result:
                    tile_id = tile_id_result[0]
                    cursor.execute("SELECT tile_data FROM images WHERE tile_id = ?", (tile_id,))
                    image_result = cursor.fetchone()
                    if image_result:
                        return image_result[0]
                
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to extract tile {z}/{x}/{y} from {mbtiles_path}: {e}")
            return None
    
    def _get_local_servers_for_region(self, region_name: str, region_bbox: list):
        """Get local MBTiles servers that cover the given region"""
        try:
            config_path = os.path.join(os.getcwd(), 'config.json')
            if not os.path.exists(config_path):
                return []
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            local_servers = []
            for server in config_data.get('servers', []):
                if server.get('type') == 'local' and server.get('source_type') == 'mbtiles':
                    # File existence check: only include if MBTiles file exists on disk
                    mbtiles_path = os.path.join(os.getcwd(), server.get('path', ''))
                    if not (mbtiles_path and os.path.exists(mbtiles_path)):
                        continue
                    # Check if server bounds intersect with region bounds
                    server_bounds = server.get('bounds')
                    if server_bounds and self._bounds_intersect(region_bbox, server_bounds):
                        local_servers.append(server)
            
            print(f"[INFO] Found {len(local_servers)} local servers for region {region_name}")
            return local_servers
            
        except Exception as e:
            print(f"[ERROR] Failed to get local servers for region {region_name}: {e}")
            return []

    def _get_mbtiles_zoom_levels(self, server_info: dict):
        """Read distinct zoom levels from an MBTiles file for accurate min/max/available_zooms"""
        try:
            mbtiles_path = os.path.join(os.getcwd(), server_info.get('path', ''))
            if not os.path.exists(mbtiles_path):
                return None
            with sqlite3.connect(mbtiles_path) as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT DISTINCT zoom_level FROM tiles")
                    rows = cur.fetchall()
                except Exception:
                    return None
                levels = sorted({int(r[0]) for r in rows if r and r[0] is not None})
                return levels if levels else None
        except Exception as e:
            print(f"[WARNING] Failed reading zoom levels from {server_info.get('name')}: {e}")
            return None
    
    def _bounds_intersect(self, bbox1, bbox2):
        """Check if two bounding boxes intersect"""
        try:
            # bbox format: [minLng, minLat, maxLng, maxLat]
            if not bbox1 or not bbox2 or len(bbox1) != 4 or len(bbox2) != 4:
                return False
            
            # Check if bboxes intersect
            return not (bbox1[2] < bbox2[0] or bbox1[0] > bbox2[2] or 
                       bbox1[3] < bbox2[1] or bbox1[1] > bbox2[3])
        except:
            return False

    def _has_filesystem_tiles(self, region_name: str, layer_type: str, layer_name: str) -> bool:
        try:
            base_path = os.path.join(os.getcwd(), 'map_tiles', self._resolve_region_directory_name(region_name), layer_type, layer_name)
            return os.path.exists(base_path) and os.path.isdir(base_path)
        except Exception:
            return False

    def _is_offline_layer(self, region_name: str, layer_type: str, layer_name: str) -> bool:
        """Only consider a layer offline if it exists on filesystem under map_tiles."""
        return self._has_filesystem_tiles(region_name, layer_type, layer_name)

    def _handle_list_regions(self):
        """Handle list_regions API endpoint - Yeni format desteği"""
        try:
            metadata = self._get_cached_metadata()
            regions = list(metadata.keys()) if metadata else []
            
            # Eğer metadata boşsa, regions dizinini tara
            if not regions:
                regions_dir = os.path.join(os.getcwd(), 'map_tiles', 'metadata', 'regions')
                if os.path.exists(regions_dir):
                    region_files = [f.replace('.json', '') for f in os.listdir(regions_dir) if f.endswith('.json')]
                    regions = region_files
            
            # Hala boşsa, map_tiles dizinini tara
            if not regions:
                map_tiles_dir = os.path.join(os.getcwd(), 'map_tiles')
                if os.path.exists(map_tiles_dir):
                    for item in os.listdir(map_tiles_dir):
                        item_path = os.path.join(map_tiles_dir, item)
                        if os.path.isdir(item_path) and not item.startswith('.'):
                            regions.append(item)
            
            # Fallback to hardcoded regions if still no regions
            if not regions:
                regions = ["ankara", "istanbul", "qatar", "trabzon", "bursa", "turkiye"]
            
            response_data = {"regions": sorted(regions)}
            self._send_json_response(response_data)
            
        except Exception as e:
            print(f"[ERROR] Failed to list regions: {e}")
            # Fallback response
            fallback_data = {"regions": ["ankara", "istanbul", "qatar", "trabzon", "bursa", "turkiye"]}
            self._send_json_response(fallback_data)
    
    def start(self):
        """Start the optimized HTTP server"""
        handler = self.create_request_handler()
        
        try:
            # Synchronize metadata before starting server
            print("=" * 60)
            print("STARTING METADATA SYNCHRONIZATION")
            print("=" * 60)
            
            if sync_metadata_on_startup:
                try:
                    sync_results = sync_metadata_on_startup(os.getcwd())
                    if sync_results.get('success', False):
                        print(f"[OK] Metadata sync completed successfully:")
                        print(f"   - {sync_results['regions_synced']} regions synced")
                        print(f"   - {sync_results['layers_added']} layers added")
                        print(f"   - {sync_results['layers_updated']} layers updated")
                        print(f"   - {sync_results['layers_removed']} layers removed")
                        print(f"   - {sync_results['total_tiles_counted']:,} tiles counted")
                        print(f"   - {sync_results['total_size_calculated'] / (1024*1024):.1f} MB calculated")
                        if sync_results['errors']:
                            print(f"   - {len(sync_results['errors'])} warnings/errors logged")
                    else:
                        print("[ERROR] Metadata sync encountered errors (see logs)")
                        for error in sync_results.get('errors', []):
                            print(f"   Error: {error}")
                except Exception as e:
                    print(f"[ERROR] Metadata sync failed: {e}")
                    print("   Server will start with existing metadata")
            else:
                print("[WARNING] Metadata synchronization unavailable (import failed)")
            
            print("=" * 60)
            
            self.httpd = socketserver.TCPServer(("", self.port), handler)
            print(f"Server started at http://localhost:{self.port}")
            print(f"Serving from: {os.getcwd()}")
            
            # Quick diagnostics
            config_path = os.path.join(os.getcwd(), 'config.json')
            if os.path.exists(config_path):
                print("Config file found")
            
            # Check for new metadata format (regions directory)
            regions_dir = os.path.join(os.getcwd(), 'map_tiles', 'metadata', 'regions')
            if os.path.exists(regions_dir):
                region_files = [f for f in os.listdir(regions_dir) if f.endswith('.json')]
                print(f"Metadata found: {len(region_files)} region files (new format)")
            else:
                # Fallback: check old metadata format
                metadata_path = os.path.join(os.getcwd(), 'map_tiles', 'metadata', 'tiles_metadata.json')
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        print(f"Metadata found: {len(metadata)} regions (legacy format)")
            
            print("\nOpen http://localhost:8080 in your browser")
            print("Press Ctrl+C to stop\n")
            
            self.httpd.serve_forever()
            
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"Error: Port {self.port} is already in use")
            else:
                print(f"Server error: {e}")
        except KeyboardInterrupt:
            print("\nServer stopped by user")
        finally:
            if hasattr(self, 'httpd'):
                self.httpd.server_close()
    
    def stop(self):
        """Stop the HTTP server"""
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
            self.httpd.server_close()
            print("Server stopped")