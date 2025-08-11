from typing import Dict, Any, Optional, List
from interfaces.tile_source import ITileSource
from adapters.mbtiles_adapter import MBTilesAdapter
from models.tile_server import TileServer
from models.local_source import LocalSource


class SourceFactory:
    """Factory for creating tile sources"""
    
    @staticmethod
    def create_source(source_config: Dict[str, Any]) -> Optional[ITileSource]:
        """Create a tile source from configuration"""
        try:
            source_type = source_config.get('type', 'http')
            
            if source_type == 'http':
                return SourceFactory._create_http_source(source_config)
            elif source_type == 'local':
                return SourceFactory._create_local_source(source_config)
            else:
                print(f"Unknown source type: {source_type}")
                return None
                
        except Exception as e:
            print(f"Failed to create source: {e}")
            return None
    
    @staticmethod
    def _create_http_source(config: Dict[str, Any]) -> Optional[TileServer]:
        """Create HTTP tile server"""
        try:
            return TileServer(
                name=config['name'],
                url=config['url'],
                headers=config.get('headers', {}),
                tile_type=config.get('tile_type', 'raster')
            )
        except Exception as e:
            print(f"Failed to create HTTP source: {e}")
            return None
    
    @staticmethod
    def _create_local_source(config: Dict[str, Any]) -> Optional[MBTilesAdapter]:
        """Create local tile source"""
        try:
            adapter = MBTilesAdapter(config)
            if adapter.initialize():
                return adapter
            else:
                print(f"Failed to initialize local source: {config.get('name', 'unknown')}")
                return None
        except Exception as e:
            print(f"Failed to create local source: {e}")
            return None
    
    @staticmethod
    def create_sources_from_config(config: Dict[str, Any]) -> List[ITileSource]:
        """Create all sources from configuration"""
        sources = []
        
        # Get enabled source names
        enabled_names = config.get('servers', [])
        
        # Process each source
        for source_name in enabled_names:
            source_config = SourceFactory._find_source_config(config, source_name)
            if source_config:
                source = SourceFactory.create_source(source_config)
                if source:
                    sources.append(source)
            else:
                print(f"Source configuration not found: {source_name}")
        
        return sources
    
    @staticmethod
    def _find_source_config(config: Dict[str, Any], source_name: str) -> Optional[Dict[str, Any]]:
        """Find source configuration by name"""
        # Check in servers list
        servers = config.get('servers', [])
        for server in servers:
            if isinstance(server, dict) and server.get('name') == source_name:
                return server
        
        return None
