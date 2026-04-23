'use client';

import type { SimulationParams } from '@/types';

interface SourceSelectorProps {
  sourceMode: SimulationParams['source_mode'];
  onSourceModeChange: (mode: SimulationParams['source_mode']) => void;
  selectedFault: string | null;
  onSelectFault: (faultId: string) => void;
  customEpicenter: { lat: number; lon: number } | null;
  isPickingEpicenter: boolean;
  onPickEpicenterToggle: () => void;
  onResetEpicenter: () => void;
}

const faults = [
  { id: 'baribis-1', name: 'Baribis Kendeng F - Cirebon-1', magnitude: '6.5 Mw' },
  { id: 'baribis-2', name: 'Baribis Kendeng F - Cirebon-2', magnitude: '6.6 Mw' },
  { id: 'ciremai', name: 'Ciremai (Strike-slip)', magnitude: '6.6 Mw' },
];

const megathrust = [
  { id: 'mega-1', name: 'M1 - Megathrust Barat Sumatra', magnitude: '8.5+ Mw' },
  { id: 'mega-7', name: 'M7 - Megathrust Sunda', magnitude: '8.5+ Mw' },
];

export default function SourceSelector({
  sourceMode,
  onSourceModeChange,
  selectedFault,
  onSelectFault,
  customEpicenter,
  isPickingEpicenter,
  onPickEpicenterToggle,
  onResetEpicenter,
}: SourceSelectorProps) {
  return (
    <div className="mb-4">
      <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
        Sumber Gempa
      </div>

      <div className="flex gap-1 bg-opacity-50 bg-black rounded-md p-1 mb-3" style={{ background: 'rgba(0, 20, 50, 0.5)' }}>
        {(['fault', 'mega', 'custom'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => onSourceModeChange(tab)}
            className={`flex-1 py-1.5 px-2 text-xs font-semibold rounded text-center transition-all ${
              sourceMode === tab ? 'text-cyan-400' : 'text-gray-500 hover:text-gray-300'
            }`}
            style={{
              background: sourceMode === tab ? 'rgba(56, 189, 248, 0.18)' : 'transparent',
              color: sourceMode === tab ? 'var(--accent)' : 'var(--muted)',
              boxShadow: sourceMode === tab ? 'inset 0 0 0 1px rgba(56, 189, 248, 0.3)' : 'none',
            }}
          >
            {tab === 'fault' && 'Patahan'}
            {tab === 'mega' && 'Megathrust'}
            {tab === 'custom' && 'Custom'}
          </button>
        ))}
      </div>

      {sourceMode === 'fault' && (
        <div className="flex flex-col gap-1 max-h-40 overflow-y-auto pr-1">
          {faults.map((fault) => (
            <button
              key={fault.id}
              type="button"
              onClick={() => onSelectFault(fault.id)}
              className="p-2.5 rounded-md border text-xs text-left transition-all"
              style={{
                background: selectedFault === fault.id ? 'rgba(56, 189, 248, 0.13)' : 'rgba(0, 20, 50, 0.4)',
                borderColor: selectedFault === fault.id ? 'var(--accent)' : 'var(--border2)',
                color: selectedFault === fault.id ? 'var(--accent)' : 'var(--text)',
              }}
            >
              <div className="font-semibold">{fault.name}</div>
              <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{fault.magnitude}</div>
            </button>
          ))}
        </div>
      )}

      {sourceMode === 'mega' && (
        <div className="flex flex-col gap-1 max-h-40 overflow-y-auto pr-1">
          {megathrust.map((mega) => (
            <button
              key={mega.id}
              type="button"
              onClick={() => onSelectFault(mega.id)}
              className="p-2.5 rounded-md border text-xs text-left transition-all"
              style={{
                background: selectedFault === mega.id ? 'rgba(251, 146, 60, 0.12)' : 'rgba(30, 12, 0, 0.4)',
                borderColor: selectedFault === mega.id ? 'var(--batnas)' : 'rgba(251, 146, 60, 0.1)',
                color: selectedFault === mega.id ? 'var(--batnas)' : 'var(--text)',
              }}
            >
              <div className="font-semibold">{mega.name}</div>
              <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{mega.magnitude}</div>
            </button>
          ))}
        </div>
      )}

      {sourceMode === 'custom' && (
        <div className="text-xs p-2 rounded-md border" style={{
          background: 'rgba(0, 18, 45, 0.5)',
          borderColor: 'var(--border)',
          color: 'var(--muted)',
          lineHeight: '1.7',
        }}>
          <div className="mb-2">📍 Klik peta untuk memilih episentrum</div>
          <div className="mb-3">
            {customEpicenter ? (
              <span style={{ color: 'var(--accent)' }}>
                {customEpicenter.lat.toFixed(5)}°, {customEpicenter.lon.toFixed(5)}°
              </span>
            ) : (
              <span style={{ color: 'var(--text)' }}>Belum ada titik episentrum</span>
            )}
          </div>
          <button
            type="button"
            onClick={onPickEpicenterToggle}
            className="w-full py-2 px-3 rounded-md font-semibold text-xs"
            style={{
              background: isPickingEpicenter ? 'rgba(56, 189, 248, 0.2)' : 'rgba(56, 189, 248, 0.08)',
              border: '1px solid',
              borderColor: isPickingEpicenter ? 'var(--accent)' : 'rgba(56, 189, 248, 0.25)',
              color: isPickingEpicenter ? 'var(--accent)' : 'var(--text)',
            }}
          >
            {isPickingEpicenter ? 'Klik peta untuk pilih titik...' : (customEpicenter ? 'Ubah titik episentrum' : 'Pilih titik episentrum')}
          </button>
          {customEpicenter && (
            <button
              type="button"
              onClick={onResetEpicenter}
              className="w-full mt-2 py-2 px-3 rounded-md text-xs"
              style={{
                background: 'rgba(248, 113, 113, 0.08)',
                border: '1px solid rgba(248, 113, 113, 0.18)',
                color: '#f87171',
              }}
            >
              Reset titik episentrum
            </button>
          )}
        </div>
      )}
    </div>
  );
}
