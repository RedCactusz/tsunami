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
  return (
    <div className={`space-y-2 ${className}`}>
      {/* Compact mode selector - horizontal 3 columns */}
      <div className="grid grid-cols-3 gap-2">
        {transportModes.map((mode) => (
          <button
            key={mode.id}
            onClick={() => onModeChange(mode.id)}
            className="p-2.5 rounded-lg border-2 transition-all text-center"
            style={{
              borderColor: selectedMode === mode.id ? '#3b82f6' : '#cbd5e1',
              background: selectedMode === mode.id ? '#dbeafe' : '#f8fafc',
              color: selectedMode === mode.id ? '#1d4ed8' : '#475569'
            }}
          >
            <div className="text-lg mb-1">{mode.icon}</div>
            <div className="text-xs font-bold leading-tight" style={{ color: selectedMode === mode.id ? '#1e40af' : '#475569' }}>
              {mode.id === 'foot' ? 'Jalan' : mode.id === 'motor' ? 'Motor' : 'Mobil'}
            </div>
            <div className="text-xs mt-1" style={{ color: '#64748b' }}>{mode.speed}</div>
          </button>
        ))}
      </div>

      {/* Speed indicator - compact */}
      <div className="flex items-center justify-between p-2 rounded-lg text-xs" style={{
        background: '#f1f5f9',
        border: `1px solid #e2e8f0`
      }}>
        <span style={{ color: '#475569' }}>Kecepatan:</span>
        <span className="font-bold" style={{ color: '#2563eb' }}>
          {transportModes.find(m => m.id === selectedMode)?.speed}
        </span>
      </div>
    </div>
  );
}