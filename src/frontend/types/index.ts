// ═══════════════════════════════════════════════
//  TYPES — WebGIS Tsunami
//  Semua tipe data yang dipakai frontend ↔ backend
// ═══════════════════════════════════════════════

// ── Parameter Simulasi (dikirim ke backend) ──────────────────────
export interface SimulationParams {
  magnitude: number;        // Mw (5.0 – 9.5)
  fault_type: 'vertical' | 'horizontal';
  fault_id: string | null;  // ID sesar yang dipilih
  source_mode: 'fault' | 'mega' | 'custom';
  depth_km?: number;        // opsional, kedalaman hiposenter
  lat?: number;             // untuk custom mode
  lon?: number;
}

export interface RoutingParams {
  transport: 'foot' | 'motor' | 'car';
  speed_kmh: number;
  safety_weight: number;    // 0–60, bobot prioritas elevasi
  origin_lat?: number;
  origin_lon?: number;
  tes_id?: string;
}

export interface ABMParams {
  warning_time_min: number;   // waktu peringatan (mnt)
  sim_duration_min: number;   // durasi simulasi (mnt)
  flood_height_m: number;     // tinggi banjir inundasi
  transport: 'foot' | 'motor' | 'car';
}

// ── Hasil Simulasi SWE ──────────────────────────────────────────
export interface WavePathPoint {
  distance_km: number;
  arrival_time_min: number;
  wave_height_m: number;
  speed_kmh: number;
  source: 'BATNAS' | 'GEBCO' | 'BLEND';
}

export interface SWEResult {
  wave_path: WavePathPoint[];
  max_inundation_m: number;
  arrival_time_min: number;
  affected_area_km2: number;
  inundation_geojson?: GeoJSON.FeatureCollection;
}

// ── Data Desa & Dampak ──────────────────────────────────────────
export interface VillageImpact {
  kelurahan: string;
  population: number;
  terdampak: number;
  percentage: number;
  zona_bahaya: 'Sangat Tinggi' | 'Tinggi' | 'Sedang' | 'Rendah';
  color: string;
  coordinates: [number, number]; // [lat, lon]
  geom?: GeoJSON.Geometry;
}

export interface ImpactSummary {
  total_terdampak: number;
  zona_sangat_tinggi: number;
  zona_tinggi: number;
  zona_sedang: number;
  zona_rendah: number;
}

export interface ImpactResult {
  summary: ImpactSummary;
  affected_villages: VillageImpact[];
  chart_data: {
    donut: { label: string; value: number; color: string }[];
  };
}

// ── Data Admin (Desa & TES) ─────────────────────────────────────
export interface DesaData {
  name: string;
  lat: number;
  lon: number;
  geom?: GeoJSON.Geometry;
}

export interface TESData {
  id: string;
  name: string;
  lat: number;
  lon: number;
  kapasitas: number;
  props?: Record<string, string>;
}

// ── Rute Evakuasi ───────────────────────────────────────────────
export interface EvacuationRoute {
  desa: string;
  target_tes: string;
  route_path: [number, number][];
  distance_km: number;
  walk_time_min: number;
  can_evacuate: boolean;
  status: 'optimal' | 'alternatif' | 'darurat';
  color: string;
  score?: number;
}

export interface RoutingResult {
  routes: EvacuationRoute[];
  summary: {
    total_routes: number;
    can_evacuate: number;
    cannot_evacuate: number;
    success_rate: number;
  };
}

// ── Hasil ABM ───────────────────────────────────────────────────
export interface ABMFrame {
  time_min: number;
  agents: {
    id: string;
    lat: number;
    lon: number;
    status: 'evacuating' | 'safe' | 'trapped';
  }[];
}

export interface ABMResult {
  total_agents: number;
  safe_count: number;
  trapped_count: number;
  avg_evacuation_time_min: number;
  frames: ABMFrame[];
}

// ── Status Server ───────────────────────────────────────────────
export type ServerStatus = 'online' | 'offline' | 'checking';
