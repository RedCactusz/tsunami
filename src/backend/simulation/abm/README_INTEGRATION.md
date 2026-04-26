# Integrasi Pemukiman dan TES untuk ABM

## 📁 Data Sources

### 1. Pemukiman (Source/Agen)
**File:** `data/Vektor/Pemukiman.geojson`

**Struktur:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "NAMOBJ": "Donotirto",        // Nama desa
        "Penduduk": 8355.0,          // Jumlah penduduk
        "Kepadatan": 0.024,          // Kepadatan
        "SHAPE_Area": 351988.19      // Luas area
      },
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [...]
      }
    }
  ]
}
```

### 2. TES (Tujuan/Shelter)
**File:** `data/Vektor/TES_Bantul.shp`

**Kolom:**
- `Nama`: Nama TES
- `kapasitas`: Kapasitas (integer)
- `jenis`: Jenis fasilitas
- `geometry`: Lokasi (Point/Polygon)

---

## 🔧 Cara Penggunaan

### Step 1: Load Data

```python
from settlement_analyzer import SettlementAnalyzer, load_settlement_data
from shelter_selector import ShelterSelector, load_shelter_data
import geopandas as gpd

# Load Pemukiman (source agents)
pemukiman_gdf = load_settlement_data('data/Vektor/Pemukiman.geojson')

# Load TES (shelter)
tes_gdf = gpd.read_file('data/Vektor/TES_Bantul.shp')
if tes_gdf.crs is not None:
    tes_gdf = tes_gdf.to_crs(epsg=4326)
```

### Step 2: Initialize Analyzers

```python
# Settlement Analyzer - untuk generate agents dari pemukiman
settlement_analyzer = SettlementAnalyzer(
    desa_gdf=None,  # Tidak perlu desa jika pakai Pemukiman langsung
    settlement_gdf=pemukiman_gdf,
    use_gpu=False
)

# Shelter Selector - untuk memilih TES terdekat
shelter_selector = ShelterSelector(
    shelter_gdf=tes_gdf,
    use_gpu=False
)
```

### Step 3: Analisis Pemukiman

```python
# Gunakan method baru untuk langsung parse Pemukiman.geojson
settlement_analyzer.analyze_pemukiman_geojson()

# Filter pemukiman yang terkena inundasi (jika ada data inundation)
affected_settlements = settlement_analyzer.filter_settlements_in_inundation_zone(
    inundation_polygon=None,  # Optional: dari hasil SWE
    depth_grid=None,
    grid_bounds=None,
    hazard_threshold_m=0.3,
    inundation_geojson=None  # Optional: GeoJSON inundation dari SWE
)

print(f"Total pemukiman terdampak: {len(affected_settlements)}")
print(f"Total penduduk terdampak: {settlement_analyzer.affected_pop}")
```

### Step 4: Generate Agent Positions

```python
# Generate agent untuk ABM
# agents_per_person: rasio (0.01 = 1 agent per 100 orang)
agents = settlement_analyzer.generate_agent_positions(
    affected_settlements,
    agents_per_person=0.01  # Sesuaikan untuk jumlah agent yang manageable
)

print(f"Total agents: {len(agents)}")
# Contoh output:
# {
#   'agent_id': 'Donotirto_0_1',
#   'lat': -8.0123,
#   'lon': 110.3456,
#   'settlement_id': 'Donotirto_0',
#   'desa': 'Donotirto',
#   'population_represented': 83,
#   'initial_depth': 1.5,
#   'hazard_level': 'TINGGI'
# }
```

### Step 5: Assign Shelter ke Agent

```python
# Filter shelter yang aman (tidak tergenang)
safe_shelters = shelter_selector.filter_safe_shelters(
    inundation_polygon=None,  # Optional: dari hasil SWE
    min_distance_m=100
)

# Assign shelter terdekat ke setiap pemukiman/agent
shelter_assignments = shelter_selector.assign_shelters_to_settlements(
    affected_settlements,
    max_distance_km=5.0
)

# Tambahkan info shelter ke setiap agent
for agent in agents:
    settlement_id = agent['settlement_id']
    if settlement_id in shelter_assignments:
        shelter_id = shelter_assignments[settlement_id]
        shelter = shelter_selector.get_shelter_by_id(shelter_id)
        if shelter:
            agent['target_shelter_id'] = shelter.shelter_id
            agent['target_shelter_name'] = shelter.name
            agent['target_shelter_lat'] = shelter.lat
            agent['target_shelter_lon'] = shelter.lon
```

### Step 6: Jalankan ABM dengan Data Lengkap

```python
# Siapkan data untuk ABM
abm_input = {
    'agents': agents,  # Dengan target shelter info
    'warning_time_min': 20.0,
    'duration_min': 120.0,
    'dt_min': 1.0,
    'num_agents': len(agents),
}

# Jalankan ABM simulation
result = abm_solver.run_abm(abm_input)
```

---

## 📊 Statistik

### Settlement Analyzer Stats
```python
stats = settlement_analyzer.get_summary_statistics()
print(stats)
# {
#   'total_desa': 10,
#   'total_settlements': 150,
#   'affected_settlements': 45,
#   'total_population': 50000,
#   'affected_population': 15000,
#   'affected_percentage': 30.0
# }
```

### Shelter Selector Stats
```python
stats = shelter_selector.get_summary_statistics()
print(stats)
# {
#   'total_safe_shelters': 16,
#   'total_capacity': 8000,
#   'types': {'TES': 16, 'PublicFacility': 0}
# }
```

---

## ⚙️ Konfigurasi

### Parameter Penting

**Settlement Analyzer:**
- `agents_per_person`: Rasio agent terhadap penduduk (0.01 = 1%)
  - Terlalu banyak → performance lambat
  - Terlalu sedikit → tidak representatif
  - Rekomendasi: 0.01 - 0.05 untuk testing

**Shelter Selector:**
- `max_distance_km`: Jarak maksimal ke shelter (default: 5.0 km)
- `min_distance_m`: Jarak minimum dari shoreline untuk shelter aman (default: 100 m)

---

## 🐛 Troubleshooting

### Masalah: CRS Mismatch
**Error:** `Operasi geometri gagal karena CRS berbeda`

**Solusi:**
```python
# Pastikan semua data dalam EPSG:4326 (WGS84)
pemukiman_gdf = pemukiman_gdf.to_crs(epsg=4326)
tes_gdf = tes_gdf.to_crs(epsg=4326)
desa_gdf = desa_gdf.to_crs(epsg=4326)
```

### Masalah: Agent Terlalu Banyak
**Error:** Timeout atau memory error

**Solusi:**
```python
# Kurangi rasio agent
agents = settlement_analyzer.generate_agent_positions(
    affected_settlements,
    agents_per_person=0.001  # 0.1% saja
)
```

### Masalah: Tidak ada Shelter yang Aman
**Warning:** `No safe shelters found`

**Solusi:**
```python
# Hilangkan filter inundation atau perbesar jarak
safe_shelters = shelter_selector.filter_safe_shelters(
    inundation_polygon=None,  # abaikan inundasi
    min_distance_m=0
)
```

---

## 📝 Catatan Penting

1. **Pemukiman.geojson** adalah source utama untuk agent positions
2. **TES_Bantul.shp** adalah destination untuk evakuasi
3. Gunakan `analyze_pemukiman_geojson()` untuk Pemukiman.geojson
4. Gunakan `analyze_settlements_per_desa()` untuk shapefile bangunan
5. Selalu cek CRS sebelum operasi geometri
6. Adjust `agents_per_person` berdasarkan kapasitas komputer

---

## 🔗 Endpoint API Contoh

```python
@app.post("/api/abm/simulate")
async def abm_simulate(req: ABMRequest):
    # 1. Load data
    pemukiman_gdf = load_settlement_data('data/Vektor/Pemukiman.geojson')
    tes_gdf = gpd.read_file('data/Vektor/TES_Bantul.shp').to_crs(epsg=4326)

    # 2. Initialize analyzers
    settlement_analyzer = SettlementAnalyzer(None, pemukiman_gdf)
    shelter_selector = ShelterSelector(tes_gdf)

    # 3. Analisis dan generate agents
    settlement_analyzer.analyze_pemukiman_geojson()
    affected_settlements = settlement_analyzer.filter_settlements_in_inundation_zone(
        inundation_geojson=req.inundation_geojson
    )
    agents = settlement_analyzer.generate_agent_positions(
        affected_settlements,
        agents_per_person=0.01
    )

    # 4. Assign shelter
    safe_shelters = shelter_selector.filter_safe_shelters()
    assignments = shelter_selector.assign_shelters_to_settlements(agents)

    # 5. Jalankan ABM
    result = abm_solver.run_abm({
        'agents': agents,
        'shelters': safe_shelters,
        'shelter_assignments': assignments,
        'warning_time_min': req.warning_time_min,
        'duration_min': req.duration_min
    })

    return result
```
