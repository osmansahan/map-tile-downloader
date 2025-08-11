// UI Controller - Handles user interface interactions and data management
// Focuses on region/style management and UI controls

// Global error handling
window.addEventListener('error', function(e) {
    if (e.filename && (e.filename.includes('content.js') || e.filename.includes('extension'))) {
        return false; // Ignore browser extension errors
    }
});

// Core variables
window.serverTypes = window.serverTypes || {
    'CartoDB_Light': 'raster',
    'CartoDB_Dark': 'raster',
    'Stamen_Terrain': 'raster',
    'Stamen_Watercolor': 'raster',
    'OpenMapTiles_Vector': 'vector'
};

// Cache for styles
const stylesCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function getCachedStyles(region) {
    const cached = stylesCache.get(region);
    if (cached && (Date.now() - cached.timestamp) < CACHE_TTL) {
        console.log(`[CACHE HIT] ${region} with region_info: ${!!cached.data.region_info}`);
        return cached.data;
    }
    return null;
}

function setCachedStyles(region, data) {
    stylesCache.set(region, {
        data: data,
        timestamp: Date.now()
    });
    console.log(`[CACHE SET] ${region}`);
}

// Region loading
async function loadRegions() {
    console.log('[INFO] Loading regions...');
    const regionSelect = document.getElementById('regionSelect');
    if (!regionSelect) {
        console.error('regionSelect element not found');
        return;
    }

    regionSelect.innerHTML = '<option value="">Loading regions...</option>';

    try {
        // Load from server first
        const response = await fetch('/list_regions');
        if (response.ok) {
            const data = await response.json();
            if (data.regions && Array.isArray(data.regions) && data.regions.length > 0) {
                populateRegionDropdown(regionSelect, data.regions);
                console.log(`[SUCCESS] Loaded ${data.regions.length} regions from server`);
            }
        }
    } catch (error) {
        console.warn('Failed to load regions from server');
    }

    // Add event listener
    regionSelect.addEventListener('change', handleRegionChange);
}

function populateRegionDropdown(select, regions) {
    select.innerHTML = '<option value="">Select region...</option>';
    regions.forEach(region => {
        const opt = document.createElement('option');
        opt.value = region;
        opt.textContent = region;
        select.appendChild(opt);
    });
}

function handleRegionChange(event) {
    const region = event.target.value;
    const serverSelect = document.getElementById('serverSelect');
    const loadMapBtn = document.getElementById('loadMapBtn');

    if (loadMapBtn) loadMapBtn.disabled = true;
    
    if (!region) {
        serverSelect.innerHTML = '<option value="">Select a region first...</option>';
        serverSelect.disabled = true;
        return;
    }

    console.log(`[INFO] Loading styles for region: ${region}`);

    // Check cache first
    const cachedData = getCachedStyles(region);
    if (cachedData) {
        populateStylesDropdown(serverSelect, cachedData);
        return;
    }

    // Load from server
    loadStylesForRegion(region, serverSelect);
}

async function loadStylesForRegion(region, serverSelect) {
    try {
        serverSelect.innerHTML = '<option value="">Loading styles...</option>';
        serverSelect.disabled = true;

        const response = await fetch(`/region_map_styles/${region}`);
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();
        
        // Cache the data
        setCachedStyles(region, data);
        
        // Populate dropdown
        populateStylesDropdown(serverSelect, data);
        
        console.log(`[SUCCESS] Loaded styles for region: ${region}`);
        
    } catch (error) {
        console.error('[ERROR] Failed to load styles:', error);
        serverSelect.innerHTML = '<option value="">Error loading styles</option>';
        serverSelect.disabled = false;
    }
}

function populateStylesDropdown(selectElement, data) {
    selectElement.innerHTML = '<option value="">Select style...</option>';
    selectElement.disabled = false;
    
    console.log('[INFO] Populating styles dropdown with data:', data);
    
    let totalStyles = 0;

    // Add raster options
    if (data.raster && typeof data.raster === 'object') {
        const rasterCount = Object.keys(data.raster).length;
        if (rasterCount > 0) {
            // Add optgroup for better organization
            const rasterGroup = document.createElement('optgroup');
            rasterGroup.label = `Raster Maps (${rasterCount})`;
            
            Object.entries(data.raster).forEach(([name, info]) => {
                const opt = document.createElement('option');
                opt.value = name;
                
                // Create more informative label
                let label = name;
                if (info.tile_count > 0) {
                    label += ` (${info.tile_count} tiles)`;
                }
                if (info.available_zooms && info.available_zooms.length > 0) {
                    const zoomRange = `${Math.min(...info.available_zooms)}-${Math.max(...info.available_zooms)}`;
                    label += ` [z${zoomRange}]`;
                }
                if (info.source) {
                    label += ` · ${info.source}`;
                }
                
                opt.textContent = label;
                opt.dataset.type = 'raster';
                if (info.source) {
                    opt.setAttribute('data-source', info.source);
                }
                opt.setAttribute('data-min-zoom', (info.min_zoom ?? 10));
                opt.setAttribute('data-max-zoom', (info.max_zoom ?? 15));
                opt.setAttribute('data-tile-count', info.tile_count || 0);
                opt.setAttribute('data-available-zooms', JSON.stringify(info.available_zooms || []));
                
                rasterGroup.appendChild(opt);
                
                // Add to serverTypes
                window.serverTypes[name] = 'raster';
                totalStyles++;
            });
            
            selectElement.appendChild(rasterGroup);
        }
    }

    // Add vector options
    if (data.vector && typeof data.vector === 'object') {
        const vectorCount = Object.keys(data.vector).length;
        if (vectorCount > 0) {
            // Add optgroup for better organization
            const vectorGroup = document.createElement('optgroup');
            vectorGroup.label = `Vector Maps (${vectorCount})`;
            
            Object.entries(data.vector).forEach(([name, info]) => {
                const opt = document.createElement('option');
                opt.value = name;
                
                // Create more informative label
                let label = name;
                if (info.tile_count > 0) {
                    label += ` (${info.tile_count} tiles)`;
                }
                if (info.available_zooms && info.available_zooms.length > 0) {
                    const zoomRange = `${Math.min(...info.available_zooms)}-${Math.max(...info.available_zooms)}`;
                    label += ` [z${zoomRange}]`;
                }
                if (info.source) {
                    label += ` · ${info.source}`;
                }
                
                opt.textContent = label;
                opt.dataset.type = 'vector';
                if (info.source) {
                    opt.setAttribute('data-source', info.source);
                }
                opt.setAttribute('data-min-zoom', (info.min_zoom ?? 10));
                opt.setAttribute('data-max-zoom', (info.max_zoom ?? 15));
                opt.setAttribute('data-tile-count', info.tile_count || 0);
                opt.setAttribute('data-available-zooms', JSON.stringify(info.available_zooms || []));
                
                vectorGroup.appendChild(opt);
                
                // Add to serverTypes
                window.serverTypes[name] = 'vector';
                totalStyles++;
            });
            
            selectElement.appendChild(vectorGroup);
        }
    }
    
    // Show message if no styles found
    if (totalStyles === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'No map styles available for this region';
        opt.disabled = true;
        selectElement.appendChild(opt);
        selectElement.disabled = true;
        console.log('[WARNING] No styles found for selected region');
    } else {
        console.log(`[SUCCESS] Added ${totalStyles} styles to dropdown`);
    }

    // Enable load button when style is selected (remove old listener first)
    selectElement.removeEventListener('change', handleStyleChange);
    selectElement.addEventListener('change', handleStyleChange);
}

function handleStyleChange(event) {
    const selectElement = event.target;
    const loadMapBtn = document.getElementById('loadMapBtn');
    const regionSelect = document.getElementById('regionSelect');
    
    if (loadMapBtn && regionSelect) {
        const hasValidSelection = selectElement.value && regionSelect.value;
        loadMapBtn.disabled = !hasValidSelection;
        
        if (hasValidSelection) {
            const selectedOption = selectElement.options[selectElement.selectedIndex];
            const styleType = selectedOption.dataset.type;
            const minZoom = selectedOption.getAttribute('data-min-zoom');
            const maxZoom = selectedOption.getAttribute('data-max-zoom');
            const tileCount = selectedOption.getAttribute('data-tile-count');
            
            console.log(`[INFO] Style selected: ${selectElement.value} (${styleType}) - ${minZoom}-${maxZoom} zoom, ${tileCount} tiles`);
        }
    }
}

// UI Control Functions
function toggleUI() {
    const controlPanel = document.getElementById('controlPanel');
    const layerControl = document.getElementById('layerControl');
    const toggleBtn = document.getElementById('toggleUIBtn');
    
    if (controlPanel.style.display === 'none') {
        controlPanel.style.display = 'block';
        layerControl.style.display = 'block';
        toggleBtn.textContent = 'Hide Tools';
    } else {
        controlPanel.style.display = 'none';
        layerControl.style.display = 'none';
        toggleBtn.textContent = 'Show Tools';
    }
}

// Expose for inline handlers in index.html
window.resetLayerOrder = resetLayerOrder;
window.showAllLayers = showAllLayers;
window.hideAllLayers = hideAllLayers;
window.fitMapToBounds = fitMapToBounds;

function toggleControlPanel() {
    const content = document.querySelector('.control-content');
    const toggleBtn = document.querySelector('.control-toggle-btn');
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggleBtn.textContent = '−';
    } else {
        content.style.display = 'none';
        toggleBtn.textContent = '+';
    }
}

function toggleLayerControl() {
    const layerList = document.getElementById('layerList');
    const toggleBtn = document.querySelector('.layer-toggle-btn');
    
    if (layerList.style.display === 'none') {
        layerList.style.display = 'block';
        toggleBtn.textContent = '−';
    } else {
        layerList.style.display = 'none';
        toggleBtn.textContent = '+';
    }
}

function resetLayerOrder() {
    try {
        const map = window.currentMap;
        const orig = window.mapLoader?.mapState?.originalLayerOrder;
        if (!map || typeof map.moveLayer !== 'function' || !Array.isArray(orig) || !orig.length) return;
        // Robust approach: move original order from bottom to top
        for (let i = orig.length - 1; i >= 0; i--) {
            const id = orig[i];
            if (!map.getLayer(id)) continue;
            try { map.moveLayer(id); } catch (_) {}
            const outlineId = id.endsWith('-fill') ? `${id.replace(/-fill$/, '')}-outline` : `${id}-outline`;
            if (map.getLayer(outlineId)) {
                try { map.moveLayer(outlineId); } catch (_) {}
            }
        }
        // Align panel DOM order with the original
        const container = document.getElementById('layerList');
        if (container) {
            const items = Array.from(container.querySelectorAll('.layer-item'));
            items.sort((a, b) => {
                const ia = orig.indexOf(a.getAttribute('data-layer-id'));
                const ib = orig.indexOf(b.getAttribute('data-layer-id'));
                return ia - ib;
            });
            items.forEach(el => container.appendChild(el));
        }
    } catch (e) {
        console.warn('[UI] Failed to reset layer order', e);
    }
}

function showAllLayers() {
    try {
        const map = window.currentMap;
        if (!map || !map.getStyle) return;
        const ids = (map.getStyle()?.layers || [])
            .map(l => l.id)
            .filter(id => id && id !== 'background' && map.getLayer(id));
        ids.forEach(id => map.setLayoutProperty(id, 'visibility', 'visible'));
        document.querySelectorAll('#layerList .layer-item input[type="checkbox"]').forEach(cb => cb.checked = true);
        if (window.mapLoader?.mapState?.availableLayers) {
            window.mapLoader.mapState.availableLayers.forEach(l => l.visible = true);
        }
    } catch (e) {
        console.warn('[UI] showAllLayers failed', e);
    }
}

function hideAllLayers() {
    try {
        if (!window.currentMap || !window.currentMap.getStyle) return;
        const map = window.currentMap;
        const style = map.getStyle();
        const ids = (style?.layers || [])
            .map(l => l.id)
            .filter(id => id && id !== 'background' && map.getLayer(id));
        ids.forEach(id => map.setLayoutProperty(id, 'visibility', 'none'));
        // Also clear panel checkboxes
        document.querySelectorAll('#layerList .layer-item input[type="checkbox"]').forEach(cb => { cb.checked = false; });
        // Update state
        if (window.mapLoader?.mapState?.availableLayers) {
            window.mapLoader.mapState.availableLayers.forEach(l => l.visible = false);
        }
    } catch (e) {
        console.warn('[UI] hideAllLayers failed', e);
    }
}

async function fitMapToBounds() {
    try {
        if (!window.currentMap) return;
        const regionSelect = document.getElementById('regionSelect');
        const regionName = regionSelect ? regionSelect.value : null;
        if (!regionName) return;
        // Fetch region bbox from server and apply
        const resp = await fetch(`/region_map_styles/${encodeURIComponent(regionName)}`);
        if (!resp.ok) return;
        const data = await resp.json();
        const bbox = data?.region_info?.bbox;
        if (!Array.isArray(bbox) || bbox.length !== 4) return;
        const sw = [bbox[0], bbox[1]]; // [minLng, minLat]
        const ne = [bbox[2], bbox[3]]; // [maxLng, maxLat]
        // MapLibre fitBounds istiyor: [[lng,lat],[lng,lat]]
        if (window.currentMap.fitBounds) {
            window.currentMap.fitBounds([sw, ne], { padding: 24 });
        } else if (window.currentMap.setView) {
            const center = [(sw[0] + ne[0]) / 2, (sw[1] + ne[1]) / 2];
            window.currentMap.setView([center[1], center[0]], 8);
        }
    } catch (e) {
        console.warn('[UI] fitMapToBounds failed', e);
    }
}

// Expose safe names to avoid shadowing in index.html helpers
window.UIActions = {
    resetLayerOrder,
    resetLayerColors,
    showAllLayers,
    hideAllLayers,
    fitMapToBounds
};

function resetLayerColors() {
    try {
        if (window.mapLoader?.mapState?.currentMapType !== 'maplibre') return;
        const map = window.currentMap;
        const originals = window.mapLoader?.mapState?.layerOriginalColors || {};
        Object.keys(originals).forEach(id => {
            const info = originals[id];
            if (!info || !info.property) return;
            if (map.getLayer(id)) {
                try { map.setPaintProperty(id, info.property, info.value); } catch (_) {}
            }
        });
        // Reset panel color inputs to previous values as well
        document.querySelectorAll('#layerList .layer-item').forEach(item => {
            const id = item.getAttribute('data-layer-id');
            const info = originals[id];
            const input = item.querySelector('.layer-color input[type="color"]');
            if (info && input && info.hex) input.value = info.hex;
            const swatch = item.querySelector('.layer-color');
            if (info && swatch && info.hex) swatch.style.backgroundColor = info.hex;
        });
    } catch (e) {
        console.warn('[UI] Failed to reset layer colors', e);
    }
}

// Event Listeners
function initializeEventListeners() {
    const regionSelect = document.getElementById('regionSelect');
    const serverSelect = document.getElementById('serverSelect');
    const loadMapBtn = document.getElementById('loadMapBtn');
    
    if (!regionSelect || !serverSelect || !loadMapBtn) {
        console.error("Required UI elements not found!");
        return;
    }
    
    // Server select change - enable/disable load button
    serverSelect.addEventListener('change', function() {
        // Enable load button only if both region and server are selected
        if (regionSelect.value && serverSelect.value) {
            loadMapBtn.disabled = false;
        } else {
            loadMapBtn.disabled = true;
        }
    });
    
    // Load map button click
    loadMapBtn.addEventListener('click', function() {
        if (typeof window.loadMap === 'function') {
            window.loadMap();
        } else {
            console.error('loadMap function not found');
            alert('Map loading functionality not available. Please refresh the page.');
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('[INFO] UI Controller initializing...');
    
    // Load regions
    loadRegions();
    
    // Initialize event listeners
    initializeEventListeners();
    
    console.log('[SUCCESS] UI Controller initialized');
});
