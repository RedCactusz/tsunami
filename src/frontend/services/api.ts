/**
 * API Service untuk komunikasi dengan Backend
 * ❌ SEMUA MOCK DATA DIHAPUS - Hanya menggunakan data asli dari backend
 * ℹ️  Kalau backend error/offline → return error / empty data (bukan mock)
 */

import type {
  ABMParams,
  ABMResult,
  DesaData,
  ImpactResult,
  RoutingParams,
  RoutingResult,
  ServerStatus,
  SimulationParams,
  SWEResult,
  TESData,
} from "@/types";

const SERVER_URL =
  process.env.NEXT_PUBLIC_SERVER_URL || "http://localhost:8000";

// ════════════════════════════════════════════════
//  HELPER: Fetch dengan timeout
// ════════════════════════════════════════════════

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout = 30000,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`Request timeout after ${timeout}ms`);
    }
    throw err;
  }
}

// ════════════════════════════════════════════════
//  CEK STATUS SERVER
// ════════════════════════════════════════════════

export async function checkServerStatus(): Promise<ServerStatus> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/`);
    return res.ok ? "online" : "offline";
  } catch {
    return "offline";
  }
}

// ════════════════════════════════════════════════
//  API FUNCTIONS - NO MOCK DATA
//  ❌ Kalau backend error → throw exception / return empty
// ════════════════════════════════════════════════

// ── /simulate → SWE + Impact ─────────────────────────────────────
export async function runSimulation(
  params: SimulationParams,
): Promise<{ swe: SWEResult; impact: ImpactResult; isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();

    return {
      swe: data.swe ?? data,
      impact: data.impact ?? {},
      isMock: false,
    };
  } catch (err) {
    console.error("[API] /simulate ERROR:", err);
    // ❌ NO MOCK DATA - Throw error untuk frontend handle
    throw new Error(
      `Gagal menjalankan simulasi: ${err instanceof Error ? err.message : "Unknown error"}`,
    );
  }
}

// ── /routing → Rute Evakuasi ─────────────────────────────────────
export async function runRouting(
  params: RoutingParams,
): Promise<RoutingResult & { isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/routing`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    console.log("[API] /routing response:", data);
    return { ...data, isMock: false };
  } catch (err) {
    console.error("[API] /routing ERROR:", err);
    // ❌ NO MOCK DATA
    throw new Error(
      `Gagal menghitung rute evakuasi: ${err instanceof Error ? err.message : "Unknown error"}`,
    );
  }
}

// ── /abm → Simulasi ABM ──────────────────────────────────────────
export async function runABM(
  params: ABMParams,
): Promise<ABMResult & { isMock: boolean }> {
  try {
    // ABM simulation timeout dengan graph routing
    // Graph routing mode (Dijkstra): ~2-3 menit untuk 258 agents (129 routes)
    // Timeout 180 detik (3 menit) untuk accommodate graph routing
    const res = await fetchWithTimeout(
      `${SERVER_URL}/abm`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      },
      300000,
    ); // 180 seconds (3 menit) timeout untuk graph routing

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    return { ...data, isMock: false };
  } catch (err) {
    console.error("[API] /abm ERROR:", err);
    // ❌ NO MOCK DATA
    throw new Error(
      `Gagal menjalankan simulasi ABM: ${err instanceof Error ? err.message : "Unknown error"}`,
    );
  }
}

// ── /admin/desa → Data Batas Desa ────────────────────────────────
export async function fetchDesa(): Promise<{
  desa: DesaData[];
  isMock: boolean;
}> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/admin/desa`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    return { desa: data.desa ?? [], isMock: false };
  } catch (err) {
    console.error("[API] /admin/desa ERROR:", err);
    // ❌ NO MOCK DATA - Return empty array
    return { desa: [], isMock: false };
  }
}

// ── /admin/tes → Data TES ────────────────────────────────────────
export async function fetchTES(): Promise<{ tes: TESData[]; isMock: boolean }> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/admin/tes`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    return { tes: data.tes ?? [], isMock: false };
  } catch (err) {
    console.error("[API] /admin/tes ERROR:", err);
    // ❌ NO MOCK DATA - Return empty array
    return { tes: [], isMock: false };
  }
}

// ── /admin/faults → Data Fault dari Shapefile ─────────────────────
export async function getFaultList(): Promise<{
  faults: Record<
    string,
    {
      label: string;
      mw: number;
      category: string;
      recurrence: string;
      view_lat: number;
      view_lon: number;
      view_zoom: number;
    }
  >;
  source: string;
  isMock: boolean;
}> {
  try {
    const res = await fetchWithTimeout(`${SERVER_URL}/admin/faults`, {
      method: "GET",
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    return {
      faults: data.faults ?? {},
      source: data.source ?? "unknown",
      isMock: false,
    };
  } catch (err) {
    console.error("[API] /admin/faults ERROR:", err);
    // ❌ NO MOCK DATA - Return empty object
    return {
      faults: {},
      source: "error",
      isMock: false,
    };
  }
}
