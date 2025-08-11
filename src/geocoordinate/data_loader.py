import geopandas as gpd
import json
import os
from pathlib import Path
from typing import Dict
from .interfaces import IDataLoader

class GeoJSONDataLoader(IDataLoader):
    """GeoJSON data loader with lazy loading"""
    
    def __init__(self, data_dir: str = "geocoordinate_data"):
        self.data_dir = Path(data_dir)
        self._provinces = None
        self._districts = None
        self._countries = None
        self._metadata = None
        self._countries_index_cache = None
    
    def load_provinces(self) -> gpd.GeoDataFrame:
        """Load province data (lazy loading)"""
        if self._provinces is None:
            try:
                # Prefer Parquet if available for faster IO
                pq = self.data_dir / "provinces.parquet"
                if pq.exists():
                    self._provinces = gpd.read_parquet(pq)
                else:
                    self._provinces = gpd.read_file(self.data_dir / "provinces_original.geojson")
            except Exception as e:
                raise Exception(f"Failed to load province data: {e}")
        return self._provinces
    
    def load_districts(self) -> gpd.GeoDataFrame:
        """Load district data (lazy loading)"""
        if self._districts is None:
            try:
                # Prefer Parquet if available for faster IO
                pq = self.data_dir / "districts.parquet"
                if pq.exists():
                    self._districts = gpd.read_parquet(pq)
                else:
                    self._districts = gpd.read_file(self.data_dir / "districts_original.geojson")
            except Exception as e:
                raise Exception(f"Failed to load district data: {e}")
        return self._districts
    
    def load_countries(self) -> gpd.GeoDataFrame:
        """Load country data (lazy loading)"""
        if self._countries is None:
            try:
                # Prefer Parquet, then FlatGeobuf, else GeoJSON
                pq = self.data_dir / "countries.parquet"
                fgb = self.data_dir / "countries.fgb"
                if pq.exists():
                    gdf = gpd.read_parquet(pq)
                elif fgb.exists():
                    gdf = gpd.read_file(fgb)
                else:
                    src = self.data_dir / "countries_original_merged.geojson"
                    if not src.exists():
                        raise Exception(f"Ülke verisi bulunamadı: {src}")
                    gdf = gpd.read_file(src)

                # Normalize country name column to adm0_name
                name_candidates = [
                    "adm0_name", "ADMIN", "ADM0_NAME", "NAME_ENGLI", "NAME_EN", "NAME", "name_en"
                ]
                name_col = next((c for c in name_candidates if c in gdf.columns), None)
                if not name_col:
                    raise Exception(f"Ülke adı kolonu bulunamadı. Kolonlar: {list(gdf.columns)}")
                if name_col != "adm0_name":
                    gdf = gdf.rename(columns={name_col: "adm0_name"})

                # CRS handling: if not CRS84/EPSG:4326, convert; if missing, set CRS84
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
                        crs_str = crs_obj.to_string().upper()
                    except Exception:
                        crs_str = str(crs_obj).upper() if crs_obj else ""
                    try:
                        epsg = crs_obj.to_epsg()
                    except Exception:
                        epsg = None
                    if not (epsg == 4326 or crs_str == "OGC:CRS84"):
                        try:
                            gdf = gdf.to_crs(4326)
                        except Exception:
                            pass

                # Keep only necessary columns
                keep = [c for c in ["adm0_name"] if c in gdf.columns]
                self._countries = gdf[keep + ["geometry"]]
                
            except Exception as e:
                raise Exception(f"Failed to load country data: {e}")
                
        return self._countries

    def load_countries_index(self) -> Dict:
        """Load countries search index strictly from metadata."""
        if self._countries_index_cache is not None:
            return self._countries_index_cache
        metadata = self.load_metadata()
        idx = metadata.get("search_indexes", {}).get("countries", {})
        self._countries_index_cache = idx if isinstance(idx, dict) else {}
        return self._countries_index_cache
    
    def load_metadata(self) -> Dict:
        """Load metadata (lazy loading)"""
        if self._metadata is None:
            try:
                with open(self.data_dir / "metadata_original.json", 'r', encoding='utf-8') as f:
                    self._metadata = json.load(f)
            except Exception as e:
                raise Exception(f"Failed to load metadata: {e}")
        return self._metadata
    
    def get_data_info(self) -> Dict:
        """Get data information"""
        provinces = self.load_provinces()
        districts = self.load_districts()
        countries = self.load_countries()
        
        def _size_mb(p: Path) -> float:
            try:
                return p.stat().st_size / (1024 * 1024)
            except Exception:
                return 0.0

        return {
            "provinces_count": len(provinces),
            "districts_count": len(districts),
            "countries_count": len(countries),
            "provinces_size_mb": _size_mb(self.data_dir / "provinces_original.geojson"),
            "districts_size_mb": _size_mb(self.data_dir / "districts_original.geojson"),
            "countries_size_mb": _size_mb(self.data_dir / "countries_original_merged.geojson"),
            "countries_index_source": "metadata"
        }