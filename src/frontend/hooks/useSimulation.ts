// ═══════════════════════════════════════════════
//  hooks/useSimulation.ts — WebGIS Tsunami
//  Hook utama yang mengelola semua state simulasi.
//  Dipakai di page.tsx untuk mengalirkan data ke
//  Sidebar, BottomBar, RightPanel, dan Map.
// ═══════════════════════════════════════════════

'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  checkServerStatus,
  runSimulation,
  runRouting,
  runABM,
  fetchDesa,
  fetchTES,
} from '@/services/api';
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

// ── Tipe state yang dikembalikan hook ────────────────────────────
export interface SimulationState {
  // Status
  serverStatus: ServerStatus;
  isLoading: boolean;
  loadingMessage: string;
  isMockData: boolean;  // true kalau backend offline → pakai mock
  error: string | null;

  // Hasil simulasi
  sweResult:     SWEResult     | null;
  impactResult:  ImpactResult  | null;
  routingResult: RoutingResult | null;
  abmResult:     ABMResult     | null;

  // Data admin (desa & TES)
  desaList: DesaData[];
  tesList:  TESData[];

  // Flag apakah simulasi pernah dijalankan
  hasSimulated: boolean;
  hasRouted:    boolean;
  hasABM:       boolean;

  // Actions
  startSimulation: (params: SimulationParams)  => Promise<void>;
  startRouting:    (params: RoutingParams)      => Promise<void>;
  startABM:        (params: ABMParams)          => Promise<void>;
  refreshServer:   ()                           => Promise<ServerStatus>;
  resetResults:    ()                           => void;
}

// ════════════════════════════════════════════════
//  HOOK
// ════════════════════════════════════════════════
export function useSimulation(): SimulationState {
  // ── Status ────────────────────────────────────
  const [serverStatus, setServerStatus] = useState<ServerStatus>('checking');
  const [isLoading,       setIsLoading]       = useState(false);
  const [loadingMessage,  setLoadingMessage]  = useState('');
  const [isMockData,      setIsMockData]      = useState(false);
  const [error,           setError]           = useState<string | null>(null);

  // ── Hasil Simulasi ────────────────────────────
  const [sweResult,     setSweResult]     = useState<SWEResult     | null>(null);
  const [impactResult,  setImpactResult]  = useState<ImpactResult  | null>(null);
  const [routingResult, setRoutingResult] = useState<RoutingResult | null>(null);
  const [abmResult,     setAbmResult]     = useState<ABMResult     | null>(null);

  // ── Data Admin ────────────────────────────────
  const [desaList, setDesaList] = useState<DesaData[]>([]);
  const [tesList,  setTesList]  = useState<TESData[]>([]);

  // ── Flags ─────────────────────────────────────
  const [hasSimulated, setHasSimulated] = useState(false);
  const [hasRouted,    setHasRouted]    = useState(false);
  const [hasABM,       setHasABM]       = useState(false);

  // ── Cek status server ─────────────────────────
  const refreshServer = useCallback(async () => {
    setServerStatus('checking');
    const status = await checkServerStatus();
    setServerStatus(status);
    return status;
  }, []);

  // ── Load data admin saat pertama kali ─────────
  useEffect(() => {
    async function loadAdminData() {
      const [desaRes, tesRes] = await Promise.all([fetchDesa(), fetchTES()]);
      setDesaList(desaRes.desa);
      setTesList(tesRes.tes);
      if (desaRes.isMock || tesRes.isMock) setIsMockData(true);
    }
    loadAdminData();

    // Cek server setiap 30 detik
    refreshServer();
    const interval = setInterval(refreshServer, 30_000);
    return () => clearInterval(interval);
  }, [refreshServer]);

  // ── Jalankan Simulasi SWE ─────────────────────
  const startSimulation = useCallback(async (params: SimulationParams) => {
    setIsLoading(true);
    setError(null);
    setLoadingMessage('Menginisialisasi solver SWE...');

    try {
      setLoadingMessage('Memproses gelombang tsunami...');
      const result = await runSimulation(params);

      setSweResult(result.swe);
      setImpactResult(result.impact);
      setIsMockData(result.isMock);
      setHasSimulated(true);

      if (result.isMock) {
        setLoadingMessage('Selesai (mode demo — backend offline)');
      } else {
        setLoadingMessage('Simulasi SWE selesai ✓');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(`Simulasi gagal: ${msg}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Analisis Rute Evakuasi ────────────────────
  const startRouting = useCallback(async (params: RoutingParams) => {
    setIsLoading(true);
    setError(null);
    setLoadingMessage('Menganalisis jaringan jalan...');

    try {
      setLoadingMessage('Menghitung rute evakuasi...');
      const result = await runRouting(params);

      setRoutingResult(result);
      setIsMockData(result.isMock);
      setHasRouted(true);
      setLoadingMessage(result.isMock ? 'Selesai (mode demo)' : 'Analisis rute selesai ✓');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(`Routing gagal: ${msg}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Simulasi ABM ──────────────────────────────
  const startABM = useCallback(async (params: ABMParams) => {
    setIsLoading(true);
    setError(null);
    setLoadingMessage('Menginisialisasi agen ABM...');

    try {
      setLoadingMessage('Mensimulasikan pergerakan penduduk...');
      const result = await runABM(params);

      setAbmResult(result);
      setIsMockData(result.isMock);
      setHasABM(true);
      setLoadingMessage(result.isMock ? 'Selesai (mode demo)' : 'Simulasi ABM selesai ✓');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(`ABM gagal: ${msg}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Reset semua hasil ─────────────────────────
  const resetResults = useCallback(() => {
    setSweResult(null);
    setImpactResult(null);
    setRoutingResult(null);
    setAbmResult(null);
    setHasSimulated(false);
    setHasRouted(false);
    setHasABM(false);
    setError(null);
    setIsMockData(false);
  }, []);

  return {
    serverStatus,
    isLoading,
    loadingMessage,
    isMockData,
    error,
    sweResult,
    impactResult,
    routingResult,
    abmResult,
    desaList,
    tesList,
    hasSimulated,
    hasRouted,
    hasABM,
    startSimulation,
    startRouting,
    startABM,
    refreshServer,
    resetResults,
  };
}
