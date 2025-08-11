export class RasterMapLoader {
    constructor(mapState, uiManager) {
        this.mapState = mapState;
        this.uiManager = uiManager;
    }

    async loadMap(regionName, serverName, center, minZoom, maxZoom, availableZooms = []) {
        try {
            console.log(`[INFO] Loading raster map: ${regionName}/${serverName} with dynamic zoom range ${minZoom}-${maxZoom}`);
            console.log(`[INFO] Available zoom levels: [${availableZooms.join(', ')}]`);
            
            const { regionBounds, regionCenter } = await this.prepareMapData(regionName, center);
            this.validateMapContainer();
            this.cleanupExistingMap();

            const initialZoom = this.getValidZoomLevel(minZoom, minZoom, maxZoom, availableZooms);
            const map = this.createLeafletMap(regionCenter, initialZoom, minZoom, maxZoom, regionBounds);
            
            this.mapState.setMapInstance(map, 'leaflet');
            window.map = map;
            window.currentMap = map;
            this.attachMapEvents(map);
            
            console.log(`[SUCCESS] Leaflet map created with zoom constraints: min=${map.getMinZoom()}, max=${map.getMaxZoom()}, current=${map.getZoom()}`);
            
            const tileLayer = this.createTileLayer(regionName, serverName, minZoom, maxZoom, regionBounds, availableZooms);
            this.setupTileLayerEvents(tileLayer, map);
            tileLayer.addTo(map);
            
            this.fitMapBounds(map, regionBounds, minZoom, maxZoom);
            this.addMapControls(map);
            // Region mask overlay removed per request (masking disabled during web render)
            this.updateUI();
            
            console.log(`[SUCCESS] Raster map loaded: ${regionName}/${serverName} (zoom: ${minZoom}-${maxZoom})`);
            
        } catch (error) {
            console.error('[ERROR] Failed to load raster map:', error);
            this.uiManager.showError(`Failed to load raster map: ${error.message}`);
        }
    }

    async prepareMapData(regionName, center) {
        const regionData = await this.getRegionData(regionName);
        const regionBounds = regionData ? regionData.bounds : null;
        const regionCenter = regionData && regionData.center ? regionData.center : center;
        
        if (!this.isValidCoordinate(regionCenter[0], regionCenter[1])) {
            throw new Error(`Invalid center coordinates: [${regionCenter[0]}, ${regionCenter[1]}]`);
        }
        
        return { regionBounds, regionCenter };
    }

    validateMapContainer() {
        const mapContainer = document.getElementById('map');
        if (!mapContainer) {
            throw new Error('Map container element (#map) not found in DOM');
        }
    }

    cleanupExistingMap() {
        if (this.mapState.currentMapInstance) {
            try {
                this.mapState.currentMapInstance.remove();
            } catch (e) {
                console.warn('Error removing existing map instance:', e);
            }
        }
    }

    createLeafletMap(regionCenter, initialZoom, minZoom, maxZoom, regionBounds) {
        return L.map('map', {
            center: regionCenter,
            zoom: initialZoom,
            minZoom: minZoom,
            maxZoom: maxZoom,
            maxBounds: regionBounds,
            maxBoundsViscosity: 1.0,
            attributionControl: false,
            zoomControl: false
        });
    }

    createTileLayer(regionName, serverName, minZoom, maxZoom, regionBounds, availableZooms) {
        const tileExtension = 'png';
        // Encode path segments to safely handle spaces/diacritics
        const regionSeg = encodeURIComponent(regionName);
        const serverSeg = encodeURIComponent(serverName);
        
        // Always serve from filesystem tiles under map_tiles directory
        const tilePath = `/map_tiles/${regionSeg}/raster/${serverSeg}/{z}/{x}/{y}.${tileExtension}`;
        
        const self = this;
        return L.tileLayer(tilePath, {
            attribution: `${serverName} - ${regionName}`,
            minZoom: minZoom,
            maxZoom: maxZoom,
            noWrap: true,
            bounds: regionBounds,
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==',
            detectRetina: false
        });
    }

    setupTileLayerEvents(tileLayer, map) {
        tileLayer.on('loading', () => {
            console.log('[INFO] Tiles loading started');
        });
        
        tileLayer.on('load', () => {
            console.log('[INFO] All tiles loaded successfully');
        });
        
        tileLayer.on('tileerror', (e) => {
            console.warn('[WARNING] Tile load error:', e.coords, e.error);
            this.handleTileError(e, map);
        });
        
        this.mapState.setTileLayer(tileLayer);
    }

    fitMapBounds(map, regionBounds, minZoom, maxZoom) {
        if (regionBounds && regionBounds.length === 2) {
            map.fitBounds(regionBounds, { 
                padding: [50, 50],
                maxZoom: Math.max(minZoom, maxZoom - 1)
            });
        }
    }

    addMapControls(map) {
        // Scale: metric only with optimized width
        L.control.scale({
            position: 'bottomleft',
            imperial: false,
            metric: true,
            maxWidth: 120
        }).addTo(map);
        // Move zoom control to bottom-right to avoid colliding with panel
        L.control.zoom({ position: 'bottomright' }).addTo(map);
    }

    attachMapEvents(map) {
        const updateInfo = () => {
            try {
                this.uiManager.updateMapInfo(this.mapState.currentMapInstance, this.mapState.currentMapType);
            } catch (e) {
                // no-op
            }
        };
        map.on('load', updateInfo);
        map.on('zoomend', updateInfo);
        map.on('moveend', updateInfo);
    }

    updateUI() {
        this.uiManager.showInfoBox();
        this.uiManager.updateMapInfo(this.mapState.currentMapInstance, this.mapState.currentMapType);
    }

    // Utility methods that need to be accessible from tile layer
    isValidCoordinate(lng, lat) {
        return !isNaN(lng) && !isNaN(lat) && 
               isFinite(lng) && isFinite(lat) &&
               lng >= -180 && lng <= 180 &&
               lat >= -85.05 && lat <= 85.05;
    }

    isValidTileCoordinate(coords, regionBounds, regionName) {
        const z = coords.z;
        const x = coords.x;
        const y = coords.y;
        
        if (isNaN(x) || isNaN(y) || isNaN(z) || x < 0 || y < 0 || z < 0) {
            return false;
        }
        
        if (!regionBounds || regionBounds.length !== 2) {
            return true;
        }
        
        const bbox = [
            regionBounds[0][1],
            regionBounds[0][0], 
            regionBounds[1][1],
            regionBounds[1][0]
        ];
        
        const n = Math.pow(2, z);
        if (!isFinite(n)) {
            return false;
        }
        
        const minX = Math.floor((bbox[0] + 180) / 360 * n);
        const maxX = Math.floor((bbox[2] + 180) / 360 * n);
        
        const minLatRad = Math.max(-85.05, bbox[1]) * Math.PI / 180;
        const maxLatRad = Math.min(85.05, bbox[3]) * Math.PI / 180;
        const minY = Math.floor((1 - Math.asinh(Math.tan(maxLatRad)) / Math.PI) / 2 * n);
        const maxY = Math.floor((1 - Math.asinh(Math.tan(minLatRad)) / Math.PI) / 2 * n);
        
        const isValid = x >= minX && x <= maxX && y >= minY && y <= maxY;
        
        if (!isValid) {
            console.log(`[DEBUG] Tile z${z}/x${x}/y${y} outside valid range: x[${minX}-${maxX}], y[${minY}-${maxY}] for ${regionName}`);
        }
        
        return isValid;
    }

    getValidZoomLevel(preferredZoom, minZoom, maxZoom, availableZooms = []) {
        const validAvailableZooms = availableZooms.filter(zoom => 
            !isNaN(zoom) && isFinite(zoom) && zoom >= 0 && zoom <= 22
        );
        
        if (validAvailableZooms.length > 0) {
            const minAvailableZoom = Math.min(...validAvailableZooms);
            return Math.max(minZoom, Math.min(maxZoom, minAvailableZoom));
        }
        
        return Math.max(minZoom, Math.min(maxZoom, minZoom));
    }

    async getRegionData(regionName) {
        try {
            console.log(`[INFO] Getting region data for: ${regionName}`);
            const response = await fetch(`/region_map_styles/${regionName}`);
            if (response.ok) {
                const data = await response.json();
                if (data.region_info && data.region_info.bbox) {
                    const bbox = data.region_info.bbox;
                    const center = data.region_info.center;
                    
                    if (bbox.some(val => isNaN(val) || !isFinite(val))) {
                        console.warn(`[WARNING] Invalid bbox values: ${bbox}`);
                        return null;
                    }
                    
                    const bounds = [
                        [bbox[1], bbox[0]],
                        [bbox[3], bbox[2]]
                    ];
                    
                    console.log(`[SUCCESS] Got region data: bbox=${bbox}, center=${center}`);
                    
                    return {
                        bounds: bounds,
                        center: center ? [center[0], center[1]] : null,
                        bbox: bbox,
                        styles: {
                            raster: data.raster || {},
                            vector: data.vector || {}
                        }
                    };
                }
            }
            
            console.warn(`[WARNING] No region data found for ${regionName}, using fallback`);
            return null;
            
        } catch (error) {
            console.error('[ERROR] Could not get region data:', error);
            return null;
        }
    }

    handleTileError(errorEvent, map) {
        const coords = errorEvent.coords;
        const currentZoom = coords ? coords.z : map.getZoom();
        
        console.warn(`[TILE ERROR] Failed to load tile at z${currentZoom} ${coords ? `/x${coords.x}/y${coords.y}` : ''}`);
        
        const serverSelect = document.getElementById('serverSelect');
        let availableZooms = [];
        
        if (serverSelect && serverSelect.selectedIndex > 0) {
            const selectedOption = serverSelect.options[serverSelect.selectedIndex];
            availableZooms = JSON.parse(selectedOption.getAttribute('data-available-zooms') || '[]');
        }
        
        let targetZoom = currentZoom - 1;
        
        if (availableZooms.length > 0) {
            const validZooms = availableZooms.filter(zoom => zoom < currentZoom).sort((a, b) => b - a);
            if (validZooms.length > 0) {
                targetZoom = validZooms[0];
            } else {
                targetZoom = Math.min(...availableZooms);
            }
        }
        
        if (targetZoom >= 0 && targetZoom !== currentZoom) {
            console.log(`[INFO] Zooming from ${currentZoom} to ${targetZoom} to find available tiles`);
            map.setZoom(targetZoom);
            this.uiManager.updateTileStatus(`Adjusted zoom to level ${targetZoom} to avoid tile errors`);
        } else {
            this.uiManager.updateTileStatus(`Tile error at zoom ${currentZoom} - no alternative zoom available`);
        }
    }
}