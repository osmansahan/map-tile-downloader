export class CoordinateUtils {
    constructor() {}

    latLngToTileCoords(lat, lng, zoom) {
        const clampedLat = Math.max(-85.05, Math.min(85.05, lat));
        
        if (isNaN(zoom) || !isFinite(zoom) || zoom < 0 || zoom > 22) {
            console.warn(`[WARNING] Invalid zoom level: ${zoom}`);
            return null;
        }
        
        const n = Math.pow(2, zoom);
        
        if (!isFinite(n)) {
            console.warn(`[WARNING] Math.pow(2, ${zoom}) returned Infinity, using zoom 10`);
            zoom = 10;
            const n = Math.pow(2, zoom);
        }
        
        const x = Math.floor((lng + 180) / 360 * n);
        const latRad = clampedLat * Math.PI / 180;
        const y = Math.floor((1 - Math.asinh(Math.tan(latRad)) / Math.PI) / 2 * n);
        
        if (!isFinite(x) || !isFinite(y)) {
            console.warn(`[WARNING] Invalid tile coordinates calculated: x=${x}, y=${y} for lat=${lat}, lng=${lng}, zoom=${zoom}`);
            return { x: 0, y: 0 };
        }
        
        return { x, y };
    }

    async calculateRegionCenter(regionName) {
        const regionData = await this.getRegionData(regionName);
        
        if (regionData && regionData.bbox) {
            const bbox = regionData.bbox;
            const centerLng = (bbox[0] + bbox[2]) / 2;
            const centerLat = (bbox[1] + bbox[3]) / 2;
            
            if (this.isValidCoordinate(centerLng, centerLat)) {
                console.log(`[DEBUG] Calculated dynamic center for ${regionName}: [${centerLng}, ${centerLat}]`);
                return [centerLng, centerLat];
            }
        }
        
        console.warn(`[WARNING] Could not determine center for ${regionName} - no valid metadata found`);
        return null;
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

    async getEffectiveCenter(regionName, serverName, serverType) {
        const data = await this.getRegionData(regionName);
        if (!data) return null;

        const stylesRoot = (data.styles && (data.styles[serverType] || data[serverType])) || null;
        const styleEntry = stylesRoot && (stylesRoot[serverName] || stylesRoot.find?.(s => s?.name === serverName));
        if (styleEntry) {
            if (Array.isArray(styleEntry.center) && styleEntry.center.length === 2) {
                const [lng, lat] = styleEntry.center;
                if (this.isValidCoordinate(lng, lat)) return [lng, lat];
            }
            if (Array.isArray(styleEntry.bounds) && styleEntry.bounds.length === 2) {
                const [[minLat, minLng], [maxLat, maxLng]] = styleEntry.bounds;
                const centerLng = (minLng + maxLng) / 2;
                const centerLat = (minLat + maxLat) / 2;
                if (this.isValidCoordinate(centerLng, centerLat)) return [centerLng, centerLat];
            }
            if (Array.isArray(styleEntry.bbox) && styleEntry.bbox.length === 4) {
                const [minLng, minLat, maxLng, maxLat] = styleEntry.bbox;
                const centerLng = (minLng + maxLng) / 2;
                const centerLat = (minLat + maxLat) / 2;
                if (this.isValidCoordinate(centerLng, centerLat)) return [centerLng, centerLat];
            }
        }

        if (Array.isArray(data.center) && data.center.length === 2) {
            const [lng, lat] = data.center;
            if (this.isValidCoordinate(lng, lat)) return [lng, lat];
        }
        if (Array.isArray(data.bbox) && data.bbox.length === 4) {
            const [minLng, minLat, maxLng, maxLat] = data.bbox;
            const centerLng = (minLng + maxLng) / 2;
            const centerLat = (minLat + maxLat) / 2;
            if (this.isValidCoordinate(centerLng, centerLat)) return [centerLng, centerLat];
        }

        return null;
    }

    async getEffectiveBounds(regionName, serverName, serverType) {
        const data = await this.getRegionData(regionName);
        if (!data) return null;

        const stylesRoot = (data.styles && (data.styles[serverType] || data[serverType])) || null;
        const styleEntry = stylesRoot && (stylesRoot[serverName] || stylesRoot.find?.(s => s?.name === serverName));
        if (styleEntry) {
            if (Array.isArray(styleEntry.bounds) && styleEntry.bounds.length === 2) {
                return styleEntry.bounds;
            }
            if (Array.isArray(styleEntry.bbox) && styleEntry.bbox.length === 4) {
                const [minLng, minLat, maxLng, maxLat] = styleEntry.bbox;
                return [[minLat, minLng], [maxLat, maxLng]];
            }
        }

        if (Array.isArray(data.bounds) && data.bounds.length === 2) {
            return data.bounds;
        }
        if (Array.isArray(data.bbox) && data.bbox.length === 4) {
            const [minLng, minLat, maxLng, maxLat] = data.bbox;
            return [[minLat, minLng], [maxLat, maxLng]];
        }

        return null;
    }

    async getRegionBounds(regionName) {
        const regionData = await this.getRegionData(regionName);
        return regionData ? regionData.bounds : [[39.0, 32.0], [42.0, 35.0]];
    }

    async getRegionCenter(regionName) {
        const regionData = await this.getRegionData(regionName);
        if (regionData && regionData.center) {
            const [lng, lat] = regionData.center;
            if (this.isValidCoordinate(lng, lat)) {
                return regionData.center;
            } else {
                console.warn(`[WARNING] Invalid center coordinates for ${regionName}: [${lng}, ${lat}]`);
            }
        }
        // No hard-coded fallback; return null to force caller to handle.
        return null;
    }

    isValidCoordinate(lng, lat) {
        return !isNaN(lng) && !isNaN(lat) && 
               isFinite(lng) && isFinite(lat) &&
               lng >= -180 && lng <= 180 &&
               lat >= -85.05 && lat <= 85.05;
    }
}