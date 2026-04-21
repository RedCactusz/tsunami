"""
evacuation_abm.py — Modul Analisis Rute Evakuasi + ABM Tsunami
===============================================================
Implementasi penuh 5-langkah sesuai Diagram Alir Evakuasi ABM:

  Proses 1 — Ekstraksi Node Jalan
              Ekstrak node persimpangan jalan yang berada di area genangan
              tsunami (inundation zone). Input: Jaringan Jalan (GeoJSON) +
              Data Genangan Tsunami (GeoJSON).

  Proses 2 — Network Analysis: Fastest Path
              Hitung rute tercepat dari setiap node tergenang ke TES
              menggunakan Dijkstra / A* dengan bobot waktu (fastest path).
              Output: Fastest Path per node asal.

  Proses 3 — Ekstraksi Data Jumlah Penduduk (Titik Asal Agen)
              Dasymetric mapping: populasi total per kelurahan didistribusikan
              proporsional ke setiap bangunan (centroid bangunan dari OSM API).
              Building Footprint → OSM Overpass API (dengan fallback centroid desa).
              Output: Titik Asal Agen (centroid bangunan + jumlah agen).

  Proses 4 — Pemodelan ABM untuk Simulasi Pergerakan Evakuasi
              Setiap agen bergerak time-step mengikuti fastest path ke TES.
              Kecepatan dasar: 1.38 m/s (pejalan kaki) = 4.97 km/h.
              Faktor: kemacetan, wave arrival time dari SWE.
              Output: posisi agen setiap waktu + status
              (waiting | moving | arrived | stranded).

  Proses 5 — Evaluasi Jalur dan Optimasi (Pengujian Lokasi TES)
              Cek kapasitas TES saat agen tiba. Jika penuh → cari TES
              alternatif terdekat → hitung ulang fastest path → lanjut.
              Simulasi berakhir saat tsunami tiba atau semua agen mendapat TES.
              Output: Jalur Optimal + Estimasi Agen Selamat & Terdampak.

Integrasi:
  - DEMManager dioper dari server (tidak dibaca ulang)
  - SWE results (opsional) untuk blokir rute tergenang + wave arrival time
  - Building Footprint dari OSM Overpass API (opsional, dengan timeout)

Cara pakai di server:
  from evacuation_abm import EvacuationABMSolver, build_graph

  solver = EvacuationABMSolver(vektor_dir=VEKTOR_DIR, dem_mgr=dem_manager)
  solver.build_caches()
  solver.set_swe_results(swe_output)

  result = solver.compute_route(origin, destination, method, transport, weight, roads)
  result = solver.run_abm(body_dict)
"""

import os, math, heapq, random, json, time
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

try:
    import urllib.request as _urlreq
    import urllib.parse   as _urlparse
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

try:
    import geopandas as gpd
    USE_GPD = True
except ImportError:
    USE_GPD = False
    print("  geopandas tidak ada — konversi SHP tidak tersedia")

try:
    from shapely.geometry import shape as _sh
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


# ═══════════════════════════════════════════════════════════════
# PARAMETER DIMENSI AGEN & KAPASITAS JARINGAN
# Referensi: Muhammad et al. (2021), Lämmel et al. (2009),
#            Weidmann (1993) — Fundamental diagram pejalan kaki
# ═══════════════════════════════════════════════════════════════

# ── Kecepatan agen (m/s dan km/h) ─────────────────────────────
# Jurnal (Muhammad 2021): pedestrian 1.66 m/s, motorbike 5.66 m/s
# Diagram alir Bantul   : pedestrian 1.38 m/s (spesifikasi proyek)
# → Digunakan nilai diagram alir untuk pedestrian (1.38 m/s = 4.97 km/h)
#   karena sesuai target proyek, motor/car tetap dari jurnal.
SPEED_DEFAULTS = {
    "foot":  4.97,    # 1.38 m/s = 4.97 km/h  (pejalan kaki, evakuasi massal)
    "motor": 20.376,  # 5.66 m/s = 20.376 km/h (motor, Muhammad et al. 2021)
    "car":   15.0,    # 4.17 m/s = 15.0 km/h   (mobil, kecepatan evakuasi terbatas)
}

# ── Dimensi fisik agen (m²/orang) ─────────────────────────────
# Referensi: Lämmel et al. (2009), Muhammad et al. (2021), Weidmann (1993)
AGENT_AREA_M2 = {
    "foot":  0.5,    # ~0.5 m²/orang (ruang personal pejalan kaki)
    "motor": 3.0,    # ~3 m²/motor   (panjang ~2m × lebar ~1m + jarak)
    "car":   9.0,    # ~9 m²/mobil   (panjang 4.5m × lebar 2m, dimensi kendaraan)
}

# ── Dimensi kendaraan (panjang × lebar, meter) ────────────────
# Referensi: Muhammad et al. (2021) motorbike 3m × 1m
#            Tambahan: mobil standar 4.5m × 2m
VEHICLE_DIM_M = {
    "foot":  (0.5, 0.5),   # lingkar tubuh pejalan kaki
    "motor": (2.0, 1.0),   # panjang × lebar motor (Hoppe & Mahardiko 2010)
    "car":   (4.5, 2.0),   # panjang × lebar mobil (standar kendaraan)
}

# ── Densitas maksimum di jaringan jalan (Dmax) ─────────────────
# Referensi: Lämmel et al. (2009), Muhammad et al. (2021)
# Dmax pejalan kaki : 5.4 orang/m²  (Weidmann 1993 fundamental diagram)
# Dmax motor        : 0.4 motor/m²  (Lämmel et al. 2009)
# Dmax mobil        : ~0.11 mobil/m² (estimasi: 1/AGENT_AREA = 1/9)
DMAX_PER_M2 = {
    "foot":  5.4,    # orang/m²    (Weidmann 1993)
    "motor": 0.4,    # motor/m²    (Lämmel et al. 2009)
    "car":   0.11,   # mobil/m²    (estimasi 1/9 m² per mobil)
}

# ── Flow Capacity maksimum (FC) per unit lebar jalan ─────────────
# FC = w × Cmax  (Muhammad et al. 2021, Eq. 1)
# Referensi: Lämmel et al. (2009), Weidmann (1993)
# Pejalan kaki : 1.3 orang/m/s  (Weidmann 1993 fundamental diagram)
# Motor        : ~4.0 orang/m/s (Lämmel 2009; ~3× lebih cepat dari pejalan kaki)
# Mobil        : ~0.5 orang/m/s (estimasi, kecepatan terbatas di jalur evakuasi)
FLOW_CAPACITY_PER_M_PER_S = {
    "foot":  1.3,    # orang/m/s   (Weidmann 1993)
    "motor": 4.0,    # orang/m/s   (Lämmel et al. 2009)
    "car":   0.5,    # orang/m/s   (estimasi kendaraan roda empat)
}

# ── Storage Capacity (SC) per link — threshold kemacetan ─────────
# SC = A × Dmax  (Muhammad et al. 2021, Eq. 2)
# Kapasitas TES threshold (jumlah agen maks di evacuation link):
#   Pejalan kaki : 200 orang  (Lämmel 2009; ~6× lebih besar dari motor)
#   Motor        : 30  motor  (Lämmel 2009; queue 10 baris × 3 motor)
#   Mobil        : 10  mobil  (estimasi; ruang lebih besar per unit)
TES_LINK_CAPACITY = {
    "foot":  200,   # orang     (Muhammad et al. 2021)
    "motor": 30,    # motor     (Muhammad et al. 2021)
    "car":   10,    # mobil     (estimasi)
}

# ── Lebar jalan standar (meter per lajur) ───────────────────────
# Referensi: Muhammad et al. (2021), Hoppe & Mahardiko (2010)
# Jalan utama Bantul: lebar 6m → 2 lajur × 3m per lajur
ROAD_WIDTH_DEFAULT_M = 3.0   # meter per lajur (Muhammad et al. 2021)

# ── Kecepatan pejalan kaki berdasarkan slope (Tobler's Hiking Function)
# Referensi: Tobler (1993), dipakai oleh Muhammad et al. (2021)
# v = 6 × exp(-3.5 × |tan(slope) + 0.05|) km/h  (Tobler 1993)
# Digunakan untuk menyesuaikan kecepatan pejalan kaki di terrain berlereng
def tobler_speed_kmh(slope_deg: float, base_speed_kmh: float = 4.97) -> float:
    """
    Hitung kecepatan pejalan kaki berdasarkan Tobler's Hiking Function.
    Referensi: Tobler (1993); digunakan dalam Muhammad et al. (2021).

    Parameters
    ----------
    slope_deg      : kemiringan dalam derajat (positif = naik, negatif = turun)
    base_speed_kmh : kecepatan dasar di terrain datar (default: 4.97 km/h = 1.38 m/s)

    Return: kecepatan terkoreksi (km/h), tidak melebihi base_speed_kmh × 1.1
    """
    import math
    tan_slope = math.tan(math.radians(slope_deg))
    # Tobler: v = 6 × exp(-3.5 × |tan(α) + 0.05|)  km/h (untuk kondisi normal)
    # Normalisasi terhadap kecepatan optimal (α ≈ -2.86° → ~6 km/h di Tobler)
    v_tobler = 6.0 * math.exp(-3.5 * abs(tan_slope + 0.05))
    # v_flat di Tobler (α = 0): 6 × exp(-3.5 × 0.05) ≈ 5.08 km/h
    v_flat_tobler = 6.0 * math.exp(-3.5 * 0.05)
    # Skala ke kecepatan dasar proyek
    ratio = v_tobler / max(v_flat_tobler, 1e-6)
    return min(base_speed_kmh * ratio, base_speed_kmh * 1.1)


def flow_capacity_link(road_width_m: float, transport: str) -> float:
    """
    Hitung Flow Capacity (FC) sebuah link jalan.
    FC = w × Cmax  (Muhammad et al. 2021, Eq. 1)

    Parameters
    ----------
    road_width_m : lebar lajur jalan (meter)
    transport    : 'foot' | 'motor' | 'car'

    Return: flow capacity (orang atau kendaraan per detik)
    """
    cmax = FLOW_CAPACITY_PER_M_PER_S.get(transport, 1.3)
    return road_width_m * cmax


def storage_capacity_link(road_length_m: float, road_width_m: float,
                           transport: str) -> float:
    """
    Hitung Storage Capacity (SC) sebuah link jalan.
    SC = A × Dmax  (Muhammad et al. 2021, Eq. 2)

    Parameters
    ----------
    road_length_m : panjang segmen jalan (meter)
    road_width_m  : lebar lajur jalan (meter)
    transport     : 'foot' | 'motor' | 'car'

    Return: storage capacity (orang atau kendaraan)
    """
    area = road_length_m * road_width_m
    dmax = DMAX_PER_M2.get(transport, 5.4)
    return area * dmax


def congestion_factor(agent_count: int, link_capacity: float) -> float:
    """
    Faktor kemacetan berdasarkan rasio kepadatan terhadap kapasitas link.
    Jika agent_count mendekati atau melebihi link_capacity → kecepatan turun.

    Return: faktor pengali kecepatan [0.1 – 1.0]
    """
    if link_capacity <= 0:
        return 1.0
    ratio = agent_count / link_capacity
    if ratio <= 0.5:
        return 1.0                        # bebas hambatan
    elif ratio <= 1.0:
        return 1.0 - 0.6 * (ratio - 0.5) / 0.5   # degradasi bertahap
    else:
        return 0.1                        # kemacetan penuh → hampir berhenti

SPEED_MAP = {
    "primary": 60, "secondary": 50, "tertiary": 40,
    "residential": 30, "unclassified": 25, "service": 20,
    "track": 15, "path": 8, "footway": 5,
}

ROAD_KEYWORDS = [
    "jalan", "road", "street", "way", "jaringan",
    "transport", "line", "ruas", "jalur", "ln_",
]

DESA_KEYWORDS = [
    "administrasi_desa", "desa", "kelurahan", "kel_", "village",
    "admin", "kecamatan", "adm", "penduduk",
]

TES_KEYWORDS = [
    "tes_", "tes_bantul", "koordinat_tes", "evakuasi", "shelter",
    "titik_kumpul", "assembly", "pengungsian",
]


# ═══════════════════════════════════════════════════════════════
# HELPER GEOMETRI
# ═══════════════════════════════════════════════════════════════

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Hitung jarak haversine antara dua titik koordinat (meter)."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _point_in_ring(lat: float, lon: float, ring: list) -> bool:
    """Ray-casting: cek titik dalam ring GeoJSON [lon, lat]."""
    n, inside, j = len(ring), False, len(ring) - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
           (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def point_in_geom(lat: float, lon: float, geom: dict) -> bool:
    """Cek apakah titik (lat, lon) berada di dalam geometry GeoJSON."""
    try:
        gt = geom.get("type", "")
        if gt == "Polygon":
            return _point_in_ring(lat, lon, geom["coordinates"][0])
        elif gt == "MultiPolygon":
            return any(_point_in_ring(lat, lon, p[0]) for p in geom["coordinates"])
    except Exception:
        pass
    return False


def path_dist_m(path: list) -> float:
    """Hitung total jarak path [(lat, lon), ...] dalam meter."""
    return sum(
        haversine_m(path[i][0], path[i][1], path[i+1][0], path[i+1][1])
        for i in range(len(path) - 1)
    )


# ═══════════════════════════════════════════════════════════════
# SHAPEFILE → GEOJSON CONVERTER
# ═══════════════════════════════════════════════════════════════

def shp_to_geojson(shp_path: str, simplify: bool = True, max_pts: int = 400) -> Optional[dict]:
    """Konversi shapefile ke GeoJSON WGS84. Membutuhkan geopandas."""
    if not USE_GPD:
        return None
    try:
        gdf = gpd.read_file(shp_path)
        if gdf is None or gdf.empty:
            return None
        if hasattr(gdf, "crs") and gdf.crs is not None:
            try:
                if gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs("EPSG:4326")
            except Exception:
                pass
        bbox = [round(x, 5) for x in list(gdf.total_bounds)]
        return {"features": json.loads(gdf.to_json())["features"], "bbox": bbox}
    except Exception as e:
        print(f"  [FAIL] Gagal membaca {shp_path}: {e}")
        return None


def get_valid_land_point(poly, dem_mgr=None) -> Tuple[float, float]:
    """Temukan titik di dalam polygon yang berada di darat."""
    try:
        c = poly.centroid
        if dem_mgr:
            elev, _ = dem_mgr.query(c.x, c.y)
            if elev is not None and elev > 0:
                return c.x, c.y
        else:
            return c.x, c.y
        rp = poly.representative_point()
        return rp.x, rp.y
    except Exception:
        try:
            return poly.centroid.x, poly.centroid.y
        except Exception:
            return 0.0, 0.0


# ═══════════════════════════════════════════════════════════════
# CACHE BUILDER: JALAN, DESA, TES
# ═══════════════════════════════════════════════════════════════

def _build_road_cache(vektor_dir: str) -> Optional[dict]:
    """
    Scan vektor_dir untuk shapefile jalan → GeoJSON + road dicts.
    Return: {geojson, roads, source_file, feature_count, bbox} atau None.
    """
    for root, _, files in os.walk(vektor_dir):
        for fn in sorted(files):
            fn_lower = fn.lower()
            if not fn_lower.endswith(".shp"):
                continue
            if not any(k in fn_lower for k in ROAD_KEYWORDS):
                continue
            shp_path = os.path.join(root, fn)
            print(f"\n[INFO] Konversi shapefile jalan: {fn}")
            try:
                gj = shp_to_geojson(shp_path, simplify=False, max_pts=50000)
                if not gj or not gj.get("features"):
                    continue
                line_feats = [f for f in gj["features"]
                              if f.get("geometry", {}).get("type", "") in
                              ("LineString", "MultiLineString")]
                if not line_feats:
                    continue
                gj["features"] = line_feats
                roads = []
                for feat in line_feats:
                    props = feat.get("properties", {}) or {}
                    geom  = feat.get("geometry", {})
                    if not geom:
                        continue
                    hw = (props.get("highway") or props.get("HIGHWAY") or
                          props.get("jenis")   or props.get("JENIS")   or
                          props.get("REMARK")  or props.get("fclass")  or
                          props.get("type")    or "residential")
                    hw = str(hw).lower().strip()
                    name   = (props.get("name") or props.get("NAMA") or
                              props.get("nama")  or props.get("NAME") or "")
                    oneway = str(props.get("oneway", "no")).lower() in ("yes", "1", "true")
                    coords = []
                    if geom["type"] == "LineString":
                        coords = [[c[1], c[0]] for c in geom["coordinates"]]
                    elif geom["type"] == "MultiLineString":
                        for seg in geom["coordinates"]:
                            coords += [[c[1], c[0]] for c in seg]
                    if len(coords) < 2:
                        continue
                    roads.append({
                        "id":        props.get("osm_id") or props.get("ID") or id(feat),
                        "highway":   hw,
                        "name":      name,
                        "oneway":    "yes" if oneway else "no",
                        "speed_kmh": SPEED_MAP.get(hw, 25),
                        "capacity":  int(props.get("lanes", 1) or 1) * 1000,
                        "coords":    coords,
                    })
                if not roads:
                    continue
                all_lons = [c[1] for r in roads for c in r["coords"]]
                all_lats = [c[0] for r in roads for c in r["coords"]]
                bbox = [round(min(all_lons), 5), round(min(all_lats), 5),
                        round(max(all_lons), 5), round(max(all_lats), 5)]
                print(f"  [OK] {fn}: {len(line_feats)} fitur → {len(roads)} road dicts")
                return {"geojson": gj, "roads": roads, "source_file": fn,
                        "feature_count": len(line_feats), "bbox": bbox}
            except Exception as e:
                print(f"  [FAIL] {fn}: {e}")
    print("  Tidak ada shapefile jalan ditemukan")
    return None


def _build_desa_cache(vektor_dir: str) -> Optional[dict]:
    """Load shapefile administrasi desa → list desa dicts."""
    for root, _, files in os.walk(vektor_dir):
        for fn in sorted(files):
            fn_lower = fn.lower()
            if not fn_lower.endswith(".shp"):
                continue
            if not any(k in fn_lower for k in DESA_KEYWORDS):
                continue
            shp_path = os.path.join(root, fn)
            print(f"\n[INFO] Konversi shapefile desa: {fn}")
            try:
                gj = shp_to_geojson(shp_path, simplify=True)
                if not gj or not gj.get("features"):
                    continue
                desa_list = []
                for feat in gj["features"]:
                    props = feat.get("properties", {}) or {}
                    geom  = feat.get("geometry", {})
                    name = ""
                    for fld in ["NAMOBJ", "WADMKD", "namobj", "NAMA_OBJ", "nama_obj",
                                "DESA", "desa", "NAMA_DESA", "nama_desa",
                                "KELURAHAN", "kelurahan", "KALURAHAN", "kalurahan",
                                "NAMA", "nama", "NAME", "name", "VILLAGE"]:
                        v = props.get(fld)
                        if v and str(v).strip() not in ("", "None"):
                            name = str(v).strip()
                            break
                    if not name:
                        name = f"Desa-{len(desa_list)+1:03d}"

                    penduduk = 1000
                    for fld in ["Penduduk", "PENDUDUK", "Jumlah_Pen", "JUMLAH_PEN",
                                "Population", "POPULATION", "JIWA", "jiwa",
                                "jumlah", "JUMLAH", "total", "TOTAL", "pop", "POP"]:
                        try:
                            v = props.get(fld)
                            if v:
                                penduduk = max(1, int(float(str(v).replace(",", ""))))
                                break
                        except Exception:
                            pass

                    lat_c = lon_c = None
                    try:
                        if HAS_SHAPELY:
                            s = _sh(geom)
                            lon_c, lat_c = s.centroid.x, s.centroid.y
                        else:
                            gt = geom.get("type", "")
                            if gt == "Polygon":
                                cs = geom["coordinates"][0]
                            elif gt == "MultiPolygon":
                                cs = max((p[0] for p in geom["coordinates"]), key=len)
                            else:
                                cs = geom["coordinates"][0]
                            lon_c = sum(c[0] for c in cs) / len(cs)
                            lat_c = sum(c[1] for c in cs) / len(cs)
                    except Exception:
                        pass

                    if lat_c is None or lon_c is None:
                        continue

                    desa_list.append({
                        "name": name, "penduduk": penduduk,
                        "lat": round(lat_c, 6), "lon": round(lon_c, 6),
                        "geom": geom,
                        "props": {k: v for k, v in list(props.items())[:10]},
                    })
                if not desa_list:
                    continue
                print(f"  [OK] {fn}: {len(desa_list)} desa")
                return {"geojson": gj, "desa": desa_list,
                        "source_file": fn, "count": len(desa_list)}
            except Exception as e:
                print(f"  [FAIL] {fn}: {e}")
    print("  [WARN] Tidak ada shapefile desa ditemukan")
    return None


def _build_tes_cache(vektor_dir: str) -> Optional[dict]:
    """Load shapefile TES → list tes dicts."""
    for root, _, files in os.walk(vektor_dir):
        for fn in sorted(files):
            fn_lower = fn.lower()
            if not fn_lower.endswith(".shp"):
                continue
            if not any(k in fn_lower for k in TES_KEYWORDS):
                continue
            shp_path = os.path.join(root, fn)
            print(f"\n[INFO] Konversi shapefile TES: {fn}")
            try:
                gj = shp_to_geojson(shp_path, simplify=False)
                if not gj or not gj.get("features"):
                    continue
                tes_list = []
                for feat in gj["features"]:
                    props = feat.get("properties", {}) or {}
                    geom  = feat.get("geometry", {})
                    name = ""
                    for fld in ["NAMA", "nama", "NAME", "name", "TES", "tes",
                                "LOKASI", "lokasi", "TEMPAT", "tempat"]:
                        v = props.get(fld)
                        if v and str(v).strip() not in ("", "None"):
                            name = str(v).strip()
                            break
                    if not name:
                        name = f"TES-{len(tes_list)+1:02d}"

                    kapasitas = 500
                    for fld in ["KAPASITAS", "kapasitas", "CAP", "cap",
                                "CAPACITY", "capacity"]:
                        try:
                            v = props.get(fld)
                            if v:
                                kapasitas = max(1, int(float(str(v))))
                                break
                        except Exception:
                            pass

                    lat_c = lon_c = None
                    try:
                        gt = geom.get("type", "")
                        if gt == "Point":
                            lon_c, lat_c = geom["coordinates"][:2]
                        elif gt == "Polygon":
                            cs = geom["coordinates"][0]
                            lon_c = sum(c[0] for c in cs) / len(cs)
                            lat_c = sum(c[1] for c in cs) / len(cs)
                        elif gt == "MultiPoint":
                            lon_c, lat_c = geom["coordinates"][0][:2]
                    except Exception:
                        pass

                    if lat_c is None or lon_c is None:
                        continue

                    tes_list.append({
                        "name": name, "kapasitas": kapasitas,
                        "lat": round(lat_c, 6), "lon": round(lon_c, 6),
                        "props": {k: v for k, v in list(props.items())[:10]},
                    })
                if not tes_list:
                    continue
                print(f"  [OK] {fn}: {len(tes_list)} TES")
                return {"geojson": gj, "tes": tes_list,
                        "source_file": fn, "count": len(tes_list)}
            except Exception as e:
                print(f"  [FAIL] {fn}: {e}")
    print("  [WARN] Tidak ada shapefile TES ditemukan")
    return None


# ═══════════════════════════════════════════════════════════════
# PROSES 3: OSM BUILDING FOOTPRINT → DASYMETRIC MAPPING
# ═══════════════════════════════════════════════════════════════

def fetch_osm_buildings(bbox_str: str, timeout: int = 20) -> List[dict]:
    """
    Ambil Building Footprint dari Overpass API OSM.
    bbox_str: "lat_min,lon_min,lat_max,lon_max"
    Return: list of {lat, lon} centroid bangunan.
    """
    if not HAS_URLLIB:
        return []
    query = (
        f"[out:json][timeout:{timeout}];"
        f"(way[building]({bbox_str});"
        f"relation[building]({bbox_str}););"
        f"out center;"
    )
    try:
        url  = "https://overpass-api.de/api/interpreter"
        data = _urlparse.urlencode({"data": query}).encode()
        req  = _urlreq.Request(url, data=data,
                               headers={"User-Agent": "TsunamiSim-ABM/2.0"})
        with _urlreq.urlopen(req, timeout=timeout + 5) as resp:
            raw = json.loads(resp.read().decode())
        return [
            {"lat": el["center"]["lat"], "lon": el["center"]["lon"]}
            for el in raw.get("elements", [])
            if el.get("center", {}).get("lat")
        ]
    except Exception as e:
        print(f"  [WARN] OSM buildings fetch gagal ({e}) — pakai centroid desa")
        return []


def dasymetric_mapping(desa_list: list,
                        inundation_geom: Optional[dict] = None,
                        osm_timeout: int = 15) -> List[dict]:
    """
    PROSES 3: Distribusi populasi ke centroid bangunan (dasymetric mapping).

    Untuk setiap desa:
      1. Ambil building footprint dari OSM Overpass API
      2. Filter bangunan dalam polygon desa (ray-casting)
      3. Distribusikan penduduk proporsional ke jumlah bangunan
      4. Filter lagi: hanya bangunan dalam zona inundasi (jika tersedia)
      5. Fallback ke centroid desa + jitter jika OSM tidak tersedia

    Return: list of {name, lat, lon, penduduk, desa, source}
    """
    agent_origins = []

    for desa in desa_list:
        dlat  = desa.get("lat")
        dlon  = desa.get("lon")
        pop   = desa.get("penduduk", 1000)
        dname = desa.get("name", "Unknown")
        geom  = desa.get("geom")

        if not dlat or not dlon:
            continue

        # Bounding box desa untuk query OSM
        bbox_osm  = None
        buildings = []

        if geom:
            try:
                coords_flat = []
                gt = geom.get("type", "")
                if gt == "Polygon":
                    coords_flat = geom["coordinates"][0]
                elif gt == "MultiPolygon":
                    for part in geom["coordinates"]:
                        coords_flat.extend(part[0])
                if coords_flat:
                    lats = [c[1] for c in coords_flat]
                    lons = [c[0] for c in coords_flat]
                    lat_min, lat_max = min(lats), max(lats)
                    lon_min, lon_max = min(lons), max(lons)
                    # Hanya query OSM jika area desa cukup kecil
                    if (lat_max - lat_min) < 0.06 and (lon_max - lon_min) < 0.06:
                        bbox_osm = f"{lat_min:.5f},{lon_min:.5f},{lat_max:.5f},{lon_max:.5f}"
            except Exception:
                pass

        if bbox_osm:
            buildings = fetch_osm_buildings(bbox_osm, timeout=osm_timeout)
            # Filter: centroid bangunan dalam polygon desa
            if geom and buildings:
                buildings = [b for b in buildings
                             if point_in_geom(b["lat"], b["lon"], geom)]

        if buildings:
            n_bldg = len(buildings)
            pop_per_bldg = max(1, pop // n_bldg)
            added = 0
            for bldg in buildings:
                # Filter: hanya bangunan dalam zona inundasi
                if inundation_geom and not point_in_geom(bldg["lat"], bldg["lon"],
                                                          inundation_geom):
                    continue
                agent_origins.append({
                    "name":     f"{dname}_bldg",
                    "lat":      bldg["lat"],
                    "lon":      bldg["lon"],
                    "penduduk": pop_per_bldg,
                    "desa":     dname,
                    "source":   "osm_building",
                })
                added += 1
            if added > 0:
                print(f"  [OK] {dname}: {n_bldg} bangunan OSM → {added} titik asal agen")
                continue

        # Fallback: jitter di sekitar centroid desa
        n_pts    = min(5, max(1, pop // 500))
        pop_each = max(1, pop // n_pts)
        for i in range(n_pts):
            jlat = dlat + random.gauss(0, 0.001)
            jlon = dlon + random.gauss(0, 0.001)
            if inundation_geom and not point_in_geom(jlat, jlon, inundation_geom):
                jlat, jlon = dlat, dlon
            agent_origins.append({
                "name":     f"{dname}_c{i}",
                "lat":      jlat,
                "lon":      jlon,
                "penduduk": pop_each,
                "desa":     dname,
                "source":   "centroid_jitter",
            })

    print(f"\n[PROSES 3] Dasymetric mapping: {len(agent_origins)} titik asal agen")
    return agent_origins


# ═══════════════════════════════════════════════════════════════
# GRAPH BUILDER + PROSES 1: EKSTRAKSI NODE TERGENANG
# ═══════════════════════════════════════════════════════════════

def build_graph(roads: list, dem_mgr=None, transport: str = "foot") -> dict:
    """
    Bangun weighted graph dari road dicts.

    Bobot edge: composite (jarak + waktu + elevasi + slope).
    Waktu tempuh pejalan kaki dikoreksi dengan Tobler's Hiking Function
    berdasarkan slope link (Muhammad et al. 2021; Tobler 1993).

    Flow Capacity dan Storage Capacity per link dihitung mengikuti:
      FC = w × Cmax  (Muhammad et al. 2021, Eq. 1)
      SC = A × Dmax  (Muhammad et al. 2021, Eq. 2)

    Parameter dimensi agen:
      Pejalan kaki : area 0.5 m², Dmax 5.4/m², FC 1.3 orang/m/s
      Motor        : area 3.0 m², Dmax 0.4/m², FC 4.0 orang/m/s
      Mobil        : area 9.0 m² (4.5m×2m), Dmax 0.11/m², FC 0.5 orang/m/s
    """
    W_DIST, W_TIME, W_ELEV, W_SLOPE = 0.30, 0.30, 0.25, 0.15
    ELEV_DANGER_MAX = 20.0
    SLOPE_MAX_PCT   = 40.0

    # Kecepatan dasar sesuai moda transportasi
    base_speed_kmh = SPEED_DEFAULTS.get(transport, SPEED_DEFAULTS["foot"])

    nodes_list: List[Tuple] = []
    nodes_idx:  Dict        = {}

    def get_or_add(lat, lon):
        key = (round(lat, 5), round(lon, 5))
        if key not in nodes_idx:
            elev = 0.0
            if dem_mgr:
                e, _ = dem_mgr.query(lon, lat)
                if e is not None:
                    elev = float(e)
            nodes_idx[key] = len(nodes_list)
            nodes_list.append((lat, lon, elev))
        return nodes_idx[key]

    edges: Dict[int, list] = {}

    for road in roads:
        coords     = road["coords"]
        speed_road = road.get("speed_kmh", 20)  # kecepatan jalan dari OSM/SHP
        hw         = road.get("highway", "residential")
        # Lebar lajur — dari data jalan jika ada, fallback ROAD_WIDTH_DEFAULT_M
        road_width = float(road.get("width_m") or road.get("WIDTH_M") or
                           ROAD_WIDTH_DEFAULT_M)
        n_lanes    = max(1, int(road.get("lanes") or 1))
        lane_width = road_width / n_lanes if n_lanes > 1 else road_width

        # FC & SC per link (dihitung saat edge dibangun — per-segment)
        fc_link = flow_capacity_link(lane_width, transport)   # orang/s per lajur

        oneway = road.get("oneway", "no") in ("yes", "true", "1")
        prev_idx = None

        for lat, lon in coords:
            idx = get_or_add(lat, lon)
            if prev_idx is not None:
                plat, plon, pelev = nodes_list[prev_idx]
                clat, clon, celev = nodes_list[idx]
                dist  = haversine_m(plat, plon, clat, clon)

                # ── Slope & Tobler correction ─────────────────────
                slope_pct = (abs(celev - pelev) / dist * 100.0) if dist > 0 else 0.0
                import math as _math
                slope_deg = _math.degrees(_math.atan(slope_pct / 100.0))

                # Koreksi kecepatan pejalan kaki via Tobler (Muhammad 2021)
                if transport == "foot":
                    eff_speed = tobler_speed_kmh(slope_deg, base_speed_kmh)
                else:
                    # Motor/mobil: speed tetap dari jalan, dibatasi oleh moda
                    eff_speed = min(speed_road, base_speed_kmh)

                t_min = (dist / 1000) / max(eff_speed, 0.1) * 60

                # Storage capacity untuk link ini
                sc_link = storage_capacity_link(dist, lane_width, transport)

                # ── Composite bobot ───────────────────────────────
                elev_pen  = min(1.0, max(0.0, 1.0 - pelev / ELEV_DANGER_MAX))
                slope_pen = min(1.0, slope_pct / SLOPE_MAX_PCT)
                composite = (W_DIST * (dist / 1000) / 10.0 +
                             W_TIME * t_min / 60.0 +
                             W_ELEV * elev_pen +
                             W_SLOPE * slope_pen)

                # Simpan edge dengan metadata dimensi agen
                # format: (v, dist_m, t_min, hw, cap, composite, slope_pct, elev,
                #          fc_link, sc_link, slope_deg, eff_speed)
                edges.setdefault(prev_idx, []).append(
                    (idx, dist, t_min, hw, sc_link, composite, slope_pct, pelev,
                     fc_link, sc_link, slope_deg, eff_speed))

                if not oneway:
                    # Edge balik — slope terbalik (turun → Tobler berbeda)
                    slope_deg_rev = -slope_deg
                    if transport == "foot":
                        eff_speed_rev = tobler_speed_kmh(slope_deg_rev, base_speed_kmh)
                    else:
                        eff_speed_rev = eff_speed
                    t_min_rev = (dist / 1000) / max(eff_speed_rev, 0.1) * 60
                    elev_pen2  = min(1.0, max(0.0, 1.0 - celev / ELEV_DANGER_MAX))
                    composite2 = (W_DIST * (dist / 1000) / 10.0 +
                                  W_TIME * t_min_rev / 60.0 +
                                  W_ELEV * elev_pen2 +
                                  W_SLOPE * slope_pen)
                    edges.setdefault(idx, []).append(
                        (prev_idx, dist, t_min_rev, hw, sc_link, composite2,
                         slope_pct, celev, fc_link, sc_link, slope_deg_rev, eff_speed_rev))

            prev_idx = idx

    return {
        "nodes":     nodes_list,
        "edges":     edges,
        "transport": transport,
        "base_speed_kmh": base_speed_kmh,
    }


def extract_inundated_nodes(graph: dict,
                             inundation_geom: Optional[dict] = None,
                             swe_flood_checker=None,
                             t_min_check: float = 0) -> List[int]:
    """
    PROSES 1: Ekstraksi node jalan yang berada di area genangan tsunami.
    Prioritas: SWE flood checker > inundation_geom GeoJSON.
    Return: list index node yang tergenang.
    """
    nodes = graph.get("nodes", [])
    flooded_idx = []
    for i, (lat, lon, elev) in enumerate(nodes):
        is_flooded = False
        if swe_flood_checker:
            try:
                is_flooded = swe_flood_checker(lat, lon, t_min_check)
            except Exception:
                pass
        if not is_flooded and inundation_geom:
            is_flooded = point_in_geom(lat, lon, inundation_geom)
        if is_flooded:
            flooded_idx.append(i)
    print(f"[PROSES 1] Node tergenang: {len(flooded_idx)} / {len(nodes)} total node")
    return flooded_idx


# ═══════════════════════════════════════════════════════════════
# GRAPH UTILITIES: NEAREST NODE, DIJKSTRA, A*
# ═══════════════════════════════════════════════════════════════

def nearest_node(nodes_list: list, lat: float, lon: float) -> Tuple[int, float]:
    """Cari index node terdekat ke (lat, lon). Return (idx, dist_m)."""
    best_idx, best_d = 0, 1e18
    for i, node in enumerate(nodes_list):
        d = haversine_m(lat, lon, node[0], node[1])
        if d < best_d:
            best_d, best_idx = d, i
    return best_idx, best_d


def dijkstra(graph: dict, start_idx: int, end_idx: int,
             weight: str = "composite",
             blocked_nodes: Optional[set] = None) -> Tuple[Optional[float], list]:
    """
    Dijkstra shortest path.
    weight: 'composite' | 'time' | 'distance'
    blocked_nodes: set of node indices yang tidak boleh dilewati.
    """
    nodes = graph["nodes"]
    edges = graph["edges"]
    dist  = {start_idx: 0}
    prev  = {}
    pq    = [(0, start_idx)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        if u == end_idx:
            break
        for edge in edges.get(u, []):
            v, dist_m, t_min = edge[0], edge[1], edge[2]
            comp = edge[5] if len(edge) > 5 else t_min / 60.0
            if blocked_nodes and v in blocked_nodes and v != end_idx:
                continue
            w  = {"time": t_min, "distance": dist_m / 1000}.get(weight, comp)
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if end_idx not in prev and end_idx != start_idx:
        return None, []
    path = []
    cur  = end_idx
    while cur in prev:
        path.append(cur)
        cur = prev[cur]
    path.append(start_idx)
    path.reverse()
    return dist.get(end_idx, 1e18), [(nodes[i][0], nodes[i][1]) for i in path]


def astar(graph: dict, start_idx: int, end_idx: int,
          weight: str = "composite",
          transport_speed_kmh: float = 30,
          blocked_nodes: Optional[set] = None) -> Tuple[Optional[float], list]:
    """A* shortest path dengan heuristik haversine."""
    nodes = graph["nodes"]
    edges = graph["edges"]
    elat, elon = nodes[end_idx][0], nodes[end_idx][1]

    def heuristic(idx):
        d = haversine_m(nodes[idx][0], nodes[idx][1], elat, elon)
        if weight == "time":
            return (d / 1000) / transport_speed_kmh * 60
        elif weight == "distance":
            return d / 1000
        return (d / 1000) / transport_speed_kmh

    g    = {start_idx: 0}
    prev = {}
    pq   = [(heuristic(start_idx), 0, start_idx)]
    while pq:
        _, gn, u = heapq.heappop(pq)
        if u == end_idx:
            break
        if gn > g.get(u, 1e18):
            continue
        for edge in edges.get(u, []):
            v, dist_m, t_min = edge[0], edge[1], edge[2]
            comp = edge[5] if len(edge) > 5 else t_min / 60.0
            if blocked_nodes and v in blocked_nodes and v != end_idx:
                continue
            w  = {"time": t_min, "distance": dist_m / 1000}.get(weight, comp)
            ng = gn + w
            if ng < g.get(v, 1e18):
                g[v]    = ng
                prev[v] = u
                heapq.heappush(pq, (ng + heuristic(v), ng, v))
    if end_idx not in prev and end_idx != start_idx:
        return None, []
    path = []
    cur  = end_idx
    while cur in prev:
        path.append(cur)
        cur = prev[cur]
    path.append(start_idx)
    path.reverse()
    return g.get(end_idx, 1e18), [(nodes[i][0], nodes[i][1]) for i in path]


# ═══════════════════════════════════════════════════════════════
# PROSES 2: NETWORK ANALYSIS — FASTEST PATH
# ═══════════════════════════════════════════════════════════════

def compute_fastest_paths(graph: dict, origin_nodes: List[int],
                           tes_list: list, speed_kmh: float,
                           blocked_nodes: Optional[set] = None) -> Dict[int, dict]:
    """
    PROSES 2: Hitung Fastest Path (Dijkstra time-weight) dari setiap
    origin node ke TES terdekat.
    Return: {origin_node_idx: {tes_name, tes_lat, tes_lon, path, dist_m, time_min}}
    """
    nodes      = graph["nodes"]
    routes_out = {}

    # Precompute TES node indices
    tes_nodes = []
    for tes in tes_list:
        if not tes.get("lat") or not tes.get("lon"):
            continue
        ti, _ = nearest_node(nodes, tes["lat"], tes["lon"])
        tes_nodes.append((ti, tes))

    if not tes_nodes:
        return routes_out

    for orig_idx in origin_nodes:
        olat, olon, _ = nodes[orig_idx]
        best_route = None
        best_time  = 1e18

        for tes_idx, tes in tes_nodes:
            _, path = dijkstra(graph, orig_idx, tes_idx,
                               weight="time", blocked_nodes=blocked_nodes)
            if not path:
                d    = haversine_m(olat, olon, tes["lat"], tes["lon"])
                t    = (d / 1000) / speed_kmh * 60
                path = [[olat, olon], [tes["lat"], tes["lon"]]]
            dist  = path_dist_m(path)
            t_min = (dist / 1000) / speed_kmh * 60
            if t_min < best_time:
                best_time  = t_min
                best_route = {
                    "tes_name": tes["name"],
                    "tes_lat":  tes["lat"],
                    "tes_lon":  tes["lon"],
                    "path":     path,
                    "dist_m":   dist,
                    "time_min": t_min,
                }
        if best_route:
            routes_out[orig_idx] = best_route

    print(f"[PROSES 2] Fastest path: {len(routes_out)} rute dari {len(origin_nodes)} node asal")
    return routes_out


# ═══════════════════════════════════════════════════════════════
# EVACUATION ABM SOLVER — entry point untuk server
# ═══════════════════════════════════════════════════════════════

class EvacuationABMSolver:
    """
    Solver gabungan rute evakuasi + ABM evakuasi tsunami (5 proses penuh).

    Alur:
      1. build_caches()    → load jalan, desa, TES dari vektor_dir
      2. set_swe_results() → integrasi hasil SWE (opsional)
      3. compute_route()   → endpoint /network/route
      4. run_abm()         → simulasi ABM lengkap 5 proses
    """

    def __init__(self, vektor_dir: Optional[str] = None, dem_mgr=None):
        self.vektor_dir = vektor_dir
        self.dem_mgr    = dem_mgr

        self.road_cache:  Optional[dict] = None
        self.graph_cache: Optional[dict] = None
        self.desa_cache:  Optional[dict] = None
        self.tes_cache:   Optional[dict] = None

        # SWE integration
        self._swe_results:  Optional[dict] = None
        self._flood_grids:  dict = {}
        self._wave_arrival: dict = {}
        self._grid_meta:    dict = {}

    # ── Cache management ──────────────────────────────────────────

    def build_caches(self):
        """Load semua data vektor dan bangun graph jalan."""
        if not self.vektor_dir or not os.path.isdir(self.vektor_dir):
            print("  [WARN] EvacuationABMSolver: vektor_dir tidak valid")
            return
        self.road_cache = _build_road_cache(self.vektor_dir)
        if self.road_cache:
            print(f"\n🔧 Membangun road graph ({self.road_cache['feature_count']} ruas)...")
            self.graph_cache = build_graph(self.road_cache["roads"], dem_mgr=self.dem_mgr)
            n = len(self.graph_cache["nodes"])
            e = sum(len(v) for v in self.graph_cache["edges"].values())
            print(f"  [OK] Road graph: {n} node, {e} edge")
        self.desa_cache = _build_desa_cache(self.vektor_dir)
        self.tes_cache  = _build_tes_cache(self.vektor_dir)

    def cache_info(self) -> dict:
        """Ringkasan status cache."""
        return {
            "road": {
                "cached":        bool(self.road_cache),
                "source_file":   self.road_cache["source_file"]   if self.road_cache else None,
                "feature_count": self.road_cache["feature_count"] if self.road_cache else 0,
                "graph_nodes":   len(self.graph_cache["nodes"])   if self.graph_cache else 0,
                "graph_edges":   (sum(len(v) for v in self.graph_cache["edges"].values())
                                  if self.graph_cache else 0),
                "dem_integrated": self.dem_mgr is not None,
            },
            "desa": {
                "cached":      bool(self.desa_cache),
                "source_file": self.desa_cache["source_file"] if self.desa_cache else None,
                "count":       self.desa_cache["count"]        if self.desa_cache else 0,
            },
            "tes": {
                "cached":      bool(self.tes_cache),
                "source_file": self.tes_cache["source_file"] if self.tes_cache else None,
                "count":       self.tes_cache["count"]        if self.tes_cache else 0,
            },
        }

    # ── SWE integration ───────────────────────────────────────────

    def set_swe_results(self, swe_output: dict):
        """Terima hasil SWE untuk integrasi rute + ABM."""
        if not swe_output or not isinstance(swe_output, dict):
            return
        self._swe_results  = swe_output
        self._flood_grids  = {}
        self._wave_arrival = {}
        self._grid_meta    = swe_output.get("grid_meta", {})
        FLOOD_THRESHOLD_M  = 0.1
        wave_frames = swe_output.get("wave_frames", [])
        gm = self._grid_meta
        if wave_frames and gm:
            ny, nx = gm.get("ny", 1), gm.get("nx", 1)
            if ny < 2 or nx < 2:
                return
            for frame in wave_frames:
                t_min    = frame.get("t_min", 0)
                eta_flat = frame.get("eta_flat", [])
                if not eta_flat:
                    continue
                fs = set()
                for idx, h in enumerate(eta_flat):
                    if abs(h) < FLOOD_THRESHOLD_M:
                        continue
                    j, i = idx // nx, idx % nx
                    fs.add((j, i))
                    if (j, i) not in self._wave_arrival:
                        self._wave_arrival[(j, i)] = t_min
                self._flood_grids[t_min] = fs
            print(f"  [OK] SWE: {len(self._flood_grids)} frame, "
                  f"{len(self._wave_arrival)} titik wave arrival")

    def _grid_ij(self, lat: float, lon: float) -> Tuple[int, int]:
        gm = self._grid_meta
        lat_min, lat_max = gm.get("lat_min", 0), gm.get("lat_max", 1)
        lon_min, lon_max = gm.get("lon_min", 0), gm.get("lon_max", 1)
        ny, nx = gm.get("ny", 1), gm.get("nx", 1)
        j = int((lat - lat_min) / max(lat_max - lat_min, 1e-9) * (ny - 1))
        i = int((lon - lon_min) / max(lon_max - lon_min, 1e-9) * (nx - 1))
        return max(0, min(ny - 1, j)), max(0, min(nx - 1, i))

    def _is_flooded(self, lat: float, lon: float, t_min: float) -> bool:
        if not self._grid_meta or not self._flood_grids:
            return False
        gm = self._grid_meta
        if not (gm.get("lat_min", 0) <= lat <= gm.get("lat_max", 0) and
                gm.get("lon_min", 0) <= lon <= gm.get("lon_max", 0)):
            return False
        j, i = self._grid_ij(lat, lon)
        past  = sorted([t for t in self._flood_grids if t <= t_min], reverse=True)
        if not past:
            return False
        return (j, i) in self._flood_grids[past[0]]

    def _wave_arrival_at(self, lat: float, lon: float) -> Optional[float]:
        if not self._grid_meta or not self._wave_arrival:
            return None
        gm = self._grid_meta
        if not (gm.get("lat_min", 0) <= lat <= gm.get("lat_max", 0) and
                gm.get("lon_min", 0) <= lon <= gm.get("lon_max", 0)):
            return None
        j, i = self._grid_ij(lat, lon)
        return self._wave_arrival.get((j, i), None)

    # ── Helper: rute ke TES ────────────────────────────────────────

    def _route_to_tes(self, graph: dict, olat: float, olon: float,
                       tes: dict, speed_kmh: float,
                       blocked: Optional[set] = None) -> Tuple[list, float, float]:
        """Hitung fastest path dari (olat,olon) ke TES. Return (path, dist_m, time_min)."""
        nodes = graph.get("nodes", [])
        if not nodes:
            d = haversine_m(olat, olon, tes["lat"], tes["lon"])
            return [[olat, olon], [tes["lat"], tes["lon"]]], d, (d / 1000) / speed_kmh * 60

        si, _ = nearest_node(nodes, olat, olon)
        ei, _ = nearest_node(nodes, tes["lat"], tes["lon"])

        _, path = dijkstra(graph, si, ei, weight="time", blocked_nodes=blocked)
        if not path or len(path) < 2:
            _, path = astar(graph, si, ei, weight="time",
                            transport_speed_kmh=speed_kmh,
                            blocked_nodes=blocked)

        if path and len(path) >= 2:
            d = path_dist_m(path)
            return path, d, (d / 1000) / speed_kmh * 60

        d = haversine_m(olat, olon, tes["lat"], tes["lon"])
        return [[olat, olon], [tes["lat"], tes["lon"]]], d, (d / 1000) / speed_kmh * 60

    # ── Helper: TES terdekat dengan kapasitas ──────────────────────

    def _nearest_available_tes(self, lat: float, lon: float,
                                tes_list: list,
                                tes_occ: Dict[str, int],
                                tes_cap: Dict[str, int]) -> Optional[dict]:
        """Cari TES terdekat yang masih ada kapasitas."""
        best, best_d = None, 1e18
        for tes in tes_list:
            if not tes.get("lat") or not tes.get("lon"):
                continue
            nm = tes["name"]
            if tes_occ.get(nm, 0) >= tes_cap.get(nm, 99999):
                continue  # penuh
            d = haversine_m(lat, lon, tes["lat"], tes["lon"])
            if d < best_d:
                best_d, best = d, tes
        return best

    # ── Route computation (/network/route) ────────────────────────

    def compute_route(self, origin: dict, destination: dict,
                      method: str = "network", transport: str = "car",
                      weight: str = "composite", roads: list = None) -> dict:
        """Hitung rute evakuasi titik-ke-titik. Dipakai endpoint /network/route."""
        try:
            speed_kmh = SPEED_DEFAULTS.get(transport, 30)
            filtered_roads = []
            src_roads = roads or (self.road_cache["roads"] if self.road_cache else [])
            for r in src_roads:
                hw = r.get("highway", "")
                if transport in ("motor", "car") and hw in ("footway", "path", "steps"):
                    continue
                adj = dict(r)
                adj["speed_kmh"] = min(r.get("speed_kmh", 20), speed_kmh)
                filtered_roads.append(adj)

            if not filtered_roads:
                return {"error": "Tidak ada data jalan tersedia"}

            if roads and len(roads) >= 50:
                graph = build_graph(filtered_roads, dem_mgr=self.dem_mgr)
            elif self.graph_cache:
                graph = self.graph_cache
            else:
                graph = build_graph(filtered_roads, dem_mgr=self.dem_mgr)

            if not graph or not graph["nodes"]:
                return {"error": "Graph kosong — data jalan tidak valid"}

            nodes = graph["nodes"]
            olat, olon = origin.get("lat"), origin.get("lon")
            dlat, dlon = destination.get("lat"), destination.get("lon")
            start_idx, start_dist = nearest_node(nodes, olat, olon)
            end_idx,   end_dist   = nearest_node(nodes, dlat, dlon)

            # Blocked nodes dari SWE
            blocked = None
            if self._flood_grids:
                bl = {ni for ni, (nlat, nlon, _) in enumerate(nodes)
                      if self._is_flooded(nlat, nlon, t_min=0)}
                blocked = bl if bl else None

            def get_elev_profile(path_coords):
                out = []
                for lat, lon in path_coords:
                    if self.dem_mgr:
                        e, _ = self.dem_mgr.query(lon, lat)
                        out.append(round(float(e), 1) if e is not None else 0.0)
                    else:
                        out.append(0.0)
                return out

            def slope_stats(path_coords):
                slopes = []
                for i in range(len(path_coords) - 1):
                    a, b = path_coords[i], path_coords[i + 1]
                    d = haversine_m(a[0], a[1], b[0], b[1])
                    if d < 1:
                        continue
                    ea = eb = 0.0
                    if self.dem_mgr:
                        v, _ = self.dem_mgr.query(a[1], a[0]); ea = float(v) if v else 0.0
                        v, _ = self.dem_mgr.query(b[1], b[0]); eb = float(v) if v else 0.0
                    slopes.append(abs(eb - ea) / d * 100)
                return {
                    "avg_slope_pct": round(sum(slopes) / len(slopes), 1) if slopes else 0.0,
                    "max_slope_pct": round(max(slopes), 1) if slopes else 0.0,
                }

            def build_route_dict(coords, label, method_str, color, badge):
                total_d  = path_dist_m(coords)
                t_min    = (total_d / 1000) / speed_kmh * 60
                ep       = get_elev_profile(coords)
                ss       = slope_stats(coords)
                min_e    = min(ep) if ep else 0
                max_e    = max(ep) if ep else 0
                flooded  = [idx for idx, (lat, lon) in enumerate(coords)
                            if self._flood_grids and self._is_flooded(lat, lon, 0)]
                return {
                    "label":             label,
                    "method":            method_str,
                    "color":             color,
                    "badge":             badge,
                    "path":              coords,
                    "distance_m":        round(total_d),
                    "distance_km":       round(total_d / 1000, 2),
                    "time_min":          round(t_min, 1),
                    "time_str":          (f"{int(t_min//60)}j {int(t_min%60)} mnt"
                                         if t_min >= 60 else f"{round(t_min)} mnt"),
                    "node_count":        len(coords),
                    "elevation_profile": ep[::max(1, len(ep)//50)],
                    "min_elevation_m":   round(min_e, 1),
                    "max_elevation_m":   round(max_e, 1),
                    "elev_gain_m":       round(max_e - min_e, 1),
                    "flooded_segments":  flooded,
                    "has_flood_risk":    len(flooded) > 0,
                    **ss,
                }

            routes_out = []

            def try_dijkstra(w, label, color, badge):
                _, coords = dijkstra(graph, start_idx, end_idx,
                                     weight=w, blocked_nodes=blocked)
                if coords:
                    routes_out.append(build_route_dict(coords, label, f"dijkstra_{w}", color, badge))

            def try_astar(w, label, color, badge):
                _, coords = astar(graph, start_idx, end_idx, weight=w,
                                  transport_speed_kmh=speed_kmh, blocked_nodes=blocked)
                if coords:
                    routes_out.append(build_route_dict(coords, label, f"astar_{w}", color, badge))

            if method == "network":
                try_dijkstra("composite", "Rute Optimal (DEM+Slope)", "#4ade80", "badge-opt")
                try_dijkstra("time",      "Rute Tercepat",            "#facc15", "badge-alt")
                try_astar("distance",     "Rute Terpendek (A*)",      "#60a5fa", "badge-bpbd")
            elif method == "astar":
                try_astar(weight, "A* — Rute Heuristik", "#60a5fa", "badge-bpbd")
            else:
                try_dijkstra(weight, "Dijkstra — Jalur Optimal", "#4ade80", "badge-opt")

            if not routes_out:
                return {"error": "Rute tidak ditemukan — origin/destination di luar jaringan jalan"}

            best = routes_out[0]
            return {
                "ok":                True,
                "method":            method,
                "transport":         transport,
                "weight":            weight,
                "routes":            routes_out,
                "path":              best["path"],
                "distance_m":        best["distance_m"],
                "distance_km":       best["distance_km"],
                "time_min":          best["time_min"],
                "time_str":          best["time_str"],
                "node_count":        best["node_count"],
                "elevation_profile": best["elevation_profile"],
                "min_elevation_m":   best["min_elevation_m"],
                "max_elevation_m":   best["max_elevation_m"],
                "elev_gain_m":       best["elev_gain_m"],
                "avg_slope_pct":     best["avg_slope_pct"],
                "snap_origin_dist_m": round(start_dist),
                "snap_dest_dist_m":   round(end_dist),
                "graph_nodes":        len(nodes),
                "dem_available":      self.dem_mgr is not None,
                "swe_integrated":     bool(self._swe_results),
            }

        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()}

    # ── ABM simulation — 5-proses penuh ──────────────────────────

    def run_abm(self, body: dict) -> dict:
        """
        Simulasi ABM Evakuasi Tsunami — implementasi 5 proses penuh.

        Proses 1: Ekstraksi node jalan di zona genangan
        Proses 2: Network Analysis Fastest Path
        Proses 3: Dasymetric mapping (OSM building footprint → titik asal agen)
        Proses 4: Simulasi ABM time-step (pergerakan agen ke TES)
        Proses 5: Evaluasi kapasitas TES + rerouting ke TES alternatif

        Parameters (body dict):
          desa_list          : [{name, penduduk, lat, lon, geom?}, ...]
          tes_list           : [{name, lat, lon, kapasitas}, ...]
          roads              : [...] road dicts (opsional)
          transport          : 'foot' | 'motor' | 'car'
          inundation_runup_m : ketinggian banjir (meter)
          inundation_geom    : GeoJSON geometry zona genangan (opsional)
          warning_time_min   : waktu peringatan dini (menit)
          sim_duration_min   : durasi simulasi (menit)
          dt_min             : time step (menit)
          use_osm_buildings  : bool (default True)
          osm_timeout        : timeout OSM API (detik, default 15)

        Return:
          {ok, summary, agents, timeline, bottlenecks, arrived_by_desa,
           optimal_routes, tes_utilization, process_log}
        """
        try:
            t0 = time.time()
            log = []

            desa_list       = body.get("desa_list", [])
            tes_list        = body.get("tes_list", [])
            roads           = body.get("roads", [])
            transport       = body.get("transport", "foot")
            runup_m         = body.get("inundation_runup_m", 5.0)
            inundation_geom = body.get("inundation_geom", None)
            warning_min     = body.get("warning_time_min", 20)
            sim_dur         = body.get("sim_duration_min", 120)
            dt_min          = body.get("dt_min", 1)
            use_osm_bldg    = body.get("use_osm_buildings", True)
            osm_timeout     = body.get("osm_timeout", 15)

            speed_kmh = SPEED_DEFAULTS.get(transport, SPEED_DEFAULTS["foot"])

            if not desa_list:
                return {"error": "desa_list kosong"}
            if not tes_list:
                tes_list = [{"name": "TES Default", "lat": -7.99,
                             "lon": 110.28, "kapasitas": 99999}]

            # ── Pilih / bangun graph ──────────────────────────────────
            graph = None
            if self.graph_cache:
                graph = self.graph_cache
                log.append(f"Graph: cache ({len(graph['nodes'])} node)")
            elif roads and len(roads) >= 50:
                graph = build_graph(roads, dem_mgr=self.dem_mgr, transport=transport)
                log.append(f"Graph: dari roads payload ({len(roads)} ruas)")
            elif self.vektor_dir:
                rc = _build_road_cache(self.vektor_dir)
                if rc:
                    graph = build_graph(rc["roads"], dem_mgr=self.dem_mgr,
                                        transport=transport)
                    log.append(f"Graph: dari shapefile lokal ({len(rc['roads'])} ruas)")

            if not graph or not graph.get("nodes"):
                return {"error": "Graph jalan tidak tersedia"}

            nodes = graph["nodes"]

            # Blocked nodes (tergenang t=0, dari SWE)
            blocked: set = set()
            if self._flood_grids:
                for ni, (nlat, nlon, _) in enumerate(nodes):
                    if self._is_flooded(nlat, nlon, t_min=0):
                        blocked.add(ni)

            # ════════════════════════════════════════════════
            # PROSES 1: EKSTRAKSI NODE JALAN TERGENANG
            # ════════════════════════════════════════════════
            inundated_idx = extract_inundated_nodes(
                graph,
                inundation_geom=inundation_geom,
                swe_flood_checker=(self._is_flooded if self._flood_grids else None),
                t_min_check=warning_min,
            )
            log.append(f"Proses 1: {len(inundated_idx)} node tergenang dari {len(nodes)} total")

            # ════════════════════════════════════════════════
            # PROSES 2: FASTEST PATH (sample node tergenang)
            # ════════════════════════════════════════════════
            sample = inundated_idx
            if len(inundated_idx) > 150:
                step   = len(inundated_idx) // 150
                sample = inundated_idx[::step]

            fastest_paths = compute_fastest_paths(
                graph, sample, tes_list,
                speed_kmh=speed_kmh,
                blocked_nodes=blocked,
            )
            log.append(f"Proses 2: {len(fastest_paths)} fastest path dihitung")

            # ════════════════════════════════════════════════
            # PROSES 3: DASYMETRIC MAPPING — TITIK ASAL AGEN
            # ════════════════════════════════════════════════
            desa_affected = []
            for desa in desa_list:
                dlat = desa.get("lat")
                dlon = desa.get("lon")
                if not dlat or not dlon:
                    continue
                is_aff = True

                if self.dem_mgr and getattr(self.dem_mgr, "tiles", None):
                    elev, _ = self.dem_mgr.query(dlon, dlat)
                    if elev is not None:
                        is_aff = float(elev) <= runup_m + 2.0

                if not is_aff and self._swe_results:
                    is_aff = self._is_flooded(dlat, dlon, t_min=warning_min)

                if not is_aff and inundation_geom:
                    is_aff = point_in_geom(dlat, dlon, inundation_geom)

                if is_aff:
                    desa_affected.append(desa)

            if not desa_affected:
                desa_affected = desa_list
                log.append("Proses 3: Semua desa dianggap terdampak (tidak ada filter aktif)")

            if use_osm_bldg:
                agent_origins = dasymetric_mapping(
                    desa_affected,
                    inundation_geom=inundation_geom,
                    osm_timeout=osm_timeout,
                )
            else:
                agent_origins = []
                for desa in desa_affected:
                    n_pts    = min(5, max(1, desa.get("penduduk", 1000) // 500))
                    pop_each = max(1, desa.get("penduduk", 1000) // n_pts)
                    for i in range(n_pts):
                        agent_origins.append({
                            "name":     f"{desa['name']}_c{i}",
                            "lat":      desa["lat"] + random.gauss(0, 0.001),
                            "lon":      desa["lon"] + random.gauss(0, 0.001),
                            "penduduk": pop_each,
                            "desa":     desa["name"],
                            "source":   "centroid_jitter",
                        })

            log.append(f"Proses 3: {len(agent_origins)} titik asal dari "
                       f"{len(desa_affected)} desa terdampak")

            # ════════════════════════════════════════════════
            # PROSES 4: BUAT AGEN + ASSIGN RUTE AWAL
            # ════════════════════════════════════════════════
            tes_cap = {t["name"]: t.get("kapasitas", 500) for t in tes_list}
            tes_occ = {t["name"]: 0 for t in tes_list}

            agents = []
            for origin in agent_origins:
                olat  = origin["lat"]
                olon  = origin["lon"]
                pop   = origin["penduduk"]
                dname = origin["desa"]

                best_tes = self._nearest_available_tes(olat, olon, tes_list,
                                                        tes_occ, tes_cap)
                if not best_tes:
                    best_tes = min(tes_list,
                                   key=lambda t: haversine_m(olat, olon,
                                                              t.get("lat", 0), t.get("lon", 0)))

                rpath, rdist, rtime = self._route_to_tes(
                    graph, olat, olon, best_tes, speed_kmh, blocked)

                response_delay = max(0.0, min(15.0, random.gauss(5, 3)))
                ind_speed      = speed_kmh * random.uniform(0.7, 1.1)
                wave_t         = self._wave_arrival_at(olat, olon)

                agents.append({
                    "id":               f"{dname}_{len(agents)}",
                    "desa":             dname,
                    "population":       pop,
                    "start_lat":        olat,
                    "start_lon":        olon,
                    "cur_lat":          olat,
                    "cur_lon":          olon,
                    "target_tes":       best_tes["name"],
                    "target_lat":       best_tes["lat"],
                    "target_lon":       best_tes["lon"],
                    "route_path":       rpath,
                    "route_dist_m":     rdist,
                    "route_time_min":   rtime,
                    "speed_kmh":        ind_speed,
                    "depart_min":       warning_min + response_delay,
                    "arrive_min":       warning_min + response_delay + rtime,
                    "wave_arrival_min": wave_t,
                    "status":           "waiting",
                    "source":           origin.get("source", ""),
                })

            if not agents:
                return {"error": "Tidak ada agen yang dibuat — cek data desa dan zona inundasi"}
            log.append(f"Proses 4: {len(agents)} agen dibuat")

            # ════════════════════════════════════════════════
            # PROSES 4 & 5: SIMULASI TIME-STEP ABM
            # ════════════════════════════════════════════════
            t_steps  = list(range(0, sim_dur + 1, dt_min))
            timeline = []
            bottlenecks: Dict[str, int] = {}
            tes_occ_sim: Dict[str, int] = {t["name"]: 0 for t in tes_list}
            optimal_routes_by_tes: Dict[str, list] = {}

            # ── Infrastruktur kemacetan (Congestion Model) ────────────
            # Referensi: Muhammad et al. (2021), Lämmel et al. (2009)
            # FC = w × Cmax → kapasitas alir link (orang/s)
            # SC = A × Dmax → kapasitas tampung link (orang)
            # Jika jumlah agen di segmen mendekati SC → kecepatan turun
            tes_link_cap = TES_LINK_CAPACITY.get(transport, TES_LINK_CAPACITY["foot"])
            default_fc   = flow_capacity_link(ROAD_WIDTH_DEFAULT_M, transport)
            default_sc   = storage_capacity_link(500, ROAD_WIDTH_DEFAULT_M, transport)

            # Jumlah agen per segmen jalan di timestep sebelumnya
            seg_agent_count: Dict[str, int] = {}

            for t in t_steps:
                moved = 0
                positions = []
                seg_agent_count_prev = dict(seg_agent_count)
                seg_agent_count.clear()

                for ag in agents:
                    # Cek apakah gelombang sudah tiba sebelum agen sampai
                    if (ag.get("wave_arrival_min") is not None
                            and ag["status"] not in ("arrived", "stranded")
                            and t >= ag["wave_arrival_min"]
                            and t < ag.get("arrive_min", 1e18)):
                        ag["status"] = "stranded"

                    if ag["status"] == "stranded":
                        positions.append({
                            "id": ag["id"], "lat": ag["cur_lat"],
                            "lon": ag["cur_lon"], "status": "stranded",
                            "pop": ag["population"],
                        })
                        continue

                    if t < ag["depart_min"]:
                        positions.append({
                            "id": ag["id"], "lat": ag["start_lat"],
                            "lon": ag["start_lon"], "status": "waiting",
                            "pop": ag["population"],
                        })
                        continue

                    elapsed      = t - ag["depart_min"]

                    # ── Congestion correction (Muhammad et al. 2021) ──────
                    # Cek kepadatan di segmen saat ini menggunakan data timestep sebelumnya
                    # Jika agent_count > SC (storage capacity) → kecepatan turun
                    cur_seg = f"{round(ag['cur_lat'], 3)},{round(ag['cur_lon'], 3)}"
                    agents_on_seg = seg_agent_count_prev.get(cur_seg, 0)
                    cf = congestion_factor(agents_on_seg, default_sc)
                    eff_speed_kmh = ag["speed_kmh"] * cf   # kecepatan terkoreksi kemacetan

                    dist_covered = (eff_speed_kmh / 60) * elapsed * 1000

                    # Cek apakah sudah tiba di TES
                    if ag["status"] == "arrived" or dist_covered >= ag["route_dist_m"]:
                        if ag["status"] != "arrived":
                            # ── PROSES 5: CEK KAPASITAS TES ──────────
                            tes_nm = ag["target_tes"]
                            occ    = tes_occ_sim.get(tes_nm, 0)
                            cap    = tes_cap.get(tes_nm, 99999)

                            if occ + ag["population"] <= cap:
                                # Masuk TES — selamat
                                ag["status"] = "arrived"
                                tes_occ_sim[tes_nm] = occ + ag["population"]
                                if tes_nm not in optimal_routes_by_tes:
                                    optimal_routes_by_tes[tes_nm] = []
                                optimal_routes_by_tes[tes_nm].append(
                                    ag["route_path"][:30])
                            else:
                                # TES penuh → reroute ke TES alternatif
                                other = [x for x in tes_list if x["name"] != tes_nm]
                                alt   = self._nearest_available_tes(
                                    ag["cur_lat"], ag["cur_lon"],
                                    other, tes_occ_sim, tes_cap)
                                if alt:
                                    np_, nd, nt = self._route_to_tes(
                                        graph,
                                        ag["cur_lat"], ag["cur_lon"],
                                        alt, speed_kmh, blocked)
                                    ag["target_tes"]   = alt["name"]
                                    ag["target_lat"]   = alt["lat"]
                                    ag["target_lon"]   = alt["lon"]
                                    ag["route_path"]   = np_
                                    ag["route_dist_m"] = nd
                                    ag["route_time_min"] = nt
                                    ag["arrive_min"]   = t + nt
                                    ag["depart_min"]   = t
                                    ag["status"]       = "moving"
                                    moved += 1
                                else:
                                    ag["status"] = "stranded"

                        if ag["status"] == "arrived":
                            positions.append({
                                "id": ag["id"],
                                "lat": ag["target_lat"],
                                "lon": ag["target_lon"],
                                "status": "arrived",
                                "pop": ag["population"],
                            })
                            continue

                    if ag["status"] == "stranded":
                        positions.append({
                            "id": ag["id"], "lat": ag["cur_lat"],
                            "lon": ag["cur_lon"], "status": "stranded",
                            "pop": ag["population"],
                        })
                        continue

                    # Interpolasi posisi sepanjang rute
                    progress = min(1.0, dist_covered / max(ag["route_dist_m"], 1))
                    path     = ag["route_path"]
                    idx_f    = progress * (len(path) - 1)
                    i0       = min(int(idx_f), len(path) - 2)
                    frac     = idx_f - i0
                    p1, p2   = path[i0], path[min(i0 + 1, len(path) - 1)]
                    cur_lat  = p1[0] + frac * (p2[0] - p1[0])
                    cur_lon  = p1[1] + frac * (p2[1] - p1[1])
                    ag["cur_lat"] = cur_lat
                    ag["cur_lon"] = cur_lon

                    # Cek genangan real-time (SWE)
                    if self._flood_grids and self._is_flooded(cur_lat, cur_lon, t_min=t):
                        ag["status"] = "stranded"
                        positions.append({
                            "id": ag["id"], "lat": cur_lat, "lon": cur_lon,
                            "status": "stranded", "pop": ag["population"],
                        })
                        continue

                    ag["status"] = "moving"
                    moved += 1

                    seg_key = f"{round(cur_lat, 3)},{round(cur_lon, 3)}"
                    bottlenecks[seg_key] = bottlenecks.get(seg_key, 0) + ag["population"]
                    # Hitung jumlah agen per segmen (untuk congestion model di t berikutnya)
                    seg_agent_count[seg_key] = seg_agent_count.get(seg_key, 0) + 1

                    positions.append({
                        "id": ag["id"], "lat": cur_lat, "lon": cur_lon,
                        "status": "moving", "pop": ag["population"],
                    })

                if t % 5 == 0 or t == sim_dur:
                    timeline.append({
                        "t_min":    t,
                        "moving":   moved,
                        "arrived":  sum(1 for a in agents if a["status"] == "arrived"),
                        "waiting":  sum(1 for a in agents if a["status"] == "waiting"),
                        "stranded": sum(1 for a in agents if a["status"] == "stranded"),
                        "positions": positions[:200],
                    })

            log.append(f"Proses 4-5: Simulasi {sim_dur} mnt selesai ({len(t_steps)} langkah)")

            # ── Statistik ringkasan ───────────────────────────────────
            total_pop      = sum(ag["population"] for ag in agents)
            final_arrived  = sum(ag["population"] for ag in agents if ag["status"] == "arrived")
            final_stranded = sum(ag["population"] for ag in agents if ag["status"] == "stranded")
            avg_time       = sum(ag["route_time_min"] for ag in agents) / max(len(agents), 1)

            arrived_by_desa: Dict[str, int] = {}
            for ag in agents:
                if ag["status"] == "arrived":
                    arrived_by_desa[ag["desa"]] = (
                        arrived_by_desa.get(ag["desa"], 0) + ag["population"])

            bottleneck_list = sorted(
                [{"lat": float(k.split(",")[0]), "lon": float(k.split(",")[1]), "count": v}
                 for k, v in bottlenecks.items()],
                key=lambda x: -x["count"],
            )[:20]

            # Optimal routes (Proses 5 output)
            optimal_routes = []
            for tes_nm, paths in optimal_routes_by_tes.items():
                if paths:
                    rep = min(paths, key=lambda p: path_dist_m(p))
                    optimal_routes.append({
                        "tes":    tes_nm,
                        "path":   rep,
                        "dist_m": round(path_dist_m(rep)),
                    })

            # TES utilization
            tes_util = [
                {
                    "name":             t.get("name", ""),
                    "kapasitas":        tes_cap.get(t.get("name", ""), 0),
                    "occupied":         tes_occ_sim.get(t.get("name", ""), 0),
                    "utilization_pct":  round(
                        tes_occ_sim.get(t.get("name", ""), 0) /
                        max(tes_cap.get(t.get("name", ""), 1), 1) * 100, 1),
                    "lat":              t.get("lat"),
                    "lon":              t.get("lon"),
                }
                for t in tes_list
            ]

            compute_s = round(time.time() - t0, 2)
            log.append(f"Total komputasi: {compute_s}s")

            return {
                "ok": True,
                "summary": {
                    "total_agents":       len(agents),
                    "total_population":   total_pop,
                    "arrived_pop":        final_arrived,
                    "stranded_pop":       final_stranded,
                    "arrival_rate":       round(final_arrived / max(total_pop, 1) * 100, 1),
                    "stranded_rate":      round(final_stranded / max(total_pop, 1) * 100, 1),
                    "avg_time_min":       round(avg_time, 1),
                    "max_time_min":       round(max(ag["route_time_min"] for ag in agents), 1),
                    "warning_time_min":   warning_min,
                    "tes_count":          len(tes_list),
                    "desa_count":         len(desa_affected),
                    "transport":          transport,
                    "speed_base_kmh":     round(speed_kmh, 2),
                    "speed_base_ms":      round(speed_kmh * 1000 / 3600, 2),
                    # Parameter dimensi agen (Muhammad et al. 2021, Lämmel 2009, Weidmann 1993)
                    "agent_area_m2":      AGENT_AREA_M2.get(transport),
                    "vehicle_dim_m":      VEHICLE_DIM_M.get(transport),
                    "dmax_per_m2":        DMAX_PER_M2.get(transport),
                    "flow_cap_per_m_s":   FLOW_CAPACITY_PER_M_PER_S.get(transport),
                    "tes_link_capacity":  tes_link_cap,
                    "road_width_m":       ROAD_WIDTH_DEFAULT_M,
                    "congestion_model":   "Muhammad et al. (2021) / Lämmel et al. (2009)",
                    "slope_correction":   "Tobler (1993)" if transport == "foot" else "tidak digunakan",
                    "swe_integrated":     bool(self._swe_results),
                    "osm_buildings_used": use_osm_bldg,
                    "inundated_nodes":    len(inundated_idx),
                    "compute_time_s":     compute_s,
                },
                "agents": [
                    {
                        "id":               ag["id"],
                        "desa":             ag["desa"],
                        "population":       ag["population"],
                        "start":            [ag["start_lat"], ag["start_lon"]],
                        "target":           [ag["target_lat"], ag["target_lon"]],
                        "target_tes":       ag["target_tes"],
                        "route_path":       ag["route_path"][:50],
                        "dist_km":          round(ag["route_dist_m"] / 1000, 2),
                        "time_min":         round(ag["route_time_min"], 1),
                        "depart_min":       round(ag["depart_min"], 1),
                        "arrive_min":       round(ag["arrive_min"], 1),
                        "wave_arrival_min": ag.get("wave_arrival_min"),
                        "status":           ag["status"],
                        "source":           ag.get("source", ""),
                    }
                    for ag in agents
                ],
                "timeline":          timeline,
                "bottlenecks":       bottleneck_list,
                "arrived_by_desa":   arrived_by_desa,
                "optimal_routes":    optimal_routes,   # Jalur evakuasi optimal (Proses 5)
                "tes_utilization":   tes_util,          # Utilisasi kapasitas TES (Proses 5)
                "process_log":       log,
            }

        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()}
