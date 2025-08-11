import { MapState } from './modules/mapState.js';
import { UIManager } from './modules/uiManager.js';
import { RasterMapLoader } from './modules/rasterMapLoader.js';
import { VectorMapLoader } from './modules/vectorMapLoader.js';
import { ValidationUtils } from './modules/validationUtils.js';
import { CoordinateUtils } from './modules/coordinateUtils.js';

class MapLoader {
    constructor() {
        this.mapState = new MapState();
        this.uiManager = new UIManager();
        this.rasterLoader = new RasterMapLoader(this.mapState, this.uiManager);
        this.vectorLoader = new VectorMapLoader(this.mapState, this.uiManager);
        this.validator = new ValidationUtils();
        this.coordUtils = new CoordinateUtils();
        
        this.loadMap = this.loadMap.bind(this);
        this.cleanupExistingMaps = this.cleanupExistingMaps.bind(this);
    }


    getUserSelections() {
        return this.uiManager.getUserSelections();
    }

    async loadRasterMap(regionName, serverName, center, minZoom, maxZoom, availableZooms = []) {
        return this.rasterLoader.loadMap(regionName, serverName, center, minZoom, maxZoom, availableZooms);
    }

    async loadVectorMap(regionName, serverName, center, minZoom, maxZoom, availableZooms = []) {
        return this.vectorLoader.loadMap(regionName, serverName, center, minZoom, maxZoom, availableZooms);
    }


    

    createLayerControl() {
        this.uiManager.createLayerControl(this.mapState.availableLayers, this.mapState.currentMapType);
    }

    hideLayerControl() {
        this.uiManager.hideLayerControl();
    }

    async cleanupExistingMaps() {
        if (window.map && window.map.remove) {
            window.map.remove();
            window.map = null;
        }
        
        if (window.maplibreMap && window.maplibreMap.remove) {
            window.maplibreMap.remove();
            window.maplibreMap = null;
        }
        
        this.mapState.reset();
        
        const mapContainer = document.getElementById('map');
        if (mapContainer) {
            mapContainer.innerHTML = '';
        }
        
        console.log('[INFO] Existing maps cleaned up');
    }

    updateInfoBox(regionName, serverName, serverType, minZoom, maxZoom) {
        this.uiManager.updateInfoBox(regionName, serverName, serverType, minZoom, maxZoom);
    }

    updateMapInfo() {
        this.uiManager.updateMapInfo(this.mapState.currentMapInstance, this.mapState.currentMapType);
    }

    // addRegionMaskOverlay removed per request

    showError(message) {
        this.uiManager.showError(message);
    }

    
    // Legacy method compatibility - moved to modules
    async getMBTilesZoomRange(serverName) {
        try {
            const response = await fetch('/src/config.json');
            if (!response.ok) return null;
            
            const config = await response.json();
            if (!config.servers) return null;
            
            const serverConfig = config.servers.find(server => 
                server.name === serverName && server.source_type === 'mbtiles'
            );
            
            if (!serverConfig) return null;
            
            const minZoom = serverConfig.min_zoom || 0;
            const maxZoom = serverConfig.max_zoom || 14;
            
            const zoomRange = [];
            for (let z = minZoom; z <= maxZoom && zoomRange.length < 5; z++) {
                zoomRange.push(z);
            }
            
            console.log(`[DEBUG] MBTiles ${serverName} zoom range from config: ${minZoom}-${maxZoom}, using: ${zoomRange}`);
            return zoomRange;
            
        } catch (error) {
            console.warn(`[WARNING] Could not get MBTiles zoom range for ${serverName}:`, error);
            return null;
        }
    }
    
    // Removed detectTileExtension - no longer needed, using metadata directly
    
    // Removed generateTestTileCandidatesForServer - no longer needed
    
    async generateTestTileCandidates(regionName, availableZooms = []) {
        const candidates = [];
        
        // Conditional discovery removed; generate directly from region bounds
        console.log(`[DEBUG] Generating coordinates from region bounds for ${regionName}`);
        
        // Get region data dynamically
        const regionData = await this.coordUtils.getRegionData(regionName);
        let testBounds = null;
        
        if (regionData && regionData.bbox) {
            // Use actual region bounds
            const bbox = regionData.bbox; // [minLng, minLat, maxLng, maxLat]
            testBounds = {
                minLng: bbox[0],
                minLat: bbox[1], 
                maxLng: bbox[2],
                maxLat: bbox[3],
                centerLng: (bbox[0] + bbox[2]) / 2,
                centerLat: (bbox[1] + bbox[3]) / 2
            };
        } else {
            // Try to get dynamic center
            const dynamicCenter = await this.coordUtils.calculateRegionCenter(regionName);
            if (dynamicCenter) {
                testBounds = {
                    centerLng: dynamicCenter[0],
                    centerLat: dynamicCenter[1]
                };
            } else {
                console.log(`[ERROR] Cannot determine center for ${regionName} - no metadata available`);
                return candidates; // Return empty array
            }
        }
        
        // Determine test zoom levels - use only valid available zooms
        const validAvailableZooms = availableZooms.filter(zoom => 
            !isNaN(zoom) && isFinite(zoom) && zoom >= 0 && zoom <= 22
        );
        
        // Only use valid available zooms - no static defaults
        if (validAvailableZooms.length === 0) {
            console.log(`[WARNING] No valid zoom levels available for ${regionName} - cannot generate test candidates`);
            return candidates;
        }
        const testZooms = validAvailableZooms.slice(0, 3).sort((a, b) => a - b);
        
        // Generate multiple test points for each zoom level
        for (const zoom of testZooms) {
            // Validate zoom level before using
            if (isNaN(zoom) || !isFinite(zoom) || zoom < 0 || zoom > 22) {
                console.warn(`[WARNING] Skipping invalid zoom level: ${zoom}`);
                continue;
            }
            // Center point
            const centerTile = this.coordUtils.latLngToTileCoords(testBounds.centerLat, testBounds.centerLng, zoom);
            candidates.push({ zoom, x: centerTile.x, y: centerTile.y, type: 'center' });
            
            // If we have bounds, test additional points within the region
            if (testBounds.minLng !== undefined) {
                // Northwest corner
                const nwTile = this.coordUtils.latLngToTileCoords(testBounds.maxLat, testBounds.minLng, zoom);
                candidates.push({ zoom, x: nwTile.x, y: nwTile.y, type: 'nw' });
                
                // Southeast corner  
                const seTile = this.coordUtils.latLngToTileCoords(testBounds.minLat, testBounds.maxLng, zoom);
                candidates.push({ zoom, x: seTile.x, y: seTile.y, type: 'se' });
                
                // Generate dynamic points based on region bounds
                const tileRangeX = Math.max(1, Math.abs(seTile.x - nwTile.x));
                const tileRangeY = Math.max(1, Math.abs(seTile.y - nwTile.y));
                
                // Sample a few points dynamically within the region bounds
                const samplePoints = Math.min(6, Math.max(tileRangeX, tileRangeY));
                for (let i = 0; i < samplePoints; i++) {
                    const offsetX = Math.floor((tileRangeX / samplePoints) * i) - Math.floor(tileRangeX / 2);
                    const offsetY = Math.floor((tileRangeY / samplePoints) * i) - Math.floor(tileRangeY / 2);
                    
                    candidates.push({
                        zoom,
                        x: Math.max(0, centerTile.x + offsetX),
                        y: Math.max(0, centerTile.y + offsetY),
                        type: 'dynamic_sample'
                    });
                }
            }
        }
        
        console.log(`[DEBUG] Generated ${candidates.length} test tile candidates for ${regionName}`);
        return candidates;
    }
    
    // Removed discoverActualTiles - no longer needed
    
    latLngToTileCoords(lat, lng, zoom) {
        // Clamp latitude to safe Mercator projection range
        const clampedLat = Math.max(-85.05, Math.min(85.05, lat));
        
        // Validate zoom level - no fallback, return null for invalid zoom
        if (isNaN(zoom) || !isFinite(zoom) || zoom < 0 || zoom > 22) {
            console.warn(`[WARNING] Invalid zoom level: ${zoom}`);
            return null;
        }
        
        const n = Math.pow(2, zoom);
        
        // Check if n is Infinity (should not happen with valid zoom)
        if (!isFinite(n)) {
            console.warn(`[WARNING] Math.pow(2, ${zoom}) returned Infinity, using zoom 10`);
            zoom = 10;
            const n = Math.pow(2, zoom);
        }
        
        const x = Math.floor((lng + 180) / 360 * n);
        const latRad = clampedLat * Math.PI / 180;
        const y = Math.floor((1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2 * n);
        
        // Validate final coordinates
        if (!isFinite(x) || !isFinite(y)) {
            console.warn(`[WARNING] Invalid tile coordinates calculated: x=${x}, y=${y} for lat=${lat}, lng=${lng}, zoom=${zoom}`);
            return { x: 0, y: 0 };
        }
        
        return { x, y };
    }
    
    async calculateRegionCenter(regionName) {
        // Try to get center from region metadata first
        const regionData = await this.coordUtils.getRegionData(regionName);
        
        if (regionData && regionData.bbox) {
            const bbox = regionData.bbox;
            const centerLng = (bbox[0] + bbox[2]) / 2;
            const centerLat = (bbox[1] + bbox[3]) / 2;
            
            if (this.validator.isValidCoordinate(centerLng, centerLat)) {
                console.log(`[DEBUG] Calculated dynamic center for ${regionName}: [${centerLng}, ${centerLat}]`);
                return [centerLng, centerLat];
            }
        }
        
        // No valid center could be determined
        console.warn(`[WARNING] Could not determine center for ${regionName} - no valid metadata found`);
        return null;
    }
    
    async calculateTestTileCoordinates(regionName, zoom) {
        // Get region center dynamically
        const center = await this.coordUtils.calculateRegionCenter(regionName);
        
        if (!center) {
            console.warn(`[WARNING] Could not calculate test coordinates for ${regionName} - no center available`);
            return null;
        }
        
        // Convert lat/lng to tile coordinates using the same formula as latLngToTileCoords
        const lat = center[1];
        const lng = center[0];
        
        const tileCoords = this.coordUtils.latLngToTileCoords(lat, lng, zoom);
        
        if (tileCoords) {
            console.log(`[DEBUG] Calculated test tile coordinates for ${regionName} at zoom ${zoom}: x=${tileCoords.x}, y=${tileCoords.y}`);
        }
        return tileCoords;
    }
    
    async testVectorTileAvailability(regionName, serverName, initialZoom, availableZooms = []) {
        console.log(`[INFO] Skipping vector tile availability test - using metadata info for ${regionName}/${serverName}`);
        
        // No need to test - we trust the metadata
        return {
            available: true,
            message: `Vector tiles available based on metadata`,
            testZoom: initialZoom,
            testCoords: null
        };
    }
    
    handleTileError(errorEvent, map, isVector = false) {
        const coords = errorEvent.coords;
        const currentZoom = coords ? coords.z : map.getZoom();
        
        console.warn(`[TILE ERROR] Failed to load tile at z${currentZoom} ${coords ? `/x${coords.x}/y${coords.y}` : ''}`);
        
        // Get current style's available zooms from the last selection
        const serverSelect = document.getElementById('serverSelect');
        let availableZooms = [];
        
        if (serverSelect && serverSelect.selectedIndex > 0) {
            const selectedOption = serverSelect.options[serverSelect.selectedIndex];
            availableZooms = JSON.parse(selectedOption.getAttribute('data-available-zooms') || '[]');
        }
        
        // Find the best available zoom level that's lower than current
        let targetZoom = currentZoom - 1;
        
        if (availableZooms.length > 0) {
            // Find the highest available zoom that's less than current zoom
            const validZooms = availableZooms.filter(zoom => zoom < currentZoom).sort((a, b) => b - a);
            if (validZooms.length > 0) {
                targetZoom = validZooms[0];
            } else {
                // If no lower zoom available, use the lowest available zoom
                targetZoom = Math.min(...availableZooms);
            }
        }
        
        // Only zoom if we have a valid target and it's different from current
        if (targetZoom >= 0 && targetZoom !== currentZoom) {
            console.log(`[INFO] Zooming from ${currentZoom} to ${targetZoom} to find available tiles`);
            
            if (isVector && this.mapState.currentMapType === 'maplibre') {
                map.setZoom(targetZoom);
            } else if (this.mapState.currentMapType === 'leaflet') {
                map.setZoom(targetZoom);
            }
            
            this.updateTileStatus(`Adjusted zoom to level ${targetZoom} to avoid tile errors`);
        } else {
            this.updateTileStatus(`Tile error at zoom ${currentZoom} - no alternative zoom available`);
        }
    }
    
    showInfoBox() {
        this.uiManager.showInfoBox();
    }
    
    updateTileStatus(message) {
        this.uiManager.updateTileStatus(message);
    }
    
    // Update the loadMap method to pass availableZooms
    async loadMap() {
        try {
            await this.cleanupExistingMaps();
            this.hideLayerControl();
            
            const selections = this.getUserSelections();
            if (!selections) {
                return;
            }
            
            const { regionName, serverName, serverType, minZoom, maxZoom, availableZooms } = selections;
            
            // Resolve dynamic center using region + selected server/style
            const center = await this.coordUtils.getEffectiveCenter(regionName, serverName, serverType);
            if (!center || !Array.isArray(center) || center.length !== 2) {
                throw new Error(`Region center not available for ${regionName}`);
            }
            console.log(`[INFO] Using dynamic center for ${regionName}: ${center}`);
            
            if (!this.validator.isValidCoordinate(center[0], center[1])) {
                throw new Error(`Invalid center coordinates for ${regionName}: [${center[0]}, ${center[1]}]`);
            }
            
            if (serverType === 'vector') {
                await this.loadVectorMap(regionName, serverName, center, minZoom, maxZoom, availableZooms);
            } else {
                await this.loadRasterMap(regionName, serverName, center, minZoom, maxZoom, availableZooms);
            }
            
            this.updateInfoBox(regionName, serverName, serverType, minZoom, maxZoom);
            this.updateTileStatus('Map loaded successfully');
            
        } catch (error) {
            console.error('Error loading map:', error);
            this.showError('Failed to load map: ' + error.message);
        }
    }
}

// Global instance
window.mapLoader = new MapLoader();

// Global function for UI to call
window.loadMap = function() {
    if (window.mapLoader) {
        return window.mapLoader.loadMap();
    } else {
        console.error('MapLoader not initialized');
    }
};

// Layer toggle function for UI
window.toggleLayer = function(layerId, visible) {
    if (window.mapLoader && window.mapLoader.mapState.currentMapInstance) {
        const map = window.mapLoader.mapState.currentMapInstance;
        
        if (window.mapLoader.mapState.currentMapType === 'maplibre') {
            const setVis = (id, vis) => {
                try {
                    if (map.getLayer(id)) {
                        map.setLayoutProperty(id, 'visibility', vis);
                    }
                } catch (e) {
                    console.warn('[WARNING] Failed to set visibility for layer', id, e);
                }
            };
            setVis(layerId, visible ? 'visible' : 'none');
            setVis(`${layerId}-outline`, visible ? 'visible' : 'none');
        }
        
        const layer = window.mapLoader.mapState.availableLayers.find(l => l.id === layerId);
        if (layer) {
            layer.visible = visible;
        }
    }
};
