'use client';

import type { RoutingParams, TESData } from '@/types';

interface RouteAnalysisPanelProps {
  transportMode: 'foot' | 'motor' | 'car';
  onTransportModeChange: (mode: 'foot' | 'motor' | 'car') => void;
  safetyWeight: number;
  onSafetyWeightChange: (weight: number) => void;
  onAnalyzeRoutes?: (params: RoutingParams) => Promise<void>;
  isLoading?: boolean;
  tesList?: TESData[];
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
}: RouteAnalysisPanelProps) {
  const handleAnalyzeRoutes = async () => {
    if (!onAnalyzeRoutes) return;

    const params: RoutingParams = {
      transport: transportMode,
      speed_kmh: transportMode === 'foot' ? 4 : transportMode === 'motor' ? 30 : 40,
      safety_weight: safetyWeight,
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
          <button className="w-full flex items-center gap-2 px-2 py-2 rounded-md border-2 border-dashed font-semibold text-xs" style={{
            borderColor: 'var(--accent)',
            background: 'rgba(56, 189, 248, 0.12)',
            color: 'var(--accent)',
          }}>
            🖱️ Klik peta untuk tentukan titik asal
          </button>
        </div>

        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>🏁 Titik Tujuan (TES)</div>
          <select className="w-full text-xs" style={{ background: 'rgba(0, 15, 40, 0.55)', color: 'var(--text)', borderColor: 'var(--border)' }}>
            <option>— Pilih TES —</option>
            {tesList.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
        <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
          Moda Transportasi
        </div>
        <div className="grid grid-cols-3 gap-2">
          {transportModes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => onTransportModeChange(mode.id as any)}
              className="p-2 rounded-md border text-xs font-bold text-center transition-all"
              style={{
                background: transportMode === mode.id ? 'rgba(56, 189, 248, 0.14)' : 'rgba(0, 15, 40, 0.5)',
                borderColor: transportMode === mode.id ? 'var(--accent)' : 'var(--border)',
                color: transportMode === mode.id ? 'var(--accent)' : 'var(--muted)',
              }}
            >
              <div className="text-lg mb-1">{mode.icon}</div>
              {mode.label}
            </button>
          ))}
        </div>

        <div className="mt-2 text-xs p-2 rounded-md" style={{
          background: 'rgba(0, 18, 45, 0.5)',
          color: 'var(--muted)',
          lineHeight: '1.7',
        }}>
          🚶 <b style={{ color: 'var(--accent)' }}>Jalan Kaki</b> — Kecepatan ~4 km/j. Jalur kaki lebih fleksibel.
        </div>
      </div>

      <div className="mb-4 pb-4">
        <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
          Metode Analisis
        </div>

        <div className="p-2 rounded-md mb-2" style={{
          background: 'rgba(56, 189, 248, 0.07)',
          border: '1px solid rgba(56, 189, 248, 0.2)',
        }}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm">🛣</span>
            <span className="text-xs font-bold" style={{ color: 'var(--accent)' }}>Jalur Terpendek + DEM</span>
            <span className="ml-auto text-xs px-2 py-1 rounded" style={{
              background: 'rgba(74, 222, 128, 0.15)',
              color: '#4ade80',
            }}>
              ✓ Aktif
            </span>
          </div>
          <div className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>
            Network analysis dengan <b style={{ color: 'var(--text)' }}>composite cost</b>: bobot jarak, waktu tempuh, <b style={{ color: '#34d399' }}>elevasi DEM</b>, dan <b style={{ color: '#a78bfa' }}>kemiringan lereng</b>.
          </div>
        </div>

        <div className="mb-3">
          <div className="flex justify-between items-center text-xs mb-1">
            <span>⛰ Prioritas Elevasi & Slope</span>
            <span style={{ color: 'var(--accent)', fontWeight: 'bold' }}>{safetyWeight}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="60"
            value={safetyWeight}
            onChange={(event) => onSafetyWeightChange(parseInt(event.target.value, 10))}
            className="w-full"
            style={{ accentColor: '#4ade80' }}
          />
        </div>

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
