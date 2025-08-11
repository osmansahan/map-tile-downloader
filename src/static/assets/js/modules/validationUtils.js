export class ValidationUtils {
    constructor() {}

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
}