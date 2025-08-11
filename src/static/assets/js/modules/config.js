export const STYLE_DEFAULTS = {
    backgroundColor: '#f8f4f0',
    tileSize: 512,
    scaleControl: {
        maxWidth: 100,
        unit: 'metric'
    },
    baseVectorLayers: [
        { name: 'water', type: 'fill', color: 'rgba(100, 150, 255, 0.7)', outlineColor: 'blue' },
        { name: 'landuse', type: 'fill', color: 'rgba(100, 255, 100, 0.5)', outlineColor: 'green' },
        { name: 'building', type: 'fill', color: 'rgba(200, 200, 200, 0.8)', outlineColor: 'gray' },
        { name: 'transportation', type: 'line', color: 'red', lineWidth: 2 }
    ]
};

// Allow runtime override via window.STYLE_DEFAULTS if provided
export function getStyleDefaults() {
    const runtime = (typeof window !== 'undefined' && window.STYLE_DEFAULTS) ? window.STYLE_DEFAULTS : {};
    return {
        ...STYLE_DEFAULTS,
        ...runtime,
        scaleControl: { ...STYLE_DEFAULTS.scaleControl, ...(runtime.scaleControl || {}) },
        baseVectorLayers: Array.isArray(runtime.baseVectorLayers) ? runtime.baseVectorLayers : STYLE_DEFAULTS.baseVectorLayers
    };
}

