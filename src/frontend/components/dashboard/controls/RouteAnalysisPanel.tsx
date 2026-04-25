'use client';

import React, { useState } from 'react';
import type { RoutingParams, TESData } from '@/types';
import TransportModeSelector from './TransportModeSelector';
import SafetyWeightSlider from './SafetyWeightSlider';

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
    <>
      <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
        <div className="flex items-center gap-2 p-2 rounded-md mb-3" style={{
          background: 'rgba(0, 18, 45, 0.6)',
          border: '1px solid var(--border2)',
        }}>
          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{
            background: '#4ade80',
            boxShadow: '0 0 6px #4ade80',
          }} />
          <span className="flex-1 text-xs" style={{ color: 'var(--muted)' }}>
            Data jalan OSM dimuat
          </span>
          <button className="text-xs px-2 py-1 rounded border font-semibold transition-all" style={{
            background: 'rgba(56, 189, 248, 0.12)',
            borderColor: 'rgba(56, 189, 248, 0.25)',
            color: 'var(--accent)',
          }}>
            🔄 Muat
          </button>
        </div>
      </div>

      <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
        <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
          Titik Asal & Tujuan
        </div>

        <div className="mb-2">
          <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>📍 Titik Asal (Zona Bahaya)</div>
          <button
            onClick={onPickOriginToggle}
            className="w-full flex items-center gap-2 px-2 py-2 rounded-md border-2 font-semibold text-xs"
            style={{
              borderColor: customOrigin ? 'var(--accent)' : 'var(--accent)',
              borderStyle: customOrigin ? 'solid' : 'dashed',
              background: isPickingOrigin ? 'rgba(56, 189, 248, 0.2)' : 'rgba(56, 189, 248, 0.12)',
              color: 'var(--accent)',
            }}
          >
            {isPickingOrigin ? '🖱️ Klik peta — pilih titik asal...' : customOrigin ? '✅ ' + customOrigin.lat.toFixed(5) + '°, ' + customOrigin.lon.toFixed(5) + '°' : '🖱️ Klik peta untuk tentukan titik asal'}
          </button>
          {customOrigin && (
            <button
              onClick={onResetOrigin}
              className="w-full mt-1 py-1 px-2 rounded text-xs"
              style={{
                background: 'rgba(246, 95, 95, 0.08)',
                border: '1px solid rgba(248, 113, 113, 0.18)',
                color: '#f87171',
              }}
            >
              Reset titik asal
            </button>
          )}
        </div>

        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>🏁 Titik Tujuan (TES)</div>
          <select
            value={selectedTesId || ''}
            onChange={(e) => setSelectedTesId(e.target.value || null)}
            className="w-full text-xs"
            style={{ background: 'rgba(0, 15, 40, 0.55)', color: 'var(--text)', borderColor: 'var(--border)' }}
          >
            <option value="">— Pilih TES —</option>
            {tesList.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
        <TransportModeSelector
          selectedMode={transportMode}
          onModeChange={onTransportModeChange}
        />
      </div>

      <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
        <SafetyWeightSlider
          value={safetyWeight}
          onChange={onSafetyWeightChange}
        />
      </div>

      <div className="mb-4 pb-4">
        <button
          type="button"
          onClick={handleAnalyzeRoutes}
          disabled={isLoading}
          className="w-full py-2 rounded-lg font-bold text-xs uppercase text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            background: 'linear-gradient(135deg, #064e3b, #059669)',
            boxShadow: '0 4px 18px rgba(5, 150, 105, 0.3)',
            letterSpacing: '1px',
          }}
        >
          🛣 ANALISIS RUTE EVAKUASI
        </button>
      </div>

      <div className="pb-4">
        <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
          Titik Evakuasi Sementara (TES)
          <span className="float-right font-bold" style={{ color: 'var(--ok)' }}>2.450</span>
        </div>
        <div className="flex flex-col gap-2 max-h-40 overflow-y-auto">
          {tesList.map((t) => (
            <div
              key={t.id}
              className="p-2 rounded-md border text-xs cursor-pointer transition-all"
              style={{
                background: 'rgba(0, 15, 40, 0.4)',
                borderColor: 'rgba(56, 189, 248, 0.08)',
                color: 'var(--text)',
              }}
            >
              <div className="font-semibold">{t.name}</div>
              <div style={{ color: 'var(--muted)', marginTop: '2px' }}>
                Kapasitas: {t.kapasitas} orang
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
