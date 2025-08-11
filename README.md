# Tile Map Downloader

An end-to-end, scriptable map-tile downloader and lightweight viewer. The project supports multiple online tile servers (vector/raster), parallel downloading with retries, optional local MBTiles sources, and a small HTTP server to explore downloaded tiles.

This README explains the full setup, how to obtain the large data dependencies (GeoCoordinate data and MBTiles) outside of Git, and provides step-by-step usage examples.

## Highlights

- Parallel downloads with retry/backoff
- Multiple sources: vector and raster online servers, optional local MBTiles
- Fallback logic across servers (e.g., try vector, fall back to raster)
- Zero-byte/empty-content safeguards for tiles
- Map tile HTTP server with caching headers
- Optional metadata syncing and audit tools
- GeoCoordinate lookup for bbox by place/country/province/district

## Project Structure

```
src/
  adapters/                 # Local MBTiles adapter
  core/                     # Main download manager
  exceptions/               # Custom exception types
  geocoordinate/            # GeoCoordinate API (bbox/lookup/search)
  infrastructure/           # Logging utilities
  models/                   # Data models
  services/                 # Download, source factory, config (JSON), HTTP server
  scripts/                  # Helper scripts (data check, parquet generation, metadata)
  static/                   # Web UI
  templates/                # Web UI
  tile_downloader.py        # CLI entry to download tiles
  web_server.py             # Local HTTP server (viewer)

config.json                 # Main configuration (regions, servers)
geocoordinate_data/         # Geo datasets (placed manually; see below)
mbtiles/                    # Local MBTiles datasets (placed manually; see below)
map_tiles/                  # Output tiles and metadata (generated)
```

## Requirements

- Python 3.9+ recommended (3.12 tested)
- pip

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Getting the Data (must-do before first run)

These large datasets are not stored in the repository. Download them and place as described.

1) GeoCoordinate data folder (place boundaries, indexes)

- Download from: [GeoCoordinate Data (Google Drive)](https://drive.google.com/drive/folders/1OgrhqSFaPmRj3H0P65lSTnonToGSjEMP?usp=sharing)
- Expected files inside `geocoordinate_data/` (example sizes):
  - `countries.parquet` (~1.14 GB)
  - `provinces.parquet` (~17.2 MB)
  - `districts.parquet` (~43.5 MB)
  - `metadata_original.json` (~218 KB)

Folder placement:

```
TileMapDownloader/
  geocoordinate_data/
    countries.parquet
    provinces.parquet
    districts.parquet
    metadata_original.json
```

2) Local MBTiles (optional; used as local sources)

- Download from: [MBTiles (Google Drive)](https://drive.google.com/drive/folders/1vfLiHNs9gZB0z-aojFhfn_4Gxegh5gqm?usp=sharing)
- Place the `.mbtiles` files into the `mbtiles/` folder:

```
TileMapDownloader/
  mbtiles/
    your_file_1.mbtiles
    your_file_2.mbtiles
```

Why manual placement? Large data cannot be committed to GitHub; users must download and place folders locally.

## Configuration (config.json)

The `config.json` controls regions, servers and output. Example (shortened):

```json
{
  "regions": {
    "istanbul": {
      "bbox": [28.5, 40.8, 29.5, 41.2],
      "min_zoom": 10,
      "max_zoom": 12,
      "description": "Istanbul region"
    }
  },
  "servers": [
    {
      "name": "OpenMapTiles_Vector",
      "type": "http",
      "url": "https://api.maptiler.com/tiles/v3/{z}/{x}/{y}.pbf?key=YOUR_KEY",
      "headers": {"User-Agent": "TileDownloader/1.0"},
      "tile_type": "vector"
    },
    {
      "name": "CartoDB_Light",
      "type": "http",
      "url": "https://cartodb-basemaps-b.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
      "headers": {"User-Agent": "TileDownloader/1.0"},
      "tile_type": "raster"
    }
  ],
  "output_dir": "map_tiles",
  "max_workers_per_server": 15,
  "retry_attempts": 3,
  "timeout": 30
}
```

Notes
- You can add local sources (MBTiles) in `config.json` with `type: "local"`. The downloader will use those as sources when requested.
- Vector servers are tried first, raster servers can serve as fallback.

## First-time Setup (Step-by-step)

1) Clone the repo and install requirements

```bash
pip install -r requirements.txt
```

2) Download data folders and place them

- Download GeoCoordinate data and put into `geocoordinate_data/`:
  - [GeoCoordinate Data (Google Drive)](https://drive.google.com/drive/folders/1OgrhqSFaPmRj3H0P65lSTnonToGSjEMP?usp=sharing)
- (Optional) Download MBTiles and put into `mbtiles/`:
  - [MBTiles (Google Drive)]([https://drive.google.com/drive/folders/1vfLiHNs9gZB0z-aojFhfn_4Gxegh5gqm?usp=drive_link](https://drive.google.com/drive/folders/1vfLiHNs9gZB0z-aojFhfn_4Gxegh5gqm?usp=sharing))

3) Verify GeoCoordinate data is visible

```bash
python - << "PY"
import os
base = 'geocoordinate_data'
print('countries.parquet:', os.path.exists(os.path.join(base,'countries.parquet')))
print('provinces.parquet:', os.path.exists(os.path.join(base,'provinces.parquet')))
print('districts.parquet:', os.path.exists(os.path.join(base,'districts.parquet')))
print('metadata_original.json:', os.path.exists(os.path.join(base,'metadata_original.json')))
PY
```

4) (Optional) Check which servers are healthy for your network

```bash
python src/scripts/check_servers.py
```

5) Download tiles

Examples:

```bash
# Download for a named region in config.json using online servers
python src/tile_downloader.py --region istanbul --servers "CartoDB_Light,OpenMapTiles_Vector"

# Download by bbox
python src/tile_downloader.py --bbox 28.5 40.8 29.5 41.2 --min-zoom 10 --max-zoom 12 --servers "CartoDB_Light"

# Use local MBTiles sources (if configured in config.json)
python src/tile_downloader.py --region ankara --sources "Local_OSM_Turkey"
```

6) View tiles in browser

```bash
python src/web_server.py
# open http://localhost:8080
```

Downloaded tiles are saved under `map_tiles/<region>/<raster|vector>/<server>/<z>/<x>/<y>.<ext>` and metadata is generated under `map_tiles/metadata/regions/`.

## Useful Scripts

- Server health check:
  - `python src/scripts/check_servers.py`
- Generate GeoParquet from GeoJSON (optional):
  - `python src/scripts/generate_geoparquet.py`
- Verify `countries.parquet` integrity:
  - `python src/scripts/verify_countries_parquet.py`
- Metadata audit and quick status:
  - `python src/scripts/metadata_status.py`
  - `python sync_metadata.py` (audit/sync full pass)

## Troubleshooting

- Empty tiles are not saved as valid; the downloader re-tries or falls back to another server.
- If country-level lookups fail, ensure `geocoordinate_data/metadata_original.json` exists and that at least one of `countries.parquet` or `countries.fgb` is present.
- For MBTiles sources, make sure requested bbox intersects the MBTiles bounds defined in `config.json`.

## License

MIT
