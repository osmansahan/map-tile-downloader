import json
import os
from typing import Dict, Any, List, Optional
from interfaces.tile_server import IConfigLoader
from models.tile_server import TileServer, Region, DownloadConfig
from models.local_source import LocalSource
from exceptions.tile_downloader_exceptions import ConfigurationError, ValidationError


class ConfigService(IConfigLoader):
    """Service for loading and validating configuration"""
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            if not os.path.exists(config_path):
                raise ConfigurationError(f"Config file {config_path} not found!")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if not self.validate_config(config):
                raise ConfigurationError("Invalid configuration format")
            
            return self._process_config(config)
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {config_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading config: {e}")
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure"""
        required_keys = ['regions', 'servers', 'output_dir', 'max_workers_per_server', 
                        'retry_attempts', 'timeout']
        
        for key in required_keys:
            if key not in config:
                raise ValidationError(f"Missing required key: {key}")
        
        if not isinstance(config['regions'], dict):
            raise ValidationError("regions must be a dictionary")
        
        if not isinstance(config['servers'], list):
            raise ValidationError("servers must be a list")
        
        return True
    
    def _process_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Process and enhance configuration"""
        # Convert server definitions to TileServer objects
        server_defs = {}
        local_sources = {}
        
        for server_data in config['servers']:
            if isinstance(server_data, dict):
                server_type = server_data.get('type', 'http')
                
                if server_type == 'http':
                    # Online server
                    server = TileServer(
                        name=server_data['name'],
                        url=server_data['url'],
                        headers=server_data.get('headers', {}),
                        tile_type=server_data.get('tile_type', 'raster')
                    )
                    server_defs[server_data['name']] = server
                elif server_type == 'local':
                    # Local source
                    local_source = LocalSource(
                        name=server_data['name'],
                        path=server_data['path'],
                        source_type=server_data.get('source_type', 'mbtiles'),
                        tile_type=server_data.get('tile_type', 'raster'),
                        bounds=server_data.get('bounds', []),
                        min_zoom=server_data.get('min_zoom', 0),
                        max_zoom=server_data.get('max_zoom', 22),
                        description=server_data.get('description', '')
                    )
                    local_sources[server_data['name']] = local_source
        
        config['server_defs'] = server_defs
        config['local_sources'] = local_sources
        
        # Convert servers list to names only if it contains dicts
        if config['servers'] and isinstance(config['servers'][0], dict):
            config['servers'] = [srv['name'] for srv in config['servers']]
        
        return config
    
    def get_enabled_servers(self, config: Dict[str, Any]) -> List[TileServer]:
        """Get list of enabled servers"""
        enabled_names = config.get('servers', [])
        server_defs = config.get('server_defs', {})
        return [server_defs[name] for name in enabled_names if name in server_defs]
    
    def get_enabled_sources(self, config: Dict[str, Any]) -> List:
        """Get list of enabled sources (both online and local)"""
        enabled_names = config.get('servers', [])
        server_defs = config.get('server_defs', {})
        local_sources = config.get('local_sources', {})
        
        sources = []
        for name in enabled_names:
            if name in server_defs:
                sources.append(server_defs[name])
            elif name in local_sources:
                sources.append(local_sources[name])
        
        return sources
    
    def get_local_sources(self, config: Dict[str, Any]) -> List[LocalSource]:
        """Get list of local sources"""
        local_sources = config.get('local_sources', {})
        return list(local_sources.values())
    
    def get_region(self, config: Dict[str, Any], region_name: str) -> Region:
        """Get region configuration by name"""
        regions = config.get('regions', {})
        if region_name not in regions:
            raise ConfigurationError(f"Region '{region_name}' not found")
        
        region_data = regions[region_name]
        return Region(
            name=region_name,
            bbox=region_data['bbox'],
            min_zoom=region_data.get('min_zoom', 10),
            max_zoom=region_data.get('max_zoom', 12),
            description=region_data.get('description', '')
        ) 

    def get_region_polygon_path(self, config: Dict[str, Any], region_name: str) -> Optional[str]:
        """Optional helper: return polygon_path for region if present in config."""
        try:
            regions = config.get('regions', {})
            if region_name in regions:
                p = regions[region_name].get('polygon_path')
                return p
        except Exception:
            pass
        return None