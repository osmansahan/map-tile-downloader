import os
import sys
import pytest

# Add project src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from geocoordinate.api import CoordinateAPI


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'geocoordinate_data')


def _has_province_data():
    return (
        os.path.exists(os.path.join(DATA_DIR, 'provinces.parquet')) or
        os.path.exists(os.path.join(DATA_DIR, 'provinces_original.geojson'))
    )


def _has_district_data():
    return (
        os.path.exists(os.path.join(DATA_DIR, 'districts.parquet')) or
        os.path.exists(os.path.join(DATA_DIR, 'districts_original.geojson'))
    )


def _has_country_data():
    return (
        os.path.exists(os.path.join(DATA_DIR, 'countries.parquet')) or
        os.path.exists(os.path.join(DATA_DIR, 'countries.fgb')) or
        os.path.exists(os.path.join(DATA_DIR, 'countries_original_merged.geojson'))
    )


@pytest.mark.skipif(not _has_province_data(), reason="province data not available")
def test_ankara_province():
    api = CoordinateAPI(DATA_DIR)
    res = api.find_coordinates('Ankara', 'province')
    assert res.get('success') is True
    assert 'Ankara' in res['found_regions']
    coords = res['coordinates']
    assert 'center' in coords and 'bounding_box' in coords and 'polygon' in coords
    assert coords['bounding_box']['bounds']['min_lon'] < coords['bounding_box']['bounds']['max_lon']


@pytest.mark.skipif(not _has_district_data(), reason="district data not available")
def test_cankaya_district():
    api = CoordinateAPI(DATA_DIR)
    res = api.find_coordinates('Cankaya', 'district')
    assert res.get('success') is True
    assert any('Cankaya' in r or 'Çankaya' in r for r in res['found_regions'])


@pytest.mark.skipif(not _has_province_data(), reason="province data not available")
def test_multiple_provinces_union():
    api = CoordinateAPI(DATA_DIR)
    res = api.find_coordinates('Ankara, Istanbul', 'province')
    assert res.get('success') is True
    assert set(res['found_regions']) & {'Ankara', 'Istanbul', 'İstanbul'}
    coords = res['coordinates']
    assert 'is_contiguous' in coords


@pytest.mark.skipif(not _has_country_data(), reason="country data not available")
def test_country_germany():
    api = CoordinateAPI(DATA_DIR)
    res = api.find_coordinates('Germany', 'country')
    assert res.get('success') is True
    assert any('Germany' in r for r in res['found_regions'])


@pytest.mark.skipif(not _has_province_data(), reason="province data not available")
def test_search_suggestions():
    api = CoordinateAPI(DATA_DIR)
    sugs = api.search_suggestions('an', 5)
    assert isinstance(sugs, list)
    assert len(sugs) <= 5


@pytest.mark.skipif(not _has_province_data(), reason="province data not available")
def test_performance_info_and_lists():
    api = CoordinateAPI(DATA_DIR)
    perf = api.get_performance_info()
    assert 'data_info' in perf
    lst = api.get_region_list('province', 'tr')
    assert isinstance(lst, list)
    assert len(lst) >= 1


@pytest.mark.skipif(not _has_province_data(), reason="province data not available")
def test_health_check_and_errors():
    api = CoordinateAPI(DATA_DIR)
    health = api.health_check()
    assert health.get('status') in ('healthy', 'unhealthy')

    res = api.find_coordinates('NonExistentRegion', 'province')
    assert res.get('success') is False
    assert 'error' in res


