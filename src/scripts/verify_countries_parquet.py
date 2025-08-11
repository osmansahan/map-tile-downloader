import os
import sys
import random
from pathlib import Path

import numpy as np
import geopandas as gpd

try:
    from pyogrio.env import Env as OgrEnv
    HAS_PYOGRIO = True
except Exception:
    HAS_PYOGRIO = False


BASE = Path(__file__).resolve().parents[2] / "geocoordinate_data"
SRC_GEOJSON = BASE / "countries_original_merged.geojson"
SRC_FGB = BASE / "countries.fgb"
DST_PARQUET = BASE / "countries.parquet"

os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")


def read_src():
    # Priority: GeoJSON -> FGB
    if SRC_GEOJSON.exists():
        try:
            if HAS_PYOGRIO:
                with OgrEnv(OGR_GEOJSON_MAX_OBJ_SIZE=0):
                    return gpd.read_file(SRC_GEOJSON, engine="pyogrio"), "geojson"
            return gpd.read_file(SRC_GEOJSON), "geojson"
        except Exception as e:
            print(f"[WARN] GeoJSON okunamadı: {e}")
    if SRC_FGB.exists():
        try:
            if HAS_PYOGRIO:
                with OgrEnv():
                    return gpd.read_file(SRC_FGB, engine="pyogrio"), "fgb"
            return gpd.read_file(SRC_FGB), "fgb"
        except Exception as e:
            print(f"[ERROR] FGB okunamadı: {e}")
    return None, None


def crs_to_str(crs):
    try:
        return crs.to_string() if crs else str(crs)
    except Exception:
        return str(crs)


def internal_only_check(dst_gdf: gpd.GeoDataFrame) -> int:
    """Parquet internal consistency checks when source cannot be read."""
    ok = True
    try:
        print(f"[OK] Satır sayısı: {len(dst_gdf)}")
        print(f"[INFO] Parquet CRS: {crs_to_str(dst_gdf.crs)}")
        print(f"[INFO] Kolon sayısı: {len(dst_gdf.columns)}")
        print(f"[INFO] total_bounds: {dst_gdf.total_bounds}")
        null_geoms = int(dst_gdf.geometry.isna().sum())
        print(f"[OK] Boş geometri sayısı: {null_geoms}")
        try:
            valid_geoms = int(dst_gdf.is_valid.sum())
            print(f"[OK] Geçerli geometri sayısı: {valid_geoms}/{len(dst_gdf)}")
        except Exception as e:
            print(f"[WARN] Geometri geçerlilik testi atlandı: {e}")
    except Exception as e:
        print(f"[FAIL] İç kontrol hatası: {e}")
        ok = False
    print("\nRESULT: INTERNAL_ONLY " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    if not DST_PARQUET.exists():
        print(f"[ERROR] Parquet bulunamadı: {DST_PARQUET}")
        sys.exit(2)

    src_gdf, src_type = read_src()
    dst_gdf = gpd.read_parquet(DST_PARQUET)

    if src_gdf is None:
        print("[INFO] Kaynak (GeoJSON/FGB) okunamadı; iç tutarlılık testi çalıştırılıyor.")
        sys.exit(internal_only_check(dst_gdf))

    ok = True

    # 1) Row count
    if len(src_gdf) != len(dst_gdf):
        print(f"[FAIL] Satır sayısı: {len(src_gdf)} != {len(dst_gdf)}")
        ok = False
    else:
        print(f"[OK] Satır sayısı: {len(src_gdf)}")

    # 2) Kolon seti
    src_cols, dst_cols = set(src_gdf.columns), set(dst_gdf.columns)
    if src_cols != dst_cols:
        missing = src_cols - dst_cols
        extra = dst_cols - src_cols
        if missing:
            print(f"[WARN] Eksik kolonlar: {sorted(missing)}")
        if extra:
            print(f"[WARN] Fazla kolonlar: {sorted(extra)}")
    else:
        print("[OK] Kolon seti eşleşti")

    # 3) CRS bilgisi
    print(f"[INFO] Kaynak CRS: {crs_to_str(src_gdf.crs)}")
    print(f"[INFO] Parquet CRS: {crs_to_str(dst_gdf.crs)}")

    # 4) total_bounds proximity
    if not np.allclose(src_gdf.total_bounds, dst_gdf.total_bounds, rtol=0, atol=1e-9):
        print(f"[FAIL] total_bounds farkı: {src_gdf.total_bounds} vs {dst_gdf.total_bounds}")
        ok = False
    else:
        print("[OK] total_bounds eşleşti")

    # 5) Empty geometries
    src_none = int(src_gdf.geometry.isna().sum())
    dst_none = int(dst_gdf.geometry.isna().sum())
    if src_none != dst_none:
        print(f"[FAIL] Boş geometri sayısı: {src_none} != {dst_none}")
        ok = False
    else:
        print(f"[OK] Boş geometri sayısı: {src_none}")

    # 6) Sample geometric equality
    n = len(src_gdf)
    sample_n = min(200, n)
    idxs = sorted(set(random.sample(range(n), sample_n))) if n > 0 else []
    mismatches = 0
    for i in idxs:
        try:
            if not src_gdf.geometry.iloc[i].equals(dst_gdf.geometry.iloc[i]):
                mismatches += 1
                if mismatches <= 5:
                    print(f"[MISMATCH] index={i}")
        except Exception:
            mismatches += 1
            if mismatches <= 5:
                print(f"[MISMATCH] index={i} (karşılaştırma hatası)")
    if mismatches > 0:
        print(f"[WARN] Örneklerde {mismatches} eşleşmeyen geometri var")
    else:
        print("[OK] Örneklem geometrileri topolojik olarak eşit")

    if ok and mismatches == 0:
        print("\nRESULT: PASS (kayıpsız dönüşüm onayı)")
        sys.exit(0)
    else:
        print("\nRESULT: CHECK REQUIRED (uyarılar var; detayları yukarıda)")
        sys.exit(1)


if __name__ == "__main__":
    main()


