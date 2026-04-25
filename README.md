# WebGIS Tsunami Simulation & Evacuation Analysis
**Simulasi Tsunami dan Analisis Evakuasi Berbasis WebGIS**

---

## 📋 Project Information

**Mata Kuliah:** Komputasi Geospasial  
**Program:** Magister Teknik Geomatika, Universitas Gadjah Mada  
**Kelompok:** 3  
**Tahun Akademik:** 2025/2026

---

## 👥 Anggota Kelompok

| No | Nama | NIM | Peran |
|-----|------|-----|------|
| 1 | Muhammad Rouf Indhra Dewa S | 24/552974/PTK/16494 | Lead Developer, Backend Architecture |
| 2 | Zulfikar Baihakki Budiyono | 25/568388/PTK/16751 | Full-Stack Developer |
| 3 | Oktavia Nutivara Waskito | 25/562735/PTK/16612 | Frontend & Visualization |
| 4 | Saffira Noor Chotimah | 25/563053/PTK/16640 | GIS Analysis & Data Processing |
| 5 | Frans Waas | 25/566567/PTK/16709 | Simulation & Algorithm |
| 6 | Iman Taufiqqurrahman | 25/569788/PTK/16971 | Testing & Documentation |

---

## 🎯 Project Overview

Aplikasi WebGIS terintegrasi untuk:
1. **Simulasi Tsunami** - Model numerik propagasi tsunami menggunakan Shallow Water Equation (SWE)
2. **Analisis Evakuasi** - Agent-Based Modeling (ABM) untuk simulasi pergerakan evakuasi penduduk
3. **Spatial Analysis** - Analisis jaringan jalan, zona genangan, dan lokasi TES (Tempat Evakuasi Sementara)
4. **Visualisasi Interaktif** - Dashboard WebGIS dengan Leaflet untuk visualisasi real-time

---

## 🏗️ Project Architecture

```
tsunami/
├── src/
│   ├── backend/               # FastAPI Backend
│   │   ├── server.py          # API Gateway & Orchestration
│   │   ├── swe_solver.py      # Tsunami SWE Simulation
│   │   ├── evacuation_abm.py  # Evacuation ABM Solver
│   │   ├── simulation/
│   │   │   └── core/
│   │   │       ├── cache.py   # Data Caching
│   │   │       ├── spatial_utils.py
│   │   │       ├── swe_solver.py
│   │   │       └── evacuation_abm.py
│   │   ├── data/              # GIS Data
│   │   │   ├── Raster/        # Bathymetry, DEM
│   │   │   └── Vektor/        # Shapefile (Faults, Roads, etc)
│   │   ├── venv/              # Python Virtual Environment
│   │   └── requirements.txt
│   │
│   └── frontend/              # Next.js Frontend
│       ├── app/               # App Router
│       ├── components/        # React Components
│       ├── services/          # API Client
│       ├── types/             # TypeScript Definitions
│       ├── hooks/             # Custom Hooks
│       └── public/            # Static Assets
│
└── README.md
```

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
- **API Swagger UI:** http://localhost:8000/redoc

---

## 📊 Core Features

### 1. Tsunami Simulation
- **Model Numerik:** Shallow Water Equation (SWE) linear & nonlinear
- **Sumber Tsunami:** Fault rectangular (Okada 1985) & Megathrust interplate
- **Bathymetry Data:** BATNAS, GEBCO, DEMNAS
- **Output:** Wave frames, inundation zones, runup estimates

### 2. Evacuation Analysis
- **Network Analysis:** Shortest path ke TES menggunakan Dijkstra/A*
- **Population Distribution:** Dasymetric mapping dari kelurahan ke building
- **ABM Simulation:** Agent movement dengan traffic congestion model
- **Output:** Evacuation routes, arrival times, stranded population

### 3. GIS Data Integration
- **Vector Data:** Fault lines, roads, villages, TES locations, coastline
- **Raster Data:** DEM, bathymetry grids
- **Format:** Shapefile, GeoTIFF

### 4. Interactive Visualization
- **Map Dashboard:** Leaflet-based interactive map
- **Real-time Results:** SWE animation, ABM agent tracking
- **Data Layers:** Toggleable fault lines, inundation zones, evacuation routes
- **Statistics:** Charts & analytics panel

---

## 📁 Data Management

### Data Location
```
src/backend/data/
├── Raster/
│   ├── BATNAS/              # Batimetri nasional
│   ├── DEMNAS/              # Digital Elevation Model
│   └── GEBCO/               # Bathymetry global
└── Vektor/
    ├── Administrasi_Desa.shp*
    ├── Garis_Pantai_Selatan.shp*
    ├── Jalan_Bantul.shp*
    ├── Koordinat_TES.shp*
    ├── TES_Bantul.shp*
    ├── Bangunan Bantul/
    └── SESAR-PUSGEN (2)/
        └── SHARE_INPUT_V1_2/
            ├── 2016_JAVA-FaultModel_v1_2.shp*
            ├── 2016_SUM_FaultModel_v1_2.shp*
            ├── 2016_Sulawesi*.shp*
            ├── INA_Megathrust.shp*
            └── ...
```
*Format: Shapefile (.shp, .dbf, .prj, .shx, dll)

### Data Acquisition

⚠️ **Data files tidak disertakan dalam repository** karena ukuran besar.

**Untuk memperoleh data, hubungi:**

```
📧 Email: 

📋 Data yang diminta:
   - Bathymetry (BATNAS, GEBCO)
   - DEM (Jawa-Bali)
   - Shapefile Vektor (semua layer)
   - Fault data (SESAR-PUSGEN v1.2)
```

---

## 🔧 Configuration

### Backend Configuration (server.py)

```python
# Data paths (auto-configured)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RASTER_DIR = os.path.join(DATA_DIR, "Raster")
VEKTOR_DIR = os.path.join(DATA_DIR, "Vektor")
BATNAS_DIR = os.path.join(RASTER_DIR, "BATNAS")
GEBCO_DIR = os.path.join(RASTER_DIR, "GEBCO_18_Mar_2026_54f29d9cc882")
DEMNAS_DIR = os.path.join(RASTER_DIR, "DEMNAS")
```

### Frontend Configuration (services/api.ts)

```typescript
// API Base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Endpoints
const ENDPOINTS = {
  simulate: "/api/simulate",
  routing: "/api/routing",
  desa: "/api/data/desa",
  tes: "/api/data/tes"
};
```

---

## 📚 API Endpoints

### Simulation
- `POST /api/simulate` - Run tsunami simulation
  ```json
  {
    "epicenter_lat": -8.0,
    "epicenter_lon": 110.28,
    "magnitude": 7.5,
    "duration": 3600,
    "fault_type": "vertical"
  }
  ```

### Routing & Evacuation
- `POST /api/routing` - Calculate evacuation routes
- `GET /api/data/desa` - Get village data
- `GET /api/data/tes` - Get TES locations

### Data Serving
- `GET /api/geodata/faults` - Fault GeoJSON
- `GET /api/geodata/megathrust` - Megathrust GeoJSON
- `GET /api/geodata/coastline` - Coastline GeoJSON

---

## 🧪 Development

### Running Tests (Backend)
```bash
cd src/backend
pytest tests/
```

### Building Frontend
```bash
cd src/frontend
npm run build
npm start  # Production build
```

### Code Structure
- **Backend:** Modular architecture dengan separation of concerns
  - `server.py` → API Gateway
  - `simulation/core/` → Business logic
  
- **Frontend:** Next.js App Router with TypeScript
  - `services/` → API clients
  - `components/` → UI Components
  - `hooks/` → State management

---

## 📖 Documentation

### Backend API Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Code Comments
- Semua function memiliki docstring (in Indonesian/English)
- Type hints untuk Python dan TypeScript

### Project Wiki
Lihat dokumentasi detail di folder `src/frontend/README.md` dan `src/backend/simulation/`

---

## 🐛 Troubleshooting

### Backend Issues
| Problem | Solution |
|---------|----------|
| "ModuleNotFoundError" | `pip install -r requirements.txt` |
| "Port 8000 already in use" | `lsof -i :8000` & kill process or use different port |
| "Data files not found" | Pastikan file data ada di `src/backend/data/` |

### Frontend Issues
| Problem | Solution |
|---------|----------|
| "Dependencies not installed" | `npm install` |
| "Port 3000 conflict" | `npm run dev -- -p 3001` |
| "API not connecting" | Check backend is running & `NEXT_PUBLIC_API_URL` correct |

---

## 📝 References

### Scientific Papers
- Okada, Y. (1985). Surface deformation due to shear and tensile faults in a half-space. *Bull. Seismol. Soc. Am.*, 75(4), 1135-1154.
- Wang, X. (2009). *COMCOT Manual*. University of Canterbury.
- Synolakis, C. (1987). The runup of solitary waves. *J. Fluid Mech.*, 185, 523-545.
- Wells, D. L., & Coppersmith, K. J. (1994). New empirical relationships among magnitude, rupture length, rupture width, rupture area, and surface displacement. *Bull. Seismol. Soc. Am.*, 84(4), 974-1002.

### GIS Data Sources
- **BATNAS:** Bakosurtanal (2012)
- **GEBCO:** GEBCO compilation v2023
- **SESAR-PUSGEN:** Indonesian Fault Model v1.2

---

## 📄 License

Komgeo Kel. 3 - Magister Teknik Geomatika UGM  
©2025-2026

---

## ✉️ Contact & Support

**Untuk pertanyaan teknis atau data:**
- Hubungi salah satu anggota kelompok
- Email: ...

---

**Last Updated:** April 24, 2026  
**Project Status:** Development
