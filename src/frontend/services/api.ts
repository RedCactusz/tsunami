// ═══════════════════════════════════════════════
//  services/api.ts — WebGIS Tsunami
//  Semua komunikasi ke FastAPI backend ada di sini.
//  Kalau backend offline → otomatis pakai MOCK DATA
//  sehingga UI tetap bisa didemoin tanpa backend.
// ═══════════════════════════════════════════════

import type {
  SimulationParams,
  RoutingParams,
  ABMParams,
  SWEResult,
  ImpactResult,
  RoutingResult,
  ABMResult,
  DesaData,
  TESData,
  ServerStatus,
} from '@/types';

// ── Config ───────────────────────────────────────────────────────
export const SERVER_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

const TIMEOUT_MS = 10_000; // 10 detik sebelum dianggap timeout

// ── Helper: fetch dengan timeout ─────────────────────────────────
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(id);
  }
}

// ════════════════════════════════════════════════
//  MOCK DATA — dipakai saat backend belum siap
// ════════════════════════════════════════════════

const MOCK_SWE_RESULT: SWEResult = {
  wave_path: [
    { distance_km: 0,   arrival_time_min: 0,   wave_height_m: 12.0, speed_kmh: 720, source: 'BLEND' },
    { distance_km: 5,   arrival_time_min: 0.5,  wave_height_m: 9.5,  speed_kmh: 680, source: 'BLEND' },
    { distance_km: 10,  arrival_time_min: 1.1,  wave_height_m: 7.8,  speed_kmh: 640, source: 'BATNAS' },
    { distance_km: 20,  arrival_time_min: 2.3,  wave_height_m: 5.2,  speed_kmh: 580, source: 'BATNAS' },
    { distance_km: 30,  arrival_time_min: 4.0,  wave_height_m: 3.9,  speed_kmh: 520, source: 'GEBCO' },
    { distance_km: 50,  arrival_time_min: 8.2,  wave_height_m: 2.1,  speed_kmh: 420, source: 'GEBCO' },
    { distance_km: 80,  arrival_time_min: 15.5, wave_height_m: 1.1,  speed_kmh: 340, source: 'GEBCO' },
    { distance_km: 100, arrival_time_min: 22.1, wave_height_m: 0.5,  speed_kmh: 290, source: 'GEBCO' },
  ],
  max_inundation_m: 8.3,
  arrival_time_min: 22,
  affected_area_km2: 47.5,
};

const MOCK_IMPACT_RESULT: ImpactResult = {
  summary: {
    total_terdampak: 18_420,
    zona_sangat_tinggi: 4_210,
    zona_tinggi: 7_830,
    zona_sedang: 5_180,
    zona_rendah: 1_200,
  },
  affected_villages: [
    { kelurahan: 'Gadingsari',  population: 4_250, terdampak: 2_975, percentage: 70, zona_bahaya: 'Sangat Tinggi', color: '#f87171', coordinates: [-7.998, 110.267] },
    { kelurahan: 'Srigading',   population: 3_820, terdampak: 2_674, percentage: 70, zona_bahaya: 'Sangat Tinggi', color: '#f87171', coordinates: [-7.985, 110.285] },
    { kelurahan: 'Tirtosari',   population: 3_100, terdampak: 1_860, percentage: 60, zona_bahaya: 'Tinggi',        color: '#fb923c', coordinates: [-7.975, 110.255] },
    { kelurahan: 'Poncosari',   population: 5_640, terdampak: 2_820, percentage: 50, zona_bahaya: 'Tinggi',        color: '#fb923c', coordinates: [-7.963, 110.298] },
    { kelurahan: 'Trimurti',    population: 2_900, terdampak: 1_160, percentage: 40, zona_bahaya: 'Sedang',        color: '#fbbf24', coordinates: [-7.952, 110.244] },
    { kelurahan: 'Banaran',     population: 4_100, terdampak: 1_640, percentage: 40, zona_bahaya: 'Sedang',        color: '#fbbf24', coordinates: [-7.941, 110.311] },
    { kelurahan: 'Palbapang',   population: 3_600, terdampak: 1_080, percentage: 30, zona_bahaya: 'Rendah',        color: '#a3e635', coordinates: [-7.930, 110.280] },
    { kelurahan: 'Sabdodadi',   population: 2_800, terdampak:   560, percentage: 20, zona_bahaya: 'Rendah',        color: '#a3e635', coordinates: [-7.920, 110.262] },
  ],
  chart_data: {
    donut: [
      { label: 'Zona Sangat Tinggi', value: 4_210, color: '#f87171' },
      { label: 'Zona Tinggi',        value: 7_830, color: '#fb923c' },
      { label: 'Zona Sedang',        value: 5_180, color: '#fbbf24' },
      { label: 'Zona Rendah',        value: 1_200, color: '#a3e635' },
    ],
  },
};

const MOCK_ROUTING_RESULT: RoutingResult = {
  routes: [
    {
      desa: 'Gadingsari', target_tes: 'TES-01',
      route_path: [[-7.998, 110.267], [-7.990, 110.270], [-7.983, 110.275]],
      distance_km: 2.3, walk_time_min: 35,
      can_evacuate: true, status: 'optimal', color: '#4ade80', score: 0.92,
    },
    {
      desa: 'Srigading', target_tes: 'TES-02',
      route_path: [[-7.985, 110.285], [-7.978, 110.282], [-7.971, 110.279]],
      distance_km: 3.1, walk_time_min: 47,
      can_evacuate: true, status: 'alternatif', color: '#facc15', score: 0.74,
    },
    {
      desa: 'Tirtosari', target_tes: 'TES-03',
      route_path: [[-7.975, 110.255], [-7.969, 110.260], [-7.963, 110.265]],
      distance_km: 4.7, walk_time_min: 71,
      can_evacuate: false, status: 'darurat', color: '#f87171', score: 0.31,
    },
  ],
  summary: {
    total_routes: 3,
    can_evacuate: 2,
    cannot_evacuate: 1,
    success_rate: 67,
  },
};

const MOCK_ABM_RESULT: ABMResult = {
  total_agents: 1_200,
  safe_count: 980,
  trapped_count: 220,
  avg_evacuation_time_min: 38,
  frames: [], // frame animasi kosong di mock
};

const MOCK_DESA: DesaData[] = [
  { name: 'Gadingsari',  lat: -7.998, lon: 110.267 },
  { name: 'Srigading',   lat: -7.985, lon: 110.285 },
  { name: 'Tirtosari',   lat: -7.975, lon: 110.255 },
  { name: 'Poncosari',   lat: -7.963, lon: 110.298 },
  { name: 'Trimurti',    lat: -7.952, lon: 110.244 },
];

const MOCK_TES: TESData[] = [
  { id: 'tes-1', name: 'TES-01 — Masjid Al Huda',       lat: -7.983, lon: 110.275, kapasitas: 150 },
  { id: 'tes-2', name: 'TES-02 — BPP Srandakan',        lat: -7.971, lon: 110.279, kapasitas: 200 },
  { id: 'tes-3', name: 'TES-03 — SD Muh Gunturgeni',    lat: -7.963, lon: 110.265, kapasitas: 180 },
  { id: 'tes-4', name: 'TES-04 — Balai Desa Poncosari', lat: -7.955, lon: 110.295, kapasitas: 250 },
];

// ════════════════════════════════════════════════
//  CEK STATUS SERVER
// ════════════════════════════════════════════════

export async function checkServerStatus(): Promise<ServerStatus> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/`);
    return res.ok ? 'online' : 'offline';
  } catch {
    return 'offline';
  }
}

// ════════════════════════════════════════════════
//  API FUNCTIONS
//  Tiap fungsi: coba backend dulu → kalau gagal → mock
// ════════════════════════════════════════════════

// ── /simulate → SWE + Impact ─────────────────────────────────────
export async function runSimulation(
  params: SimulationParams
): Promise<{ swe: SWEResult; impact: ImpactResult; isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    return {
      swe:    data.swe    ?? data,
      impact: data.impact ?? MOCK_IMPACT_RESULT,
      isMock: false,
    };
  } catch (err) {
    console.warn('[API] /simulate gagal, pakai mock data:', err);
    // Simulasikan sedikit variasi berdasarkan magnitude
    const factor = (params.magnitude - 5) / 4.5; // 0–1
    const mockSWE: SWEResult = {
      ...MOCK_SWE_RESULT,
      max_inundation_m:  parseFloat((MOCK_SWE_RESULT.max_inundation_m  * (0.5 + factor)).toFixed(1)),
      arrival_time_min:  Math.round(MOCK_SWE_RESULT.arrival_time_min   * (1.2 - factor * 0.4)),
      affected_area_km2: parseFloat((MOCK_SWE_RESULT.affected_area_km2 * (0.3 + factor)).toFixed(1)),
    };
    return { swe: mockSWE, impact: MOCK_IMPACT_RESULT, isMock: true };
  }
}

// ── /routing → Rute Evakuasi ─────────────────────────────────────
export async function runRouting(
  params: RoutingParams
): Promise<RoutingResult & { isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/routing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return { ...data, isMock: false };
  } catch (err) {
    console.warn('[API] /routing gagal, pakai mock data:', err);
    return { ...MOCK_ROUTING_RESULT, isMock: true };
  }
}

// ── /abm → Simulasi ABM ──────────────────────────────────────────
export async function runABM(
  params: ABMParams
): Promise<ABMResult & { isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/abm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return { ...data, isMock: false };
  } catch (err) {
    console.warn('[API] /abm gagal, pakai mock data:', err);
    return { ...MOCK_ABM_RESULT, isMock: true };
  }
}

// ── /admin/desa → Data Batas Desa ────────────────────────────────
export async function fetchDesa(): Promise<{ desa: DesaData[]; isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/admin/desa`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return { desa: data.desa ?? [], isMock: false };
  } catch (err) {
    console.warn('[API] /admin/desa gagal, pakai mock data:', err);
    return { desa: MOCK_DESA, isMock: true };
  }
}

// ── /admin/tes → Data TES ────────────────────────────────────────
export async function fetchTES(): Promise<{ tes: TESData[]; isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/admin/tes`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return { tes: data.tes ?? [], isMock: false };
  } catch (err) {
    console.warn('[API] /admin/tes gagal, pakai mock data:', err);
    return { tes: MOCK_TES, isMock: true };
  }
}
