import concurrent.futures
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests

# Ensure 'src' directory is on sys.path when running this script directly
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parents[1]
if str(_src_dir) not in [str(p) for p in sys.path]:
    sys.path.insert(0, str(_src_dir))

from services.config_service import ConfigService
from models.tile_server import TileServer
from utils.tile_calculator import TileCalculator


def choose_region_and_tile(config: Dict) -> Tuple[int, int, int]:
    regions = config.get("regions", {})
    preferred = ["istanbul", "ankara", "turkiye", "qatar"]
    region_name = None
    for name in preferred:
        if name in regions:
            region_name = name
            break
    if region_name is None and regions:
        region_name = next(iter(regions.keys()))
    if region_name is None:
        # Default to a global z/x/y
        return (2, 1, 1)

    region = regions[region_name]
    bbox = region["bbox"]
    z = int(region.get("min_zoom", 5))
    tiles = TileCalculator.get_tiles_for_bbox(bbox, z, z)
    if not tiles:
        return (2, 1, 1)
    z0, x0, y0 = tiles[0]
    return (z0, x0, y0)


def create_session(timeout: int) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "ServerChecker/1.0"})
    s.timeout = timeout
    return s


def validate_content(tile_type: str, content: bytes) -> Tuple[bool, str]:
    if not content or len(content) == 0:
        return False, "empty content"
    # Best-effort magic checks
    if tile_type == "raster":
        # PNG or JPEG minimal
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return True, "png"
        if content.startswith(b"\xff\xd8"):
            return True, "jpeg"
        # Some servers may return webp, try RIFF/WEBP header
        if content.startswith(b"RIFF") and b"WEBP" in content[:16]:
            return True, "webp?"
        # Accept non-empty as last resort
        return True, "non-empty raster"
    else:
        # Vector tiles are often gzipped protobuf
        if content.startswith(b"\x1f\x8b"):
            return True, "gzipped pbf"
        # Accept non-empty as last resort
        return True, "non-empty vector"


def test_server(session: requests.Session, server: TileServer, coord: Tuple[int, int, int], timeout: int) -> Dict:
    z, x, y = coord
    url = server.get_tile_url(z, x, y)
    headers = server.get_headers()
    try:
        resp = session.get(url, headers=headers, timeout=timeout)
        status = resp.status_code
        if not (200 <= status < 300):
            return {"name": server.get_name(), "type": server.get_tile_type(), "ok": False, "reason": f"HTTP {status}", "url": url}
        ok, info = validate_content(server.get_tile_type(), resp.content)
        return {"name": server.get_name(), "type": server.get_tile_type(), "ok": ok, "reason": info if ok else "empty", "url": url}
    except Exception as e:
        return {"name": server.get_name(), "type": server.get_tile_type(), "ok": False, "reason": str(e), "url": url}


def main():
    cfg_service = ConfigService()
    cfg = cfg_service.load_config("config.json")
    servers: List[TileServer] = cfg_service.get_enabled_servers(cfg)
    http_servers = [s for s in servers]
    if not http_servers:
        print("[HATA] Test edilecek HTTP sunucusu bulunamadı (config.servers).")
        sys.exit(2)

    coord = choose_region_and_tile(cfg)
    print(f"[BİLGİ] Test edilecek koordinat: z={coord[0]} x={coord[1]} y={coord[2]}")

    timeout = int(cfg.get("timeout", 30))
    session = create_session(timeout)

    print("\nSunucu durumu (tek tile isteği ile):")
    print("-" * 80)
    print(f"{'Name':30} {'Type':8} {'OK?':5} Reason")
    print("-" * 80)

    results: List[Dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(http_servers))) as ex:
        futs = [ex.submit(test_server, session, s, coord, timeout) for s in http_servers]
        for f in concurrent.futures.as_completed(futs):
            results.append(f.result())

    # Stable order by name
    results.sort(key=lambda r: r["name"].lower())
    ok_count = 0
    for r in results:
        ok = "OK" if r["ok"] else "FAIL"
        if r["ok"]:
            ok_count += 1
        print(f"{r['name'][:30]:30} {r['type'][:8]:8} {ok:5} {r['reason']}")

    print("-" * 80)
    print(f"Çalışan sunucu sayısı: {ok_count}/{len(results)}")

    # Exit code non-zero if none are working
    sys.exit(0 if ok_count > 0 else 1)


if __name__ == "__main__":
    main()


