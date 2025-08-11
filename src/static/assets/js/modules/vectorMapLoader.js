import { getStyleDefaults } from './config.js';

export class VectorMapLoader {
    constructor(mapState, uiManager) {
        this.mapState = mapState;
        this.uiManager = uiManager;
    }

    async loadMap(regionName, serverName, center, minZoom, maxZoom, availableZooms = []) {
        try {
            console.log(`[INFO] Loading vector map: ${regionName}/${serverName} with dynamic zoom range ${minZoom}-${maxZoom}`);
            console.log(`[INFO] Available zoom levels: [${availableZooms.join(', ')}]`);
            
            const { regionBounds, regionCenter } = await this.prepareMapData(regionName, center);
            this.validateMapContainer();
            this.cleanupExistingMap();

            const initialZoom = this.getValidZoomLevel(minZoom, minZoom, maxZoom, availableZooms);
            const tileUrl = this.createTileUrl(regionName, serverName);
            
            const map = this.createMapLibreMap(regionCenter, initialZoom, minZoom, maxZoom, regionBounds, tileUrl, serverName, regionName);
            
            this.mapState.setMapInstance(map, 'maplibre');
            window.maplibreMap = map;
            window.currentMap = map;
            
            console.log(`[SUCCESS] MapLibre map created with zoom constraints: min=${map.getMinZoom()}, max=${map.getMaxZoom()}, current=${map.getZoom()}`);
            
            await this.waitForMapLoad(map);
            await this.setupDynamicLayers(map, serverName);
            this.addMapControls(map);
            this.updateUI();
            
            console.log(`[SUCCESS] Vector map setup complete: ${regionName}/${serverName}`);
            
        } catch (error) {
            console.error('[ERROR] Failed to load vector map:', error);
            this.uiManager.showError(`Failed to load vector map: ${error.message}`);
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
                if (this.mapState.currentMapInstance.remove) {
                    this.mapState.currentMapInstance.remove();
                } else if (this.mapState.currentMapInstance._container) {
                    this.mapState.currentMapInstance._container.remove();
                }
            } catch (e) {
                console.warn('Error removing existing map instance:', e);
            }
        }
    }

    createTileUrl(regionName, serverName) {
        const protocol = window.location.protocol;
        const host = window.location.host;
        const cacheBuster = `v=${Date.now()}`;
        const regionSeg = encodeURIComponent(regionName);
        const serverSeg = encodeURIComponent(serverName);
        
        // Always serve from filesystem tiles under map_tiles directory
        return `${protocol}//${host}/map_tiles/${regionSeg}/vector/${serverSeg}/{z}/{x}/{y}.pbf?${cacheBuster}`;
    }

    createMapLibreMap(regionCenter, initialZoom, minZoom, maxZoom, regionBounds, tileUrl, serverName, regionName) {
        const style = this.createVectorStyle(tileUrl, minZoom, maxZoom, regionBounds, serverName, regionName);
        
        return new maplibregl.Map({
            container: 'map',
            style: style,
            center: regionCenter,
            zoom: initialZoom,
            minZoom: minZoom,
            maxZoom: maxZoom,
            maxBounds: regionBounds ? [regionBounds[0][1], regionBounds[0][0], regionBounds[1][1], regionBounds[1][0]] : undefined,
            attributionControl: false
        });
    }

    createVectorStyle(tileUrl, minZoom, maxZoom, regionBounds, serverName, regionName) {
        const defaults = getStyleDefaults();
        return {
            version: 8,
            sources: {
                'openmaptiles': {
                    type: 'vector',
                    tiles: [tileUrl],
                    tileSize: defaults.tileSize,
                    scheme: 'xyz',
                    minzoom: minZoom,
                    maxzoom: maxZoom,
                    bounds: regionBounds ? [regionBounds[0][1], regionBounds[0][0], regionBounds[1][1], regionBounds[1][0]] : undefined,
                    attribution: `${serverName} - ${regionName}`
                }
            },
            layers: this.createBasicLayers()
        };
    }

    createBasicLayers() {
        const defaults = getStyleDefaults();
        return [
            {
                id: 'background',
                type: 'background',
                paint: {
                    'background-color': defaults.backgroundColor
                }
            },
            ...defaults.baseVectorLayers.map((l) => {
                if (l.type === 'line') {
                    return {
                        id: `${l.name}-line`,
                        type: 'line',
                        source: 'openmaptiles',
                        'source-layer': l.name,
                        paint: {
                            'line-color': l.color,
                            'line-width': l.lineWidth || 1
                        }
                    };
                }
                return {
                    id: `${l.name}-fill`,
                    type: 'fill',
                    source: 'openmaptiles',
                    'source-layer': l.name,
                    paint: {
                        'fill-color': l.color,
                        ...(l.outlineColor ? { 'fill-outline-color': l.outlineColor } : {})
                    }
                };
            })
        ];
    }

    async waitForMapLoad(map) {
        return new Promise((resolve) => {
            const timeout = setTimeout(() => {
                console.log('[INFO] Load timeout reached - proceeding');
                resolve();
            }, 10000);
            
            map.on('load', () => {
                clearTimeout(timeout);
                console.log('[SUCCESS] Vector map loaded');
                try {
                    // Move zoom control to bottom-right (avoid overlap)
                    const nav = new maplibregl.NavigationControl({ showCompass: false });
                    // Remove existing controls first to clean up
                    const controls = document.querySelectorAll('.maplibregl-ctrl-top-left .maplibregl-ctrl');
                    controls.forEach(el => el.parentNode && el.parentNode.removeChild(el));
                    map.addControl(nav, 'bottom-right');
                } catch (e) {
                    console.warn('[WARNING] Could not reposition MapLibre controls', e);
                }
                this.attachMapEvents(map);
                resolve();
            });
            
            map.on('error', (e) => {
                const err = e && e.error ? e.error : e;
                const message = err && err.message ? err.message : String(err);
                console.error('[ERROR] Vector map error:', message, {
                    sourceId: e && e.sourceId,
                    sourceDataType: e && e.sourceDataType,
                    tile: e && e.tile,
                });
            });
        });
    }

    async setupDynamicLayers(map, serverName) {
        this.logMapInfo(map);
        this.checkVectorSource(map);

        // After style loads, record all existing layers
        this.registerAllStyleLayers(map);

        // If local MBTiles, add MBTiles layers and refresh the list
        if (serverName.startsWith('Local_')) {
            await this.addMBTilesLayers(map, serverName);
            // Re-scan after MBTiles are added
            this.registerAllStyleLayers(map);
        }

        // Apply default GIS order and store the initial order (Reset Order)
        try {
            const ordered = this.applySemanticDefaultOrder(map);
            this.mapState.originalLayerOrder = ordered;
        } catch {}

        // Create/update the panel
        this.uiManager.createLayerControl(this.mapState.availableLayers, this.mapState.currentMapType);
    }

    registerAllStyleLayers(map) {
        try {
            const style = map.getStyle();
            const layers = Array.isArray(style?.layers) ? style.layers : [];
            layers.forEach((layer) => {
                if (!layer || !layer.id) return;
                if (layer.type === 'background') return; // skip background
                if (!map.getLayer(layer.id)) return;
                const vis = map.getLayoutProperty(layer.id, 'visibility');
                const visible = vis !== 'none';
                if (!this.mapState.availableLayers.find(x => x.id === layer.id)) {
                    this.mapState.addLayer({ id: layer.id, name: layer.id, type: layer.type || 'vector', visible });
                }
            });
        } catch (e) {
            console.warn('[WARNING] Failed to register style layers', e);
        }
    }

    // --- Semantic default ordering for GIS layers ---
    applySemanticDefaultOrder(map) {
        const style = map.getStyle();
        const layers = (style?.layers || [])
            .map(l => l.id)
            .filter(id => id && id !== 'background' && map.getLayer(id));

        const priorityOf = (id) => {
            const lid = String(id).toLowerCase();
            // Lower number at bottom (drawn first), higher on top
            if (lid.includes('water')) return 10;
            if (lid.includes('landcover')) return 15;
            if (lid.includes('landuse')) return 20;
            if (lid.includes('park') || lid.includes('forest') || lid.includes('green')) return 22;
            if (lid.endsWith('-fill') && lid.includes('building')) return 30;
            if (lid.includes('building') && (lid.includes('line') || lid.includes('outline'))) return 31;
            if (lid.includes('road') || lid.includes('transport') || lid.includes('highway') || lid.includes('street')) return 40;
            if (lid.includes('bridge')) return 41;
            if (lid.includes('tunnel')) return 39;
            if (lid.includes('boundary')) return 45;
            if (lid.includes('label') || lid.includes('symbol') || lid.includes('name')) return 50;
            // Dynamic/other layers mid-level
            return 35;
        };

        const ordered = layers
            .slice()
            .sort((a, b) => priorityOf(a) - priorityOf(b)); // küçükten büyüğe: alttan üste

        // Apply ordering stably using moveLayer(beforeId)
        for (let i = 0; i < ordered.length; i++) {
            const id = ordered[i];
            const beforeId = ordered[i + 1]; // place under the next layer
            try {
                if (beforeId && map.getLayer(beforeId)) {
                    map.moveLayer(id, beforeId);
                } else {
                    // If no beforeId, move to top
                    map.moveLayer(id);
                }
            } catch (_) {}
            // Move paired outline layer together if exists
            const outlineId = id.endsWith('-fill') ? `${id.replace(/-fill$/, '')}-outline` : `${id}-outline`;
            if (map.getLayer(outlineId)) {
                try {
                    const outlineBefore = ordered[i + 1] || undefined;
                    if (outlineBefore && map.getLayer(outlineBefore)) map.moveLayer(outlineId, outlineBefore);
                    else map.moveLayer(outlineId);
                } catch (_) {}
            }
        }
        return ordered;
    }

    attachMapEvents(map) {
        const updateInfo = () => {
            try {
                this.uiManager.updateMapInfo(this.mapState.currentMapInstance, this.mapState.currentMapType);
            } catch (e) {
                // no-op
            }
        };
        map.on('zoomend', updateInfo);
        map.on('moveend', updateInfo);
    }

    logMapInfo(map) {
        const style = map.getStyle();
        console.log('[DEBUG] Map style sources:', Object.keys(style.sources || {}));
        console.log('[DEBUG] Map style layers:', (style.layers || []).map(l => l.id));
    }

    checkVectorSource(map) {
        setTimeout(() => {
            const source = map.getSource('openmaptiles');
            console.log('[DEBUG] Vector source loaded:', !!source);
            
            if (source && source.loaded && source.loaded()) {
                console.log('[SUCCESS] Vector source reports as loaded');
            } else {
                console.log('[WARNING] Vector source not reporting as loaded');
            }
        }, 2000);
    }

    async addMBTilesLayers(map, serverName) {
        try {
            const resp = await fetch(`/inspect_mbtiles?server=${encodeURIComponent(serverName)}`);
            if (resp.ok) {
                const info = await resp.json();
                const layerNames = Array.isArray(info.layers) ? info.layers : [];
                console.log(`[INFO] MBTiles layer names detected (${layerNames.length}):`, layerNames);
                
                let added = 0;
                layerNames.forEach((layerName, idx) => {
                    try {
                        if (!map.getLayer(`${layerName}-fill`)) {
                            map.addLayer({
                                id: `${layerName}-fill`,
                                type: 'fill',
                                source: 'openmaptiles',
                                'source-layer': layerName,
                                paint: {
                                    'fill-color': this.mapState.getLayerColor(idx),
                                    'fill-opacity': 0.5
                                }
                            });
                            this.mapState.addLayer({ id: `${layerName}-fill`, name: `${layerName} (fill)`, type: 'vector', visible: true });
                            added++;
                        }
                        if (!map.getLayer(`${layerName}-outline`)) {
                            map.addLayer({
                                id: `${layerName}-outline`,
                                type: 'line',
                                source: 'openmaptiles',
                                'source-layer': layerName,
                                paint: {
                                    'line-color': this.mapState.getLayerColor(idx),
                                    'line-width': 1,
                                    'line-opacity': 0.7
                                }
                            });
                            // Outline varsayılan olarak fill ile aynı görünürlükte
                            if (map.getLayer(`${layerName}-fill`)) {
                                const isVisible = map.getLayoutProperty(`${layerName}-fill`, 'visibility') !== 'none';
                                map.setLayoutProperty(`${layerName}-outline`, 'visibility', isVisible ? 'visible' : 'none');
                            }
                        }
                    } catch (e) {
                        console.warn(`[WARNING] Failed adding dynamic layer for '${layerName}':`, e);
                    }
                });
                
                if (added > 0) {
                    console.log(`[SUCCESS] Added ${added} dynamic vector layers from MBTiles metadata`);
                    this.uiManager.createLayerControl(this.mapState.availableLayers, this.mapState.currentMapType);
                } else {
                    console.log('[INFO] No dynamic layers added (may already exist or no layers detected)');
                }
            } else {
                console.log('[WARNING] Failed to inspect MBTiles layers');
            }
        } catch (e) {
            console.log('[WARNING] MBTiles inspection failed:', e);
        }
    }

    addMapControls(map) {
        const defaults = getStyleDefaults();
        // Ölçek kontrolünü sol alta yerleştir, sadece metrik
        const scale = new maplibregl.ScaleControl({
            maxWidth: defaults.scaleControl?.maxWidth || 120,
            unit: 'metric'
        });
        map.addControl(scale, 'bottom-left');
    }

    updateUI() {
        this.uiManager.showInfoBox();
        this.uiManager.updateMapInfo(this.mapState.currentMapInstance, this.mapState.currentMapType);
    }

    // Utility methods
    isValidCoordinate(lng, lat) {
        return !isNaN(lng) && !isNaN(lat) && 
               isFinite(lng) && isFinite(lat) &&
               lng >= -180 && lng <= 180 &&
               lat >= -85.05 && lat <= 85.05;
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
}