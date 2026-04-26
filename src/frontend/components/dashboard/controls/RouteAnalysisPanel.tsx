'use client';

import { useState } from 'react';
import type { RoutingParams, TESData } from '@/types';
import TransportModeSelector from './TransportModeSelector';
// import SafetyWeightSlider from './SafetyWeightSlider'; // Hidden - Coming Soon

interface RouteAnalysisPanelProps {
  transportMode: 'foot' | 'motor' | 'car';
  onTransportModeChange: (mode: 'foot' | 'motor' | 'car') => void;
  safetyWeight: number;
  onSafetyWeightChange: (weight: number) => void;
  onAnalyzeRoutes?: (params: RoutingParams) => Promise<void>;
  isLoading?: boolean;
  tesList?: TESData[];
  customOrigin?: { lat: number; lon: number } | null;
  isPickingOrigin?: boolean;
  onPickOriginToggle?: () => void;
  onResetOrigin?: () => void;
}

const transportModes = [
  { id: 'foot', label: 'Jalan Kaki', speed: '~4 km/j', icon: '🚶' },
  { id: 'motor', label: 'Motor', speed: '~30 km/j', icon: '🏍' },
  { id: 'car', label: 'Mobil', speed: '~40 km/j', icon: '🚗' },
];

export default function RouteAnalysisPanel({
  transportMode,
  onTransportModeChange,
  safetyWeight,
  onSafetyWeightChange,
  onAnalyzeRoutes,
  isLoading = false,
  tesList = [],
  customOrigin,
  isPickingOrigin = false,
  onPickOriginToggle,
  onResetOrigin,
}: RouteAnalysisPanelProps) {
  const [selectedTesId, setSelectedTesId] = useState<string | null>(null);

  const handleAnalyzeRoutes = async () => {
    if (!onAnalyzeRoutes) return;

    const speedMap = {
      foot: 4,
      motor: 30,
      car: 40
    };

    // Gunakan TES yang dipilih, atau default ke TES-01 jika belum memilih
    const tesId = selectedTesId || tesList[0]?.id || 'TES-01';

    const params: RoutingParams = {
      transport: transportMode,
      speed_kmh: speedMap[transportMode],
      safety_weight: safetyWeight,
      tes_id: tesId,
      origin_lat: customOrigin?.lat,
      origin_lon: customOrigin?.lon,
    };

    await onAnalyzeRoutes(params);
  };

  return (
    <div className="space-y-3">
      {/* Status bar */}
      <div className="flex items-center gap-2 p-2.5 rounded-lg" style={{
        background: '#f0fdf4',
        border: '1px solid #86efac',
      }}>
        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{
          background: '#22c55e',
          boxShadow: '0 0 6px #22c55e',
        }} />
        <span className="flex-1 text-xs" style={{ color: '#166534' }}>
          Data jalan OSM dimuat
        </span>
        <span className="text-xs px-2.5 py-1 rounded-lg border font-semibold" style={{
          background: '#dcfce7',
          borderColor: '#86efac',
          color: '#15803d',
        }}>
          ✅ Ready
        </span>
      </div>

      {/* Titik Asal & Tujuan */}
      <div>
        <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
          📍 Titik Asal & Tujuan
        </div>

        <div className="mb-2">
          <button
            onClick={onPickOriginToggle}
            className="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg border font-semibold text-xs"
            style={{
              borderColor: customOrigin ? '#3b82f6' : '#cbd5e1',
              borderStyle: customOrigin ? 'solid' : 'dashed',
              background: isPickingOrigin ? '#dbeafe' : '#eff6ff',
              color: isPickingOrigin || customOrigin ? '#1d4ed8' : '#64748b',
            }}
          >
            <span className="flex-1 text-left">
              {isPickingOrigin ? '🖱️ Klik peta...' : customOrigin ? `✅ ${customOrigin.lat.toFixed(4)}°, ${customOrigin.lon.toFixed(4)}°` : '🖱️ Pilih titik asal di peta'}
            </span>
            {customOrigin && !isPickingOrigin && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onResetOrigin?.();
                }}
                className="px-2 py-1 rounded text-xs font-semibold"
                style={{
                  background: '#fee2e2',
                  color: '#dc2626',
                  border: '1px solid #fca5a5',
                }}
              >
                Reset
              </button>
            )}
          </button>
        </div>

        <div>
          <select
            value={selectedTesId || ''}
            onChange={(e) => setSelectedTesId(e.target.value || null)}
            className="w-full text-xs px-3 py-2.5 rounded-lg border"
            style={{ background: '#ffffff', color: '#1e293b', borderColor: '#cbd5e1' }}
          >
            <option value="">🏁 — Pilih Titik Tujuan (TES) —</option>
            {tesList.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Transport Mode */}
      <div>
        <TransportModeSelector
          selectedMode={transportMode}
          onModeChange={onTransportModeChange}
        />
      </div>

      {/* Safety Weight Slider - Hidden (Coming Soon)
      <div>
        <SafetyWeightSlider
          value={safetyWeight}
          onChange={onSafetyWeightChange}
        />
      </div>
      */}

      {/* Tombol Analisis */}
      <button
        type="button"
        onClick={handleAnalyzeRoutes}
        disabled={isLoading}
        className="w-full py-3.5 rounded-lg font-bold uppercase text-sm text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: isLoading
            ? 'rgba(5, 150, 105, 0.5)'
            : 'linear-gradient(135deg, #064e3b, #059669)',
          boxShadow: '0 4px 20px rgba(5, 150, 105, 0.3)',
          letterSpacing: '1px',
        }}
      >
        {isLoading ? '⏳ MENGANALISIS...' : '🛣 ANALISIS RUTE EVAKUASI'}
      </button>

      {/* Daftar TES - hanya tampilkan jika ada data */}
      {tesList.length > 0 && (
        <div className="pt-2 border-t" style={{ borderColor: '#e2e8f0' }}>
          <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
            Titik Evakuasi Sementara
            <span className="float-right font-normal" style={{ color: '#3b82f6' }}>{tesList.length} lokasi</span>
          </div>
          <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto pr-1">
            {tesList.map((t) => (
              <div
                key={t.id}
                className="p-2.5 rounded-lg border text-xs cursor-pointer transition-all hover:bg-opacity-80"
                style={{
                  background: selectedTesId === t.id ? '#dbeafe' : '#f8fafc',
                  borderColor: selectedTesId === t.id ? '#3b82f6' : '#e2e8f0',
                  color: '#1e293b',
                }}
                onClick={() => setSelectedTesId(t.id)}
              >
                <div className="font-semibold" style={{ color: selectedTesId === t.id ? '#1d4ed8' : '#3b82f6' }}>{t.name}</div>
                <div style={{ color: '#64748b', marginTop: '2px' }}>
                  Kapasitas: {t.kapasitas} orang
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
