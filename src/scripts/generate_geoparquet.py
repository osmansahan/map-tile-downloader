import sys
import os
import traceback
import argparse
from pathlib import Path
from typing import Optional

import geopandas as gpd
try:
    import pyogrio
    from pyogrio import read_dataframe as ogr_read_dataframe
    from pyogrio.env import Env as OgrEnv
    HAS_PYOGRIO = True
except Exception:
    HAS_PYOGRIO = False
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Remove GDAL limit for large GeoJSON objects
os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")
DATA_DIR = PROJECT_ROOT / "geocoordinate_data"


def to_parquet_safe(gdf: gpd.GeoDataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(out_path)


def normalize_countries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    name_candidates = [
        "adm0_name",
        "ADMIN",
        "ADM0_NAME",
        "NAME_ENGLI",
        "NAME_EN",
        "NAME",
        "name_en",
    ]
    name_col = next((c for c in name_candidates if c in gdf.columns), None)
    if name_col and name_col != "adm0_name":
        gdf = gdf.rename(columns={name_col: "adm0_name"})

    # CRS: ensure EPSG:4326 / CRS84
    try:
        crs_obj = gdf.crs
    except Exception:
        crs_obj = None
    if crs_obj is None:
        try:
            gdf = gdf.set_crs("OGC:CRS84", inplace=False)
        except Exception:
            pass
    else:
        try:
            epsg = crs_obj.to_epsg()
        except Exception:
            epsg = None
        if epsg != 4326:
            try:
                gdf = gdf.to_crs(4326)
            except Exception:
                pass

    return gdf


def read_geojson(path: Path) -> Optional[gpd.GeoDataFrame]:
    if not path.exists():
        print(f"Skip: {path} yok")
        return None
    try:
        # Try pyogrio engine first (more robust and faster)
        if HAS_PYOGRIO:
            try:
                with OgrEnv(GDAL_CACHEMAX=1024, OGR_GEOJSON_MAX_OBJ_SIZE=0):
                    return gpd.read_file(path, engine="pyogrio")
            except Exception:
                # If GeoPandas+pyogrio fails, try pyogrio API directly
                try:
                    with OgrEnv(GDAL_CACHEMAX=1024, OGR_GEOJSON_MAX_OBJ_SIZE=0):
                        gdf = ogr_read_dataframe(path)
                        return gpd.GeoDataFrame(gdf, geometry=gdf.geometry, crs=gdf.crs)
                except Exception as e2:
                    print(f"pyogrio read error: {e2}")
        # Last resort: default engine
        return gpd.read_file(path)
    except Exception as e:
        print(f"Error: could not read {path}: {e}")
        return None


def validate_equivalence(src: gpd.GeoDataFrame, pq_path: Path) -> bool:
    try:
        dst = gpd.read_parquet(pq_path)

        # Row count and column set equality
        if len(src) != len(dst):
            print(f"Validation failed: row count differs ({len(src)} != {len(dst)})")
            return False
        if set(src.columns) != set(dst.columns):
            print("Validation warning: column set may differ (order/name).")

        # total_bounds proximity (allow small float tolerance)
        if not np.allclose(src.total_bounds, dst.total_bounds, rtol=0, atol=1e-12):
            print(f"Validation failed: total_bounds differ {src.total_bounds} vs {dst.total_bounds}")
            return False

        # Geometry equality by sample records (first, middle, last)
        idxs = [0, len(src) // 2, len(src) - 1] if len(src) >= 3 else list(range(len(src)))
        for i in idxs:
            if not src.geometry.iloc[i].equals(dst.geometry.iloc[i]):
                print(f"Validation failed: geometry differs at index={i}")
                return False

        return True
    except Exception:
        traceback.print_exc()
        return False


def build_parquet(geojson_name: str, parquet_name: str, normalize: bool = False) -> None:
    src_path = DATA_DIR / geojson_name
    pq_path = DATA_DIR / parquet_name

    gdf = read_geojson(src_path)
    if gdf is None:
        return

    if normalize:
        gdf = normalize_countries(gdf)

    to_parquet_safe(gdf, pq_path)
    print(f"OK: {pq_path}")

    # doğrulama (kayıpsızlık testi)
    ok = validate_equivalence(gdf, pq_path)
    if not ok:
        print(f"HATA: Doğrulama başarısız: {parquet_name}")
        sys.exit(2)
    else:
        print(f"Doğrulama başarılı: {parquet_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="GeoJSON -> GeoParquet dönüşümü (doğrulamalı)")
    parser.add_argument("--only-provinces", action="store_true", help="Sadece illeri dönüştür")
    parser.add_argument("--only-districts", action="store_true", help="Sadece ilçeleri dönüştür")
    parser.add_argument("--only-countries", action="store_true", help="Sadece ülkeleri dönüştür")
    parser.add_argument("--skip-countries", action="store_true", help="Ülkeleri atla")
    args = parser.parse_args()

    print(f"DATA_DIR: {DATA_DIR}")
    if not DATA_DIR.exists():
        print("HATA: geocoordinate_data dizini bulunamadı")
        sys.exit(1)

    run_provinces = args.only_provinces or not (args.only_districts or args.only_countries)
    run_districts = args.only_districts or not (args.only_provinces or args.only_countries)
    run_countries = args.only_countries or (not (args.only_provinces or args.only_districts))

    if run_provinces and not args.only_districts and not args.only_countries:
        # In default mode, all run; run_provinces already True
        pass

    if run_provinces:
        build_parquet("provinces_original.geojson", "provinces.parquet", normalize=False)

    if run_districts:
        build_parquet("districts_original.geojson", "districts.parquet", normalize=False)

    if run_countries and not args.skip_countries:
        countries_geojson = DATA_DIR / "countries_original_merged.geojson"
        if countries_geojson.exists():
            build_parquet("countries_original_merged.geojson", "countries.parquet", normalize=True)
        else:
            print("Uyarı: countries_original_merged.geojson bulunamadı (opsiyonel)")

    print("Tamamlandı.")


if __name__ == "__main__":
    main()


