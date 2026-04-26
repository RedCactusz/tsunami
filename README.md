# WebGIS Tsunami Simulation & Evacuation Analysis
**Simulasi Tsunami dan Analisis Evakuasi Berbasis WebGIS**

---

## 📋 Project Information

**Mata Kuliah:** Komputasi Geospasial
**Program:** Magister Teknik Geomatika, Universitas Gadjah Mada
**Kelompok:** 3
**Tahun Akademik:** 2024/2025

---

## 👥 Anggota Kelompok

| No | Nama | NIM | Peran |
|-----|------|-----|------|
| 1 | Muhammad Rouf Indhra Dewa S | 24/552974/PTK/16494 |
| 2 | Zulfikar Baihakki Budiyono | 25/568388/PTK/16751 |
| 3 | Oktavia Nutivara Waskito | 25/562735/PTK/16612 |
| 4 | Saffira Noor Chotimah | 25/563053/PTK/16640 |
| 5 | Frans Waas | 25/566567/PTK/16709 |
| 6 | Iman Taufiqqurrahman | 25/569788/PTK/16971 |

---

## 🎯 Project Overview

Aplikasi WebGIS terintegrasi untuk:
1. **Simulasi Tsunami** - Model numerik propagasi tsunami menggunakan Shallow Water Equation (SWE)
2. **Analisis Evakuasi** - Agent-Based Modeling (ABM) untuk simulasi pergerakan evakuasi penduduk
3. **Routing Analysis** - Analisis jaringan jalan dan rute evakuasi optimal ke TES
4. **Visualisasi Interaktif** - Dashboard modern dengan Leaflet untuk visualisasi real-time

---

## 🏗️ Project Architecture

```
tsunami/
├── src/
│   ├── backend/                      # FastAPI Backend
│   │   ├── server.py                 # API Gateway & Orchestration
│   │   ├── requirements.txt          # Python Dependencies
│   │   ├── data/                     # GIS Data Storage
│   │   │   ├── Raster/               # Bathymetry & DEM
│   │   │   │   ├── BATNAS/           # Batimetri nasional
│   │   │   │   ├── DEMNAS/           # Digital Elevation Model
│   │   │   │   └── GEBCO/            # Bathymetry global
│   │   │   └── Vektor/              # Vector Shapefiles
│   │   │       ├── Administrasi_Desa.shp
│   │   │       ├── Garis_Pantai_Selatan.shp
│   │   │       ├── Jalan_Bantul.shp
│   │   │       ├── Koordinat_TES.shp
│   │   │       ├── TES_Bantul.shp
│   │   │       ├── Pemukiman.geojson
│   │   │       ├── SESAR-PUSGEN/    # Fault data (LineString)
│   │   │       └── INA_Megathrust.shp # Megathrust zones (Polygon)
│   │   └── simulation/              # Simulation Modules
│   │       ├── swe/                 # Shallow Water Equations
│   │       │   ├── fault_loader.py  # Load fault & megathrust data
│   │       │   └── swe_solver.py    # SWE numerical solver
│   │       ├── routing/             # Network Analysis
│   │       │   └── routing.py       # Dijkstra pathfinding
│   │       └── abm/                 # Agent-Based Modeling
│   │           ├── evacuation_abm.py # Main ABM solver
│   │           ├── agent_generator.py # Generate population agents
│   │           ├── data_loader.py    # Load settlement & TES data
│   │           ├── settlement_analyzer.py # Population analysis
│   │           └── shelter_selector.py # Shelter allocation
│   │
│   └── frontend/                    # Next.js Frontend (TypeScript)
│       ├── app/                     # Next.js App Router
│       │   ├── page.tsx             # Main page
│       │   ├── globals.css          # Global styles & theme
│       │   └── layout.tsx           # Root layout
│       ├── components/              # React Components
│       │   ├── dashboard/           # Dashboard panels
│       │   │   ├── UnifiedPanel.tsx # Main control panel
│       │   │   ├── BottomBar.tsx    # Bottom info bar
│       │   │   └── controls/        # Control components
│       │   │       ├── SourceSelector.tsx      # Earthquake source selector
│       │   │       ├── FaultSelector.tsx        # Fault list selector
│       │   │       ├── SimulationParameters.tsx # Magnitude, fault type, etc
│       │   │       ├── RouteAnalysisPanel.tsx  # Routing controls
│       │   │       ├── ABMPanel.tsx            # ABM controls
│       │   │       └── TransportModeSelector.tsx # Foot/motor/car
│       │   ├── map/                 # Map components
│       │   │   ├── Map.tsx          # Main Leaflet map
│       │   │   ├── LayerControl.tsx # Layer toggle panel
│       │   │   ├── ServerStatus.tsx # Backend status indicator
│       │   │   ├── ExportPanel.tsx  # Data export panel
│       │   │   └── ABMAgentsLayer.tsx # ABM agent visualization
│       │   └── ui/                  # UI components
│       │       ├── Header.tsx       # App header with UGM logo
│       │       ├── ProgressBar.tsx  # Simulation progress
│       │       └── ABMAnimationControls.tsx # ABM playback controls
│       ├── services/                # API Client
│       │   └── api.ts               # Backend API calls
│       ├── types/                   # TypeScript Definitions
│       │   └── index.ts             # Type definitions
│       ├── hooks/                   # Custom React Hooks
│       │   └── useSimulation.ts     # Simulation state management
│       ├── package.json             # Node.js dependencies
│       └── public/                  # Static assets
│           └── Logo UGM.png         # UGM Logo
│
└── README.md
```

---

## 🎨 UI/UX Features

### Modern Academic Theme
- **Color Scheme:** Blue (#3b82f6), White (#ffffff), Yellow (#f59e0b)
- **Typography:** Plus Jakarta Sans for clean, readable text
- **Design Style:** Casual academic - professional but approachable

### Key UI Components
1. **Unified Control Panel** - Single panel for all simulation parameters
   - Tab navigation: Simulasi Tsunami | Evakuasi
   - Earthquake source selection: Fault | Megathrust | Custom Epicenter
   - Real-time parameter feedback

2. **Interactive Map** - Leaflet-based with:
   - Multiple basemaps: Satellite, OSM, Terrain
   - Layer control: Toggle inundation, routes, agents, admin boundaries
   - Fault highlighting with auto-zoom
   - Custom point picker for epicenter/origin

3. **Status Indicators**
   - Server status widget (online/offline)
   - Simulation progress tracker
   - Real-time result feedback

4. **Export Panel** - Export simulation results in multiple formats
   - GeoJSON, Shapefile, CSV, KML, PNG

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (untuk backend)
- **Node.js 18+** (untuk frontend)
- **Git**

### Backend Setup

1. **Navigate ke backend directory**
   ```bash
   cd src/backend
   ```

2. **Create & activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # atau
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run FastAPI server**
   ```bash
   python server.py
   # atau dengan uvicorn
   uvicorn server:app --reload --host 0.0.0.0 --port 8000
   ```
   Server akan berjalan di `http://localhost:8000`

### Frontend Setup

1. **Navigate ke frontend directory**
   ```bash
   cd src/frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Run development server**
   ```bash
   npm run dev
   ```
   Aplikasi akan membuka di `http://localhost:3000`

### Access Application

- **WebGIS Dashboard:** http://localhost:3000
- **API Documentation:** http://localhost:8000/docs
- **API ReDoc:** http://localhost:8000/redoc

---

## 📊 Core Features

### 1. Tsunami Simulation (SWE)
- **Model Numerik:** Shallow Water Equation (SWE) linear & nonlinear
- **Sumber Tsunami:**
  - ⚡ **Fault** - Aktif fault sesar (LineString geometry)
  - 🌊 **Megathrust** - Interplate megathrust zones (Polygon geometry)
  - 📍 **Custom** - Custom epicenter point selection
- **Okada Model:** Rectangular fault surface deformation
- **Parameter Inputs:**
  - Magnitude: 5.0 - 9.5 Mw
  - Fault type: Vertical, Horizontal, Thrust
  - Depth, length, rake (default values)
- **Output:** Wave propagation animation, inundation zones, max wave height

### 2. Routing Analysis
- **Network Graph:** OSM road network converted to graph
- **Pathfinding:** Dijkstra's algorithm for shortest path
- **Transport Modes:** Foot (4 km/h), Motor (30 km/h), Car (40 km/h)
- **Features:**
  - Custom origin point picker
  - TES destination selection
  - Route visualization on map
  - Travel time estimation

### 3. ABM Evacuation
- **Agent Generation:** Dasymetric population mapping
- **Movement Logic:** Hazard-aware routing dengan traffic congestion
- **Parameters:**
  - Warning time: 20 min (default)
  - Simulation duration: 120 min (default)
  - Flood height: 5 m (from SWE output)
- **Output:** Agent positions, arrival times, evacuation statistics
- **Integration:** Uses SWE inundation data for hazard-aware routing

### 4. GIS Data Integration
- **Vector Data:**
  - Fault lines (SESAR-PUSGEN v1.2) - 15 segments
  - Megathrust zones (INA_Megathrust) - 15 zones
  - Road network (OpenStreetMap)
  - Village boundaries (Administrasi_Desa)
  - TES locations (Koordinat_TES, TES_Bantul)
  - Settlements (Pemukiman)
  - Coastline (Garis_Pantai_Selatan)
- **Raster Data:**
  - DEM (DEMNAS) - Topography
  - Bathymetry (BATNAS, GEBCO) - Seafloor

---

## 🧪 How to Use

### Simulasi Tsunami

1. **Pilih Sumber Gempa**
   - **Patahan**: Pilih dari daftar sesar aktif (F1-F15)
   - **Megathrust**: Pilih zona megathrust (M1-M15)
   - **Custom**: Klik peta untuk menentukan episentrum

2. **Atur Parameter**
   - Magnitudo (5.0 - 9.5 Mw)
   - Jenis sesar (Vertikal/Horizontal)

3. **Jalankan Simulasi**
   - Klik "JALANKAN SIMULASI (SWE NUMERIK)"
   - Tunggu progress bar selesai
   - Hasil akan tampil di peta

### Analisis Rute Evakuasi

1. **Pilih Titik Asal**
   - Klik "Pilih titik asal di peta"
   - Klik lokasi di peta

2. **Pilih Tujuan**
   - Pilih TES dari dropdown

3. **Pilih Moda Transportasi**
   - Jalan kaki / Motor / Mobil

4. **Analisis Rute**
   - Klik "ANALISIS RUTE EVAKUASI"
   - Rute akan tampil di peta

### Simulasi ABM

1. **Pastikan SWE Sudah Dijalankan**
   - ABM membutuhkan data inundasi dari simulasi tsunami

2. **Jalankan ABM**
   - Klik "JALANKAN SIMULASI ABM"
   - Parameter menggunakan default (warning time, duration, flood height)
   - Agen akan bergerak di peta

---

## 📁 Data Management

### Data Location
```
src/backend/data/
├── Raster/
│   ├── BATNAS/              # Batimetri nasional
│   ├── DEMNAS/              # Digital Elevation Model (Jawa-Bali)
│   └── GEBCO/               # Bathymetry global
└── Vektor/
    ├── Administrasi_Desa.*  # Batas desa
    ├── Garis_Pantai_Selatan.* # Garis pantai
    ├── Jalan_Bantul.*       # Jaringan jalan
    ├── Koordinat_TES.*      # Lokasi TES
    ├── TES_Bantul.*         # TES Bantul
    ├── Pemukiman.geojson    # Permukiman
    ├── SESAR-PUSGEN/        # Data sesar aktif
    │   └── SHARE_INPUT_V1_2/
    │       └── 2016_JAVA-FaultModel_v1_2.* # Sesar Jawa
    └── INA_Megathrust.*     # Zona megathrust
```

⚠️ **Data files tidak disertakan dalam repository** karena ukuran besar.

**Untuk memperoleh data:**
- BATNAS: Bakosurtanal
- DEMNAS: BIG (Tanahair Indonesia)
- GEBCO: https://www.gebco.net/
- SESAR-PUSGEN: Pusgen (2016) v1.2
- Megathrust: Indonesian megathrust geometry

---

## 🔧 Configuration

### Backend Configuration

**File:** `src/backend/server.py`
```python
# Data paths (auto-configured)
DATA_DIR = "data"
RASTER_DIR = os.path.join(DATA_DIR, "Raster")
VEKTOR_DIR = os.path.join(DATA_DIR, "Vektor")
```

**Frontend API:**
```typescript
// src/frontend/services/api.ts
const API_BASE = "http://localhost:8000";
```

---

## 📚 API Endpoints

### Simulation Endpoints

#### Run Tsunami Simulation
```http
POST /api/simulate
Content-Type: application/json

{
  "magnitude": 7.5,
  "fault_type": "vertical",
  "fault_id": "F3",
  "source_mode": "fault",
  "depth": 15,
  "length": 100,
  "rake": 0,
  "lat": -8.0,
  "lon": 110.28
}
```

#### Calculate Evacuation Routes
```http
POST /api/routing
Content-Type: application/json

{
  "transport": "foot",
  "speed_kmh": 4,
  "safety_weight": 25,
  "tes_id": "TES-01",
  "origin_lat": -8.0,
  "origin_lon": 110.28
}
```

#### Run ABM Simulation
```http
POST /api/abm
Content-Type: application/json

{
  "warning_time_min": 20,
  "sim_duration_min": 120,
  "flood_height_m": 5,
  "transport": "foot"
}
```

### Data Endpoints

```http
GET /api/data/desa          # Village boundaries
GET /api/data/tes           # TES locations
GET /api/data/faults        # Fault list with metadata
GET /api/geodata/faults      # Fault GeoJSON
GET /api/geodata/megathrust  # Megathrust GeoJSON
GET /api/status              # Backend server status
```

---

## 🎯 Recent Updates (April 2025)

### UI/UX Improvements
- ✅ **Theme Overhaul**: Changed from neon/cyberpunk to clean academic theme
  - Color palette: Blue (#3b82f6), White (#ffffff), Yellow (#f59e0b)
  - Typography: Plus Jakarta Sans
  - Improved contrast and readability

- ✅ **Logo Update**: Replaced with UGM logo

- ✅ **Unified Control Panel**:
  - Single panel with tab navigation
  - Eliminated duplicate fault selection
  - Cleaner, more intuitive workflow

- ✅ **Enhanced Spacing**: Proper padding and margins throughout

### Feature Enhancements
- ✅ **Megathrust Support**: Backend now loads megathrust zones (Polygon geometry)
- ✅ **Fault Selection with Zoom**: Auto-zoom to selected fault with highlight
- ✅ **Custom Epicenter**: Interactive point picker on map
- ✅ **ABM Integration**: ABM uses SWE inundation data for hazard-aware routing
- ✅ **Layer Control**: Toggleable layers with proper defaults
- ✅ **Export Panel**: Export results in multiple formats

### Bug Fixes
- ✅ Fixed `onFaultSelect is not defined` error
- ✅ Fixed `localSelectedFault is not defined` error
- ✅ Fixed megathrust data loading (Polygon support)
- ✅ Fixed text contrast issues (light text on dark backgrounds)
- ✅ Fixed button sizing (routing/ABM buttons now same size as SWE button)

---

## 🐛 Troubleshooting

### Backend Issues
| Problem | Solution |
|---------|----------|
| "ModuleNotFoundError" | `pip install -r requirements.txt` |
| "Port 8000 already in use" | Kill process or use different port |
| "Data files not found" | Ensure data files are in `src/backend/data/` |
| "Megathrust not loading" | Check if `INA_Megathrust.shp` uses Polygon geometry |
| "Fault selection error" | Verify fault shapefile exists and is valid |

### Frontend Issues
| Problem | Solution |
|---------|----------|
| "Dependencies not installed" | `npm install` |
| "Port 3000 conflict" | `npm run dev -- -p 3001` |
| "API not connecting" | Check backend is running & CORS is enabled |
| "Map not loading" | Check browser console for errors |
| "Layers not visible" | Ensure data is loaded from backend |

---

## 📝 References

### Scientific Papers
- Okada, Y. (1985). Surface deformation due to shear and tensile faults in a half-space. *Bull. Seismol. Soc. Am.*, 75(4), 1135-1154.
- Wang, X. (2009). *COMCOT Manual*. University of Canterbury.
- Synolakis, C. (1987). The runup of solitary waves. *J. Fluid Mech.*, 185, 523-545.
- Wells, D. L., & Coppersmith, K. J. (1994). New empirical relationships among magnitude, rupture length, rupture width, rupture area, and surface displacement. *Bull. Seismol. Soc. Am.*, 84(4), 974-1002.

### GIS Data Sources
- **BATNAS:** Bakosurtanal (2012) - Batimetri Nasional
- **DEMNAS:** BIG (2020) - Digital Elevation Model Nasional
- **GEBCO:** GEBCO Compilation Group (2023) - General Bathymetric Chart of the Oceans
- **SESAR-PUSGEN:** Pusgen (2016) - Indonesian Seismic Hazard Model v1.2

### Technologies Used
- **Backend:** Python, FastAPI, GeoPandas, NumPy, SciPy
- **Frontend:** Next.js 15, React, TypeScript, Leaflet, Tailwind CSS
- **GIS:** GDAL, PROJ, Shapely, Fiona

---

## 📄 License

Komgeo Kel. 3 - Magister Teknik Geomatika UGM
© 2024-2025

---

## ✉️ Contact & Support

**Untuk pertanyaan teknis atau data:**
- Hubungi salah satu anggota kelompok
- Repository: [GitHub](https://github.com/your-repo)

---

**Last Updated:** April 27, 2025
**Project Status:** Active Development
**Version:** 1.0.0

---

## 🙏 Acknowledgments

- Dosen Mata Kuliah Komputasi Geospasial MTG UGM
- Pusat Studi Gunung Api dan Mitigasi Bencana Geologi (PVMBG)
- Badan Informasi Geospasial (BIG)
- Pusat Vulkanologi dan Mitigasi Bencana Geologi (PVMBG)
