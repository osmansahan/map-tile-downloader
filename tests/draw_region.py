# draw_region.py (test helper)
import sys
import json
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from shapely.geometry import shape

# Add project modules to import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / 'src'))

from geocoordinate.api import CoordinateAPI  # noqa: E402


def plot_geometry(ax, geom, edge_color='#ff0000', face_color='none', lw=1.5, alpha=0.9):
    gt = geom.geom_type
    if gt == 'Polygon':
        x, y = geom.exterior.xy
        ax.plot(x, y, color=edge_color, linewidth=lw, alpha=alpha)
        for ring in geom.interiors:
            rx, ry = ring.xy
            ax.plot(rx, ry, color=edge_color, linewidth=1.0, alpha=0.6, linestyle='--')
    elif gt == 'MultiPolygon':
        for poly in geom.geoms:
            plot_geometry(ax, poly, edge_color, face_color, lw, alpha)
    else:
        try:
            x, y = geom.exterior.xy
            ax.plot(x, y, color=edge_color, linewidth=lw, alpha=alpha)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Draw region polygon(s) with bounding box and center.\n'
            '- Provide multiple regions separated by commas.\n'
            '- Use --show-internal to keep internal borders visible for multiple regions.'
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            'Examples:\n'
            '  Province (show on screen):\n'
            '    python tests/draw_region.py --place "Ankara" --region-type province\n\n'
            '  District (save to file):\n'
            '    python tests/draw_region.py --place "Cankaya" --region-type district --out cankaya.png\n\n'
            '  Country:\n'
            '    python tests/draw_region.py --place "Germany" --region-type country\n\n'
            '  Multiple regions (show internal borders):\n'
            '    python tests/draw_region.py --place "Istanbul, Kocaeli" --region-type province --show-internal --out ist_koc.png\n\n'
            'Tip: If you encounter issues with non-ASCII characters, try ASCII equivalents (e.g., Istanbul).'
        )
    )
    parser.add_argument(
        '--place',
        default='istanbul',
        help=(
            'Region name(s).\n'
            '- Single: "Ankara"\n'
            '- Multiple: "Istanbul, Kocaeli" (use quotes and separate by comma)'
        )
    )
    parser.add_argument(
        '--region-type',
        default='province',
        choices=['auto', 'province', 'district', 'country'],
        help=(
            'Region type.\n'
            '- auto: Auto-detect from names\n'
            '- province: Province\n'
            '- district: District\n'
            '- country: Country'
        )
    )
    parser.add_argument(
        '--data-dir',
        default=str(PROJECT_ROOT / 'geocoordinate_data'),
        help='Geocoordinate data directory (default: geocoordinate_data)'
    )
    parser.add_argument(
        '--out',
        default=None,
        help='PNG output file (e.g., out.png). If omitted, the figure is shown on screen.'
    )
    parser.add_argument(
        '--show-internal',
        action='store_true',
        help='For multiple regions, draw each separately with distinct colors to keep internal borders visible.'
    )
    args = parser.parse_args()

    api = CoordinateAPI(args.data_dir)

    places = [p.strip() for p in args.place.split(',') if p.strip()]
    multiple = len(places) > 1 and args.show_internal

    fig, ax = plt.subplots(figsize=(8, 8))

    if multiple:
        colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#a65628', '#f781bf', '#999999']
        all_bounds = []
        for idx, place in enumerate(places):
            r = api.find_coordinates(place, args.region_type)
            if not r.get('success'):
                print('Hata:', r.get('error') or 'Bilinmeyen hata', '->', place)
                continue
            c = r['coordinates']
            poly = shape(c['polygon'])
            plot_geometry(ax, poly, edge_color=colors[idx % len(colors)], lw=1.8, alpha=0.95)
            b = c['bounding_box']['bounds']
            all_bounds.append((b['min_lon'], b['min_lat'], b['max_lon'], b['max_lat']))
            ctr = c['center']
            ax.plot(ctr['lon'], ctr['lat'], marker='o', color=colors[idx % len(colors)],
                    markersize=4, label=place)

        if not all_bounds:
            print('Hiçbir bölge başarıyla bulunamadı')
            sys.exit(1)

        min_lon = min(b[0] for b in all_bounds)
        min_lat = min(b[1] for b in all_bounds)
        max_lon = max(b[2] for b in all_bounds)
        max_lat = max(b[3] for b in all_bounds)

        rect = Rectangle((min_lon, min_lat),
                         max_lon - min_lon,
                         max_lat - min_lat,
                         linewidth=1.0,
                         edgecolor='#3333ff',
                         facecolor='none',
                         linestyle=':')
        ax.add_patch(rect)

        ax.set_title(f"{', '.join(places)} ({args.region_type}) - internal boundaries shown")
    else:
        res = api.find_coordinates(args.place, args.region_type)

        if not res.get('success'):
            print('Hata:', res.get('error') or 'Bilinmeyen hata')
            print('Not found:', res.get('not_found'))
            sys.exit(1)

        coords = res['coordinates']
        poly_geojson = coords['polygon']
        bounds = coords['bounding_box']['bounds']
        center = coords['center']

        geom = shape(poly_geojson)
        plot_geometry(ax, geom)

        min_lon, min_lat, max_lon, max_lat = bounds['min_lon'], bounds['min_lat'], bounds['max_lon'], bounds['max_lat']
        rect = Rectangle((min_lon, min_lat),
                         max_lon - min_lon,
                         max_lat - min_lat,
                         linewidth=1.0,
                         edgecolor='#3333ff',
                         facecolor='none',
                         linestyle=':')
        ax.add_patch(rect)

        ax.plot(center['lon'], center['lat'], 'ko', markersize=5, label='Merkez')

        ax.set_title(f"{args.place} ({res['region_type']})")
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend(loc='best')
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, alpha=0.3)

    pad_x = (max_lon - min_lon) * 0.05 or 0.05
    pad_y = (max_lat - min_lat) * 0.05 or 0.05
    ax.set_xlim(min_lon - pad_x, max_lon + pad_x)
    ax.set_ylim(min_lat - pad_y, max_lat + pad_y)

    if args.out:
        fig.savefig(args.out, dpi=150, bbox_inches='tight')
        print(f'Kaydedildi: {args.out}')
    else:
        plt.show()


if __name__ == '__main__':
    main()


