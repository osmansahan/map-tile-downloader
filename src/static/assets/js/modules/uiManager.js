export class UIManager {
    constructor() {
        this.serverTypes = window.serverTypes || {};
    }

    getUserSelections() {
        const regionSelect = document.getElementById('regionSelect');
        const serverSelect = document.getElementById('serverSelect');
        
        if (!regionSelect || !serverSelect) {
            this.showError('UI elements not found. Please refresh the page.');
            return null;
        }
        
        const regionName = regionSelect.value;
        const serverName = serverSelect.value;
        
        if (!regionName) {
            this.showError('Please select a region first!');
            return null;
        }
        
        if (!serverName) {
            this.showError('Please select a map style!');
            return null;
        }
        
        const selectedOption = serverSelect.options[serverSelect.selectedIndex];
        const minZoom = parseInt(selectedOption?.getAttribute('data-min-zoom')) || 0;
        const maxZoom = parseInt(selectedOption?.getAttribute('data-max-zoom')) || 18;
        const tileCount = parseInt(selectedOption?.getAttribute('data-tile-count')) || 0;
        
        console.log(`[INFO] Dynamic zoom range for ${regionName}/${serverName}: ${minZoom}-${maxZoom}`);
        
        let availableZooms = [];
        try {
            const rawAvailableZooms = JSON.parse(selectedOption?.getAttribute('data-available-zooms') || '[]');
            availableZooms = rawAvailableZooms.filter(zoom => 
                !isNaN(zoom) && isFinite(zoom) && zoom >= 0 && zoom <= 22
            );
        } catch (error) {
            console.warn('[WARNING] Failed to parse available zooms:', error);
            availableZooms = [];
        }
        
        const serverType = selectedOption?.dataset.type || this.serverTypes[serverName] || 'raster';
        
        if (tileCount === 0 && availableZooms.length === 0) {
            console.warn(`[WARNING] No tiles available for ${regionName}/${serverName}`);
        }
        
        return { 
            regionName, 
            serverName, 
            serverType, 
            minZoom, 
            maxZoom, 
            tileCount,
            availableZooms
        };
    }

    showError(message) {
        console.error('[ERROR]', message);
        
        const mapContainer = document.getElementById('map');
        if (mapContainer) {
            mapContainer.innerHTML = `
                <div class="map-message">
                    <h3>Error</h3>
                    <p>${message}</p>
                </div>
            `;
        }
    }

    showInfoBox() {
        const infoBox = document.getElementById('infoBox');
        if (infoBox) {
            infoBox.style.display = 'block';
            infoBox.setAttribute('data-has-content', '1');
        }
    }

    hideLayerControl() {
        const layerControl = document.getElementById('layerControl');
        if (layerControl) {
            layerControl.style.display = 'none';
        }
    }

    updateInfoBox(regionName, serverName, serverType, minZoom, maxZoom) {
        const currentRegion = document.getElementById('currentRegion');
        const currentServer = document.getElementById('currentServer');
        const currentServerType = document.getElementById('currentServerType');
        const maxZoomSpan = document.getElementById('maxZoom');
        
        if (currentRegion) currentRegion.textContent = regionName;
        if (currentServer) currentServer.textContent = serverName;
        if (currentServerType) currentServerType.textContent = serverType;
        if (maxZoomSpan) maxZoomSpan.textContent = maxZoom;
    }

    updateMapInfo(mapInstance, mapType) {
        if (!mapInstance) return;
        const currentZoom = document.getElementById('currentZoom');
        const maxZoomSpan = document.getElementById('maxZoom');
        if (currentZoom) {
            let z = 0;
            if (mapType === 'leaflet') {
                z = mapInstance.getZoom();
            } else if (mapType === 'maplibre') {
                z = mapInstance.getZoom();
            }
            // Clearer display: integer, 0.5 steps if needed
            const zFixed = Number.isInteger(z) ? z : Math.round(z * 2) / 2;
            currentZoom.textContent = zFixed;
        }
        // maxZoom already set by updateInfoBox; optionally refresh here
        if (maxZoomSpan && typeof mapInstance.getMaxZoom === 'function') {
            maxZoomSpan.textContent = mapInstance.getMaxZoom();
        }
    }

    updateTileStatus(message) {
        const tileStatus = document.getElementById('tileStatus');
        if (tileStatus) {
            tileStatus.textContent = message;
            tileStatus.style.color = message.includes('error') ? '#dc3545' : '#28a745';
        }
    }

    createLayerControl(availableLayers, currentMapType) {
        const layerList = document.getElementById('layerList');
        const layerControl = document.getElementById('layerControl');
        
        if (!layerList || !layerControl) {
            console.warn('[WARNING] Layer control elements not found');
            return;
        }
        
        // Hide layer control for raster maps
        if (currentMapType !== 'maplibre') {
            layerControl.style.display = 'none';
            return;
        }

        layerList.innerHTML = '';
        if (availableLayers.length === 0) {
            layerList.innerHTML = '<div class="no-layers">No layers available</div>';
            layerControl.style.display = 'block';
            return;
        }
        
        console.log(`[INFO] Creating layer control for ${availableLayers.length} layers`);
        
        availableLayers.forEach(layer => {
            const layerItem = document.createElement('div');
            layerItem.className = 'layer-item';
            layerItem.setAttribute('data-layer-id', layer.id);
            layerItem.setAttribute('draggable', 'true');

            const topRow = document.createElement('div');
            topRow.className = 'layer-top-row';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `layer-${layer.id}`;
            checkbox.checked = !!layer.visible;
            checkbox.addEventListener('change', () => {
                try {
                    if (window.mapLoader && window.mapLoader.mapState.currentMapType === 'maplibre') {
                        const map = window.mapLoader.mapState.currentMapInstance;
                        const setVis = (id, vis) => {
                            if (map.getLayer(id)) {
                                map.setLayoutProperty(id, 'visibility', vis ? 'visible' : 'none');
                            }
                        };
                        setVis(layer.id, checkbox.checked);
                        const outlineId = layer.id.endsWith('-fill') ? `${layer.id.replace(/-fill$/, '')}-outline` : `${layer.id}-outline`;
                        if (map.getLayer(outlineId)) setVis(outlineId, checkbox.checked);
                    }
                    const l = window.mapLoader?.mapState.availableLayers.find(l => l.id === layer.id);
                    if (l) l.visible = checkbox.checked;
                } catch (e) {
                    console.warn('[WARNING] Failed to toggle layer', layer.id, e);
                }
            });

            const label = document.createElement('label');
            label.htmlFor = `layer-${layer.id}`;
            label.textContent = layer.name;

            // Color picker (for vector line/fill)
            const colorWrap = document.createElement('div');
            colorWrap.className = 'layer-color';
            const colorInput = document.createElement('input');
            colorInput.type = 'color';
            // Read default color from map style and assign to input (show actual color)
            try {
                if (window.mapLoader?.mapState?.currentMapType === 'maplibre') {
                    const map = window.mapLoader.mapState.currentMapInstance;
                    const [propName, currentColor] = this._readLayerColor(map, layer.id);
                    const resolved = this._resolveStyleColor(currentColor, map);
                    const hex = this._normalizeColorToHex(resolved) || '#33a3ff';
                    colorInput.value = hex;
                    colorWrap.style.backgroundColor = hex;
                    // On first display, store original color
                    if (!window.mapLoader.mapState.layerOriginalColors[layer.id]) {
                        window.mapLoader.mapState.layerOriginalColors[layer.id] = { property: propName, value: resolved ?? currentColor, hex };
                    }
                } else {
                    colorInput.value = '#33a3ff';
                    colorWrap.style.backgroundColor = '#33a3ff';
                }
            } catch (_) { colorInput.value = '#33a3ff'; colorWrap.style.backgroundColor = '#33a3ff'; }
            colorInput.title = 'Change layer color';
            colorWrap.appendChild(colorInput);
            colorInput.addEventListener('input', () => {
                try {
                    if (window.mapLoader?.mapState?.currentMapType !== 'maplibre') return;
                    const map = window.mapLoader.mapState.currentMapInstance;
                    const id = layer.id;
                    const color = colorInput.value;
                    const [propName] = this._readLayerColor(map, id);
                    if (propName && map.getLayer(id)) {
                        map.setPaintProperty(id, propName, color);
                    }
                    colorWrap.style.backgroundColor = color;
                } catch (e) {
                    console.warn('[WARNING] Failed to change layer color', e);
                }
            });

            const rightSide = document.createElement('div');
            rightSide.className = 'layer-actions';
            const btnUp = document.createElement('button');
            btnUp.type = 'button';
            btnUp.className = 'layer-act-btn';
            btnUp.title = 'Move up';
            btnUp.textContent = '↑';
            const btnDown = document.createElement('button');
            btnDown.type = 'button';
            btnDown.className = 'layer-act-btn';
            btnDown.title = 'Move down';
            btnDown.textContent = '↓';
            rightSide.appendChild(btnUp);
            rightSide.appendChild(btnDown);

            btnUp.addEventListener('click', () => {
                const prev = layerItem.previousElementSibling;
                if (prev && prev.classList.contains('layer-item')) {
                    layerList.insertBefore(layerItem, prev);
                    this._applyDomOrderToMap(layerList);
                }
            });
            btnDown.addEventListener('click', () => {
                const next = layerItem.nextElementSibling;
                if (next && next.classList.contains('layer-item')) {
                    layerList.insertBefore(next, layerItem);
                    this._applyDomOrderToMap(layerList);
                }
            });

            topRow.appendChild(checkbox);
            topRow.appendChild(label);
            topRow.appendChild(colorWrap);
            topRow.appendChild(rightSide);
            layerItem.appendChild(topRow);
            layerList.appendChild(layerItem);
        });

        // Drag-and-drop ordering enabled
        this._enableDragSort(layerList);
        layerControl.style.display = 'block';
    }

    _enableDragSort(container) {
        let dragEl = null;

        const onDragStart = (e) => {
            dragEl = e.currentTarget;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', dragEl.getAttribute('data-layer-id'));
            dragEl.classList.add('dragging');
        };

        const onDragOver = (e) => {
            e.preventDefault();
            const target = e.target.closest('.layer-item');
            if (!target || target === dragEl) return;
            const rect = target.getBoundingClientRect();
            const next = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
            container.insertBefore(dragEl, next && target.nextSibling || target);
        };

        const onDragEnd = () => {
            if (dragEl) dragEl.classList.remove('dragging');
            dragEl = null;
            this._applyDomOrderToMap(container);
        };

        container.querySelectorAll('.layer-item').forEach(item => {
            item.addEventListener('dragstart', onDragStart);
            item.addEventListener('dragover', onDragOver);
            item.addEventListener('dragend', onDragEnd);
        });
    }

    _readLayerColor(map, layerId) {
        // Returns: [propertyName, value]
        let propName = null;
        if (layerId.endsWith('-line')) propName = 'line-color';
        else if (layerId.endsWith('-fill')) propName = 'fill-color';
        else {
            // Heuristic: try line first, then fill
            if (map.getLayer(layerId) && map.getPaintProperty(layerId, 'line-color') != null) propName = 'line-color';
            else if (map.getLayer(layerId) && map.getPaintProperty(layerId, 'fill-color') != null) propName = 'fill-color';
        }
        const val = propName ? map.getPaintProperty(layerId, propName) : null;
        return [propName, val];
    }

    _normalizeColorToHex(input) {
        try {
            if (!input) return null;
            if (typeof input === 'string') {
                if (input.startsWith('#')) {
                    // normalize #abc -> #aabbcc
                    if (input.length === 4) {
                        return '#' + input[1] + input[1] + input[2] + input[2] + input[3] + input[3];
                    }
                    return input;
                }
                const m = input.match(/rgba?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
                if (m) {
                    const r = parseInt(m[1], 10), g = parseInt(m[2], 10), b = parseInt(m[3], 10);
                    const toHex = (n) => ('0' + n.toString(16)).slice(-2);
                    return '#' + toHex(r) + toHex(g) + toHex(b);
                }
            }
        } catch (_) {}
        return null;
    }

    _resolveStyleColor(styleValue, map) {
        try {
            if (!styleValue) return null;
            // Color could be plain, rgba string, or expression array
            if (typeof styleValue === 'string') return styleValue;
            if (Array.isArray(styleValue)) {
                // Common patterns: ['rgb', r, g, b], ['rgba', r, g, b, a], case/step/interpolate
                const head = styleValue[0];
                if (head === 'rgb' || head === 'rgba') {
                    const r = Number(styleValue[1])|0;
                    const g = Number(styleValue[2])|0;
                    const b = Number(styleValue[3])|0;
                    return `rgb(${r}, ${g}, ${b})`;
                }
                // Fallback: if expression, try to evaluate at current zoom if last literal is color-like
                const literals = styleValue.filter(v => typeof v === 'string' && (v.startsWith('#') || v.startsWith('rgb')));
                if (literals.length > 0) return literals[literals.length - 1];
            }
        } catch (_) {}
        return null;
    }

    _applyDomOrderToMap(container) {
        try {
            const ids = Array.from(container.querySelectorAll('.layer-item'))
                .map(el => el.getAttribute('data-layer-id'))
                .filter(Boolean);
            const map = window.mapLoader?.mapState?.currentMapInstance;
            if (!map || typeof map.moveLayer !== 'function') return;
            // To apply listed order top-to-bottom, move from bottom to top
            for (let i = ids.length - 1; i >= 0; i--) {
                const id = ids[i];
                if (map.getLayer(id)) {
                    map.moveLayer(id);
                    const outlineId = id.endsWith('-fill') ? `${id.replace(/-fill$/, '')}-outline` : `${id}-outline`;
                    if (map.getLayer(outlineId)) map.moveLayer(outlineId);
                }
            }
            // Update state
            if (window.mapLoader?.mapState?.availableLayers) {
                const byId = new Map(window.mapLoader.mapState.availableLayers.map(l => [l.id, l]));
                window.mapLoader.mapState.availableLayers = ids.map(id => byId.get(id)).filter(Boolean);
            }
        } catch (e) {
            console.warn('[WARNING] Failed to apply order to map layers', e);
        }
    }
}