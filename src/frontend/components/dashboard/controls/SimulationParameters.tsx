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
    <div className="mb-5">
      <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: '#475569' }}>
        Parameter Gempa
      </div>

      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs font-medium" style={{ color: '#1e293b' }}>Magnitudo</span>
          <span className="text-sm font-bold font-mono" style={{ color: '#2563eb' }}>
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

        <div className="flex gap-2 flex-wrap mt-2">
          {magnitudePresets.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => onMagnitudeChange(preset)}
              className="px-3 py-1.5 rounded text-xs border font-semibold transition-all"
              style={{
                background: magnitude === preset ? '#dbeafe' : '#ffffff',
                borderColor: magnitude === preset ? '#3b82f6' : '#cbd5e1',
                color: magnitude === preset ? '#1d4ed8' : '#64748b',
              }}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
        Jenis Sesar
      </div>
      <div className="grid grid-cols-2 gap-2 mb-4">
        {(['vertical', 'horizontal'] as const).map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => onFaultTypeChange(type)}
            className="p-3 rounded-lg border text-center text-xs font-semibold transition-all"
            style={{
              background: faultType === type ? '#dbeafe' : '#f1f5f9',
              borderColor: faultType === type ? '#3b82f6' : '#cbd5e1',
              color: faultType === type ? '#1d4ed8' : '#475569',
            }}
          >
            <div className="text-base mb-1">{type === 'vertical' ? '↕' : '↔'}</div>
            {type === 'vertical' ? 'Vertikal' : 'Horizontal'}
          </button>
        ))}
      </div>

      <div className="text-xs p-4 rounded-lg mb-4" style={{
        background: '#fef3c7',
        color: '#92400e',
        lineHeight: '1.7',
        border: '1px solid #fbbf24',
      }}>
        ⚡ Vertikal → perpindahan lantai laut lebih besar → potensi tsunami lebih tinggi
      </div>

      <button
        type="button"
        onClick={onRunSimulation}
        disabled={isLoading || (sourceMode === 'custom' && !customEpicenter)}
        className="w-full py-3.5 rounded-lg font-bold uppercase text-sm text-white transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
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
