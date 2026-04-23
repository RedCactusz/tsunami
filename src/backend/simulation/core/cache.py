"""
cache.py — Cache builders untuk shapefile dan data geospasial
Membangun cache dari shapefile TES, Desa, dan Jalan pada startup.
"""

import os
import asyncio
from typing import Optional
from pathlib import Path

from .spatial_utils import shp_to_geojson


def build_road_cache(vektor_dir: str) -> Optional[dict]:
    """
    Scan vektor_dir untuk shapefile jalan, konversi ke GeoJSON,
    lalu parse ke list road dicts siap pakai.
    """
    ROAD_KEYWORDS = [
        'jalan', 'road', 'street', 'way', 'jaringan',
        'transport', 'line', 'ruas', 'jalur', 'ln_',
    ]
    SPEED_MAP = {
        'primary': 60, 'secondary': 50, 'tertiary': 40,
        'residential': 30, 'unclassified': 25, 'service': 20,
        'track': 15, 'path': 8, 'footway': 5,
    }

    for root, _, files in os.walk(vektor_dir):
        for fn in sorted(files):
            if not fn.lower().endswith('.shp'):
                continue
            if not any(k in fn.lower() for k in ROAD_KEYWORDS):
                continue

            shp_path = os.path.join(root, fn)
            print(f"\n🛣  Konversi shapefile jalan ke cache: {fn}")
            try:
                gj = shp_to_geojson(shp_path, simplify=False)
                if not gj or not gj.get('features'):
                    print(f"  ⚠ {fn}: kosong, skip")
                    continue

                roads = []
                for feat in gj['features']:
                    props = feat.get('properties', {}) or {}
                    geom = feat.get('geometry', {})
                    
                    # Nama jalan
                    name = props.get('NAMRJL') or props.get('NAMA') or f"Road-{len(roads)+1}"
                    
                    # Kecepatan default
                    speed = SPEED_MAP.get(props.get('FCLASS', 'unclassified'), 25)
                    
                    roads.append({
                        "name": name,
                        "speed_kmh": speed,
                        "geometry": geom,
                        "props": {k: v for k, v in list(props.items())[:10]},
                    })

                if not roads:
                    print(f"  ⚠ {fn}: tidak ada jalan valid")
                    continue

                print(f"  ✅ {fn}: {len(roads)} jalan di-cache")
                return {
                    "geojson": gj,
                    "roads": roads,
                    "source_file": fn,
                    "feature_count": len(roads),
                }
            except Exception as e:
                print(f"  ✗ Error konversi jalan {fn}: {e}")

    print("  ⚠ Tidak ada shapefile jalan ditemukan")
    return None


def build_desa_cache(vektor_dir: str) -> Optional[dict]:
    """Scan dan cache data administrasi desa dari shapefile."""
    DESA_KEYWORDS = ['admin', 'desa', 'kelurahan', 'village', 'kecamatan', 'district']

    for root, _, files in os.walk(vektor_dir):
        for fn in sorted(files):
            if not fn.lower().endswith('.shp'):
                continue
            if not any(k in fn.lower() for k in DESA_KEYWORDS):
                continue

            shp_path = os.path.join(root, fn)
            print(f"\n🏘  Konversi shapefile desa ke cache: {fn}")
            try:
                gj = shp_to_geojson(shp_path, simplify=False)
                if not gj or not gj.get('features'):
                    print(f"  ⚠ {fn}: kosong, skip")
                    continue

                desa_list = []
                for feat in gj['features']:
                    props = feat.get('properties', {}) or {}
                    geom = feat.get('geometry', {})

                    # Nama desa
                    name = ""
                    for fld in ['NAMA', 'nama', 'NAME', 'name', 'DESA', 'desa']:
                        v = props.get(fld)
                        if v and str(v).strip() not in ('', 'None'):
                            name = str(v).strip()
                            break
                    if not name:
                        name = f"Desa-{len(desa_list)+1}"

                    # Koordinat dari centroid
                    lat_c = lon_c = None
                    try:
                        if geom['type'] == 'Point':
                            lon_c, lat_c = geom['coordinates']
                        elif geom['type'] == 'Polygon':
                            cs = geom['coordinates'][0]
                            lon_c = sum(c[0] for c in cs) / len(cs)
                            lat_c = sum(c[1] for c in cs) / len(cs)
                        elif geom['type'] == 'MultiPolygon':
                            all_coords = []
                            for poly in geom['coordinates']:
                                all_coords.extend(poly[0])
                            lon_c = sum(c[0] for c in all_coords) / len(all_coords)
                            lat_c = sum(c[1] for c in all_coords) / len(all_coords)
                    except:
                        pass

                    desa_list.append({
                        "name": name,
                        "lat": round(lat_c, 6) if lat_c else None,
                        "lon": round(lon_c, 6) if lon_c else None,
                        "props": {k: v for k, v in list(props.items())[:10]},
                    })

                if not desa_list:
                    print(f"  ⚠ {fn}: tidak ada desa valid")
                    continue

                print(f"  ✅ {fn}: {len(desa_list)} desa di-cache")
                return {
                    "geojson": gj,
                    "desa": desa_list,
                    "source_file": fn,
                    "count": len(desa_list),
                }
            except Exception as e:
                print(f"  ✗ Error konversi desa {fn}: {e}")

    print("  ⚠ Tidak ada shapefile desa ditemukan")
    return None


def build_tes_cache(vektor_dir: str) -> Optional[dict]:
    """Scan dan cache data Titik Evakuasi Sementara dari shapefile."""
    TES_KEYWORDS = ['tes', 'evakuasi', 'shelter', 'pengungsian', 'koordinat_tes']

    for root, _, files in os.walk(vektor_dir):
        for fn in sorted(files):
            if not fn.lower().endswith('.shp'):
                continue
            if not any(k in fn.lower() for k in TES_KEYWORDS):
                continue

            shp_path = os.path.join(root, fn)
            print(f"\n🏕  Konversi shapefile TES ke cache: {fn}")
            try:
                gj = shp_to_geojson(shp_path, simplify=False)
                if not gj or not gj.get('features'):
                    print(f"  ⚠ {fn}: kosong, skip")
                    continue

                tes_list = []
                for feat in gj['features']:
                    props = feat.get('properties', {}) or {}
                    geom = feat.get('geometry', {})

                    # Nama TES
                    name = ""
                    for fld in ['NAMA','nama','NAME','name','TES','tes',
                                'LOKASI','lokasi','TEMPAT','tempat']:
                        v = props.get(fld)
                        if v and str(v).strip() not in ('', 'None'):
                            name = str(v).strip()
                            break
                    if not name:
                        name = f"TES-{len(tes_list)+1:02d}"

                    # Kapasitas
                    kapasitas = 500
                    for fld in ['KAPASITAS','kapasitas','CAP','cap','CAPACITY']:
                        try:
                            v = props.get(fld)
                            if v:
                                kapasitas = int(float(str(v)))
                                break
                        except:
                            pass

                    # Koordinat
                    lat_c = lon_c = None
                    try:
                        if geom['type'] == 'Point':
                            lon_c, lat_c = geom['coordinates']
                        elif geom['type'] == 'Polygon':
                            cs = geom['coordinates'][0]
                            lon_c = sum(c[0] for c in cs) / len(cs)
                            lat_c = sum(c[1] for c in cs) / len(cs)
                        elif geom['type'] == 'MultiPoint':
                            lon_c, lat_c = geom['coordinates'][0]
                    except:
                        pass

                    tes_list.append({
                        "name": name,
                        "kapasitas": kapasitas,
                        "lat": round(lat_c, 6) if lat_c else None,
                        "lon": round(lon_c, 6) if lon_c else None,
                        "props": {k: v for k, v in list(props.items())[:10]},
                    })

                if not tes_list:
                    print(f"  ⚠ {fn}: tidak ada TES valid")
                    continue

                print(f"  ✅ {fn}: {len(tes_list)} TES di-cache")
                return {
                    "geojson": gj,
                    "tes": tes_list,
                    "source_file": fn,
                    "count": len(tes_list),
                }
            except Exception as e:
                print(f"  ✗ Error konversi TES {fn}: {e}")

    print("  ⚠ Tidak ada shapefile TES ditemukan")
    return None
