# WebGIS Tsunami UI - Rewrite ke Next.js

## 📋 Overview

UI dari `old_project/index.html` telah ditulis ulang ke React/Next.js framework dengan struktur yang lebih modular dan maintainable.

## 🎨 Design System

### Color Palette (Dark Theme)
```
Background:   #060d1b
Panel:        #0a1628, #0d1d35
Accent:       #38bdf8 (Cyan Primary)
Secondary:    #0ea5e9
Text:         #ddeeff
Muted:        rgba(148, 200, 240, 0.55)
Status OK:    #34d399
Status Warn:  #fbbf24
Status Error: #f87171
```

### Typography
- Primary: Plus Jakarta Sans (400, 500, 600, 700, 800)
- Mono: JetBrains Mono (400, 600) - untuk numeric values

### Layout
```
┌─────────────────────────────────────────────────┐
│                    HEADER (auto)                │
├─────────────┬──────────────────────┬────────────┤
│   SIDEBAR   │                      │   RIGHT    │
│  (w-80)     │      MAP             │   PANEL    │
│             │                      │  (w-72)    │
│             ├──────────────────────┤            │
│             │   BOTTOM BAR         │            │
│             │   (h-56)             │            │
└─────────────┴──────────────────────┴────────────┘
```

## 📁 Component Structure

```
src/frontend/
├── app/
│   ├── globals.css              # Design tokens & global styles
│   ├── components.css           # Utility component classes
│   ├── layout.tsx               # Root layout
│   └── page.tsx                 # Main page
├── components/
│   ├── ui/
│   │   └── Header.tsx           # Top header with status badges
│   ├── dashboard/
│   │   ├── Sidebar.tsx          # Left control panel
│   │   ├── BottomBar.tsx        # Data visualization area
│   │   └── RightPanel.tsx       # Network analysis & ABM panel
│   └── map/
│       └── Map.tsx              # Leaflet map container
└── public/
    └── assets/                  # Logos, icons, etc
```

## 🔧 Component API

### Header
```tsx
import Header from '@/components/ui/Header';

<Header />
// Displays: Logo, Title, Status Badges (Server Data, Pre-loading, Vektor)
```

### Sidebar
```tsx
import Sidebar from '@/components/dashboard/Sidebar';

<Sidebar 
  onSimulationRun={() => console.log('Run simulation')}
/>
// Features:
// - Source selector (Fault/Megathrust/Custom)
// - Fault list with selection
// - Depth probe display
// - Magnitude slider with presets
// - Fault type buttons (Vertical/Horizontal)
// - Run simulation button
// - Layer toggles placeholder
```

### MapComponent
```tsx
import MapComponent from '@/components/map/Map';

<MapComponent 
  onBasemapChange={(basemap) => console.log(basemap)}
/>
// Features:
// - Leaflet map placeholder
// - Zoom preset buttons
// - Basemap switcher dropdown
// - Episentrum hint
```

### BottomBar
```tsx
import BottomBar from '@/components/dashboard/BottomBar';

<BottomBar simulationActive={false} />
// Displays:
// - Penduduk Terdampak table
// - Bar chart placeholder
// - Donut chart placeholder
// - Summary statistics
```

### RightPanel
```tsx
import RightPanel from '@/components/dashboard/RightPanel';

<RightPanel 
  onAnalyzeRoutes={() => console.log('Analyze')}
  onRunABM={() => console.log('Run ABM')}
/>
// Features:
// - Tab switcher (Network / ABM)
// - Network Analysis: Origin/Destination, Transport modes, Safety weight
// - ABM: Parameters and controls
```

## 🎯 Key Features Implemented

### Left Sidebar (Pemodelan Tsunami)
✅ Source selector with tabs
✅ Fault & Megathrust lists
✅ Depth probe display
✅ Magnitude slider (5-9.5) with presets
✅ Fault type selector (Vertical/Horizontal)
✅ Run simulation button
✅ Layer toggles (placeholder)

### Center Map Area
✅ Leaflet map placeholder
✅ Basemap switcher with dropdown (OSM, Satellite, Terrain)
✅ Zoom preset buttons (4 presets)
✅ Episentrum selection hint

### Bottom Bar (Data Visualization)
✅ Penduduk terdampak table
✅ Bar chart placeholder (Chart.js ready)
✅ Donut chart placeholder (Chart.js ready)
✅ Summary statistics grid

### Right Panel (Rute Evakuasi)
✅ Network Analysis tab:
  - OSM roads status
  - Origin/Destination picker
  - Transport mode selector (Jalan Kaki, Motor, Mobil)
  - Analysis method info
  - Safety weight slider
  - Analyze routes button
  - TES list display

✅ ABM Evakuasi tab:
  - Warning time input
  - Simulation duration input
  - Flood height slider
  - Transport mode selector
  - Run ABM button

## 🚀 Getting Started

### 1. Install Dependencies
```bash
cd src/frontend
npm install
```

### 2. Run Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000)

### 3. Build for Production
```bash
npm run build
npm run start
```

## 📝 Styling

### Global Styles
- `globals.css`: CSS variables, base styles, responsive utilities
- `components.css`: Component utility classes, Leaflet customization

### Using Tailwind + CSS Variables
Components use a mix of:
- Tailwind classes for layout
- CSS custom properties for theme colors (var(--accent), var(--bg), etc.)
- Inline styles for dynamic theming

Example:
```tsx
<div style={{ background: 'var(--panel)', color: 'var(--text)' }}>
  Content
</div>
```

## 🔄 Integration Points

### Backend Connection
Components export callback handlers:
```tsx
onSimulationRun()        // When "JALANKAN SIMULASI" clicked
onAnalyzeRoutes()        // When "ANALISIS RUTE" clicked
onRunABM()              // When "JALANKAN ABM" clicked
onBasemapChange()       // When basemap selected
```

### Map Integration (TODO)
- Import real Leaflet with react-leaflet
- Load GeoJSON data for faults, megathrust, villages
- Add simulation results layer
- Add evacuation routes layer

### Data Visualization (TODO)
- Integrate Chart.js for bottom bar charts
- Connect real data from backend
- Update tables with actual penduduk data

## 🎨 Customization

### Change Colors
Edit `globals.css` :root variables:
```css
:root {
  --accent: #38bdf8;  /* Primary cyan */
  --ok: #34d399;      /* Success green */
  --warn: #fbbf24;    /* Warning amber */
  /* ... etc */
}
```

### Modify Sidebar Width
Update layout in `page.tsx`:
```tsx
<Sidebar />  // Default: w-80 (320px)
```

### Adjust Bottom Bar Height
Update `page.tsx` or `BottomBar.tsx`:
```tsx
<BottomBar />  // Default: h-56 (224px)
```

## 📊 Data Structure Examples

### Fault Data
```json
{
  "id": "baribis-1",
  "name": "Baribis Kendeng F - Cirebon-1",
  "magnitude": "6.5 Mw",
  "type": "vertical"
}
```

### TES Data
```json
{
  "id": "tes-1",
  "name": "TES-01 — TES Masjid Al Huda",
  "capacity": 150,
  "lat": -7.9045,
  "lng": 110.3650
}
```

### Simulation Settings
```json
{
  "magnitude": 7.5,
  "faultType": "vertical",
  "source": "fault-id-123",
  "warningTime": 20,
  "evacuationDuration": 120
}
```

## 🚧 TODO / Future Enhancements

- [ ] Real Leaflet map integration with react-leaflet
- [ ] GeoJSON data loading (faults, megathrust, villages)
- [ ] Chart.js implementation in BottomBar
- [ ] Modal/Dialog components for result display
- [ ] Responsive design for mobile/tablet
- [ ] Keyboard shortcuts (e.g., spacebar for play/pause)
- [ ] Accessibility improvements (ARIA labels, keyboard navigation)
- [ ] Real-time simulation progress updates
- [ ] Export/download functionality
- [ ] Advanced layer controls with visibility toggles

## 🔗 Original Files Reference
- Old HTML: `old_project/index.html`
- Old Assets: `old_project/asset/`
- Old Server: `old_project/server.py`

## 📞 Support

For questions or issues with the UI rewrite:
1. Check component props and callbacks
2. Review globals.css for styling
3. Verify data structure matches expected format
4. Check browser console for errors

---

**Created**: April 21, 2026
**Framework**: Next.js 16.2.4 + React 19.2.4
**Styling**: Tailwind CSS 4 + Custom CSS Variables
**Map**: Leaflet 1.9.4 + react-leaflet 5.0.0
