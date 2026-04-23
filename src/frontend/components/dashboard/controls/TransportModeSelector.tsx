'use client';

import React from 'react';

interface TransportModeSelectorProps {
  selectedMode: 'foot' | 'motor' | 'car';
  onModeChange: (mode: 'foot' | 'motor' | 'car') => void;
  className?: string;
}

const transportModes = [
  {
    id: 'foot' as const,
    label: 'Jalan Kaki',
    speed: '~4 km/jam',
    icon: '🚶',
    color: 'bg-green-500',
    description: 'Evakuasi darat, cocok untuk jarak pendek'
  },
  {
    id: 'motor' as const,
    label: 'Sepeda Motor',
    speed: '~30 km/jam',
    icon: '🏍️',
    color: 'bg-yellow-500',
    description: 'Transportasi cepat, dapat melewati jalan kecil'
  },
  {
    id: 'car' as const,
    label: 'Mobil',
    speed: '~40 km/jam',
    icon: '🚗',
    color: 'bg-blue-500',
    description: 'Transportasi keluarga, kapasitas lebih besar'
  }
];

export default function TransportModeSelector({
  selectedMode,
  onModeChange,
  className = ''
}: TransportModeSelectorProps) {
  // Design tokens matching old index.html
  const theme = {
    panel: '#0a1628',
    border: 'rgba(56, 189, 248, 0.14)',
    border2: 'rgba(56, 189, 248, 0.08)',
    accent: '#38bdf8',
    text: '#ddeeff',
    text2: '#a8ccee',
    muted: 'rgba(148, 200, 240, 0.55)',
    ok: '#34d399',
  };
  return (
    <div className={`space-y-3 ${className}`}>
      <div className="text-sm font-semibold" style={{ color: theme.text }}>Moda Transportasi</div>

      <div className="flex gap-3 overflow-x-auto pb-2">
        {transportModes.map((mode) => (
          <button
            key={mode.id}
            onClick={() => onModeChange(mode.id)}
            className="flex-1 min-w-[130px] p-4 rounded-lg border-2 transition-all text-left"
            style={{
              borderColor: selectedMode === mode.id ? theme.accent : theme.border,
              background: selectedMode === mode.id ? 'rgba(56, 189, 248, 0.12)' : 'rgba(56, 189, 248, 0.06)',
              color: selectedMode === mode.id ? theme.accent : theme.text2
            }}
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-lg" style={{
                background: mode.color
              }}>
                {mode.icon}
              </div>
              <div>
                <div className="font-medium text-sm" style={{ color: theme.text }}>{mode.label}</div>
                <div className="text-xs" style={{ color: theme.muted }}>{mode.speed}</div>
              </div>
            </div>
            <div className="text-xs leading-tight" style={{ color: theme.muted }}>{mode.description}</div>
          </button>
        ))}
      </div>

      {/* Speed indicator */}
      <div className="mt-4 p-3 rounded-lg" style={{
        background: 'rgba(56, 189, 248, 0.06)',
        border: `1px solid ${theme.border2}`
      }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium" style={{ color: theme.text }}>Kecepatan Estimasi</span>
          <span className="text-sm font-bold" style={{ color: theme.accent }}>
            {transportModes.find(m => m.id === selectedMode)?.speed}
          </span>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-2">
          <div
            className="h-2 rounded-full transition-all duration-300"
            style={{
              background: theme.accent,
              width: `${
                selectedMode === 'foot' ? '25%' :
                selectedMode === 'motor' ? '75%' :
                '100%'
              }`
            }}
          />
        </div>
      </div>
    </div>
  );
}