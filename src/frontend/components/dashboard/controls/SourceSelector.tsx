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
    <div className="mb-5">
      <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: '#475569' }}>
        Sumber Gempa
      </div>

      <div className="flex gap-2 rounded-lg p-1.5 mb-4" style={{ background: '#f1f5f9' }}>
        {(['fault', 'mega', 'custom'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => {
              onSourceModeChange(tab);
              // Reset selected fault ketika ganti mode
              if (tab === 'custom') {
                onSelectFault('');
              }
            }}
            className="flex-1 py-2.5 px-3 text-xs font-medium rounded-md text-center transition-all hover:bg-blue-50"
            style={{
              background: sourceMode === tab ? '#3b82f6' : '#ffffff',
              color: sourceMode === tab ? '#ffffff' : '#1e293b',
              border: sourceMode === tab ? '1px solid #3b82f6' : '1px solid #cbd5e1',
            }}
          >
            {tab === 'fault' && '⚡ Patahan'}
            {tab === 'mega' && '🌊 Megathrust'}
            {tab === 'custom' && '📍 Custom'}
          </button>
        ))}
      </div>

      {sourceMode === 'custom' && (
        <div className="text-xs p-4 rounded-lg border" style={{
          background: '#fef3c7',
          borderColor: '#fbbf24',
          color: '#92400e',
          lineHeight: '1.7',
        }}>
          {/* Layout horizontal untuk instruksi dan tombol */}
          <div className="flex items-center gap-3 mb-3">
            <div className="flex-1">
              {customEpicenter ? (
                <span className="font-semibold">
                  📍 {customEpicenter.lat.toFixed(4)}°, {customEpicenter.lon.toFixed(4)}°
                </span>
              ) : (
                <span>📍 Klik peta untuk memilih episentrum</span>
              )}
            </div>
            <button
              type="button"
              onClick={onPickEpicenterToggle}
              className="py-2.5 px-4 rounded-md font-semibold text-xs whitespace-nowrap"
              style={{
                background: isPickingEpicenter ? '#d97706' : '#f59e0b',
                color: '#ffffff',
                border: '1px solid',
                borderColor: isPickingEpicenter ? '#d97706' : '#f59e0b',
              }}
            >
              {isPickingEpicenter ? 'Memilih...' : (customEpicenter ? 'Ubah' : 'Pilih')}
            </button>
          </div>
          {customEpicenter && (
            <button
              type="button"
              onClick={onResetEpicenter}
              className="w-full py-2.5 px-4 rounded-md text-xs font-semibold"
              style={{
                background: '#ffffff',
                border: '1px solid #fca5a5',
                color: '#dc2626',
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
