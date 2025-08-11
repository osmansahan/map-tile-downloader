export class MapState {
    constructor() {
        this.currentMapInstance = null;
        this.currentMapType = null;
        this.currentTileLayer = null;
        this.availableLayers = [];
        this.vectorLayers = {};
        this.serverTypes = window.serverTypes || {};
        this.layerOriginalColors = {};
    }

    setMapInstance(mapInstance, mapType) {
        this.currentMapInstance = mapInstance;
        this.currentMapType = mapType;
    }

    setTileLayer(tileLayer) {
        this.currentTileLayer = tileLayer;
    }

    addLayer(layer) {
        this.availableLayers.push(layer);
    }

    clearLayers() {
        this.availableLayers = [];
    }

    reset() {
        this.currentMapInstance = null;
        this.currentMapType = null;
        this.currentTileLayer = null;
        this.availableLayers = [];
        this.vectorLayers = {};
        this.layerOriginalColors = {};
    }

    getLayerColor(index) {
        const colors = [
            '#3388ff', '#ff3388', '#33ff88', '#8833ff', '#ff8833',
            '#33ffff', '#ff33ff', '#ffff33', '#ff3333', '#33ff33'
        ];
        return colors[index % colors.length];
    }
}