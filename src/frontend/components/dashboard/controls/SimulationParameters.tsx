'use client';

import type { SimulationParams } from '@/types';

interface SimulationParametersProps {
  magnitude: number;
  onMagnitudeChange: (value: number) => void;
  faultType: SimulationParams['fault_type'];
  onFaultTypeChange: (value: SimulationParams['fault_type']) => void;
  magnitudePresets: number[];
  sourceMode: SimulationParams['source_mode'];
  customEpicenter: { lat: number; lon: number } | null;
  isLoading: boolean;
  onRunSimulation: () => void;
}

export default function SimulationParameters({
  magnitude,
  onMagnitudeChange,
  faultType,
  onFaultTypeChange,
  magnitudePresets,
  sourceMode,
  customEpicenter,
  isLoading,
  onRunSimulation,
}: SimulationParametersProps) {
  return (
    <div className="mb-4">
      <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
        Parameter Gempa
      </div>

      <div className="mb-3">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs">Magnitudo</span>
          <span className="text-sm font-bold font-mono" style={{ color: 'var(--accent)' }}>
            {magnitude.toFixed(1)} Mw
          </span>
        </div>
        <input
          type="range"
          min="5"
          max="9.5"
          step="0.1"
          value={magnitude}
          onChange={(event) => onMagnitudeChange(parseFloat(event.target.value))}
          className="w-full"
        />

        <div className="flex gap-1 flex-wrap mt-2">
          {magnitudePresets.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => onMagnitudeChange(preset)}
              className="px-2 py-1 rounded text-xs border font-semibold transition-all"
              style={{
                background: 'transparent',
                borderColor: magnitude === preset ? 'var(--accent)' : 'var(--border)',
                color: magnitude === preset ? 'var(--accent)' : 'var(--muted)',
              }}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
        Jenis Sesar
      </div>
      <div className="grid grid-cols-2 gap-2 mb-3">
        {(['vertical', 'horizontal'] as const).map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => onFaultTypeChange(type)}
            className="p-2 rounded border text-center text-xs font-semibold transition-all"
            style={{
              background: faultType === type ? 'rgba(56, 189, 248, 0.14)' : 'rgba(0, 15, 40, 0.5)',
              borderColor: faultType === type ? 'var(--accent)' : 'var(--border)',
              color: faultType === type ? 'var(--accent)' : 'var(--muted)',
            }}
          >
            <div className="text-base mb-1">{type === 'vertical' ? '↕' : '↔'}</div>
            {type === 'vertical' ? 'Vertikal' : 'Horizontal'}
          </button>
        ))}
      </div>

      <div className="text-xs p-2 rounded-md mb-3" style={{
        background: 'rgba(0, 20, 40, 0.5)',
        color: 'var(--muted)',
        lineHeight: '1.6',
      }}>
        ⚡ Vertikal → perpindahan lantai laut lebih besar → potensi tsunami lebih tinggi
      </div>

      <button
        type="button"
        onClick={onRunSimulation}
        disabled={isLoading || (sourceMode === 'custom' && !customEpicenter)}
        className="w-full py-3 rounded-lg font-bold uppercase text-sm text-white transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: 'linear-gradient(135deg, #005c99, #0088cc)',
          boxShadow: '0 4px 20px rgba(14, 165, 233, 0.3)',
          letterSpacing: '1px',
        }}
      >
        {isLoading ? '⏳ SIMULASI BERJALAN...' : '▶ JALANKAN SIMULASI (SWE NUMERIK)'}
      </button>
    </div>
  );
}
