'use client';

import React, { useState } from 'react';

interface DetailedParameterControlsProps {
  magnitude: number;
  onMagnitudeChange: (value: number) => void;
  faultType: 'vertical' | 'horizontal' | 'thrust';
  onFaultTypeChange: (type: 'vertical' | 'horizontal' | 'thrust') => void;
  depth: number;
  onDepthChange: (value: number) => void;
  length: number;
  onLengthChange: (value: number) => void;
  rake: number;
  onRakeChange: (value: number) => void;
  className?: string;
}

const magnitudePresets = [6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0];
const faultTypes = [
  { id: 'vertical' as const, label: 'Strike-Slip', description: 'Geser mendatar', icon: '↔️' },
  { id: 'thrust' as const, label: 'Thrust', description: 'Dorong naik', icon: '⬆️' },
  { id: 'horizontal' as const, label: 'Normal', description: 'Tarik turun', icon: '⬇️' },
];

export default function DetailedParameterControls({
  magnitude,
  onMagnitudeChange,
  faultType,
  onFaultTypeChange,
  depth,
  onDepthChange,
  length,
  onLengthChange,
  rake,
  onRakeChange,
  className = ''
}: DetailedParameterControlsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Design tokens matching old index.html
  const theme = {
    panel: '#0a1628',
    border: 'rgba(56, 189, 248, 0.14)',
    border2: 'rgba(56, 189, 248, 0.08)',
    accent: '#38bdf8',
    text: '#ddeeff',
    text2: '#a8ccee',
    muted: 'rgba(148, 200, 240, 0.55)',
  };

  return (
    <div className={`rounded-lg shadow-lg overflow-hidden ${className}`} style={{
      background: theme.panel,
      border: `1px solid ${theme.border}`,
      backdropFilter: 'blur(8px)'
    }}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between transition-colors"
        style={{
          borderBottom: `1px solid ${theme.border2}`
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.06)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">⚙️</span>
          <div className="text-left">
            <div className="text-sm font-semibold" style={{ color: theme.text }}>Parameter Detail</div>
            <div className="text-xs" style={{ color: theme.muted }}>Kontrol granular simulasi</div>
          </div>
        </div>
        <span className={`text-sm transition-transform ${isExpanded ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {isExpanded && (
        <div className="p-4 space-y-6">
          {/* Magnitude */}
          <div>
            <label className="block text-sm font-semibold mb-2" style={{ color: theme.text }}>
              Magnitude (Mw)
            </label>
            <div className="flex gap-2 mb-3">
              {magnitudePresets.map((preset) => (
                <button
                  key={preset}
                  onClick={() => onMagnitudeChange(preset)}
                  className="px-3 py-1 text-xs rounded-md transition-colors"
                  style={{
                    background: magnitude === preset ? theme.accent : 'rgba(56, 189, 248, 0.08)',
                    color: magnitude === preset ? '#000' : theme.text2,
                    border: `1px solid ${magnitude === preset ? theme.accent : theme.border2}`
                  }}
                >
                  {preset}
                </button>
              ))}
            </div>
            <input
              type="range"
              min="5.0"
              max="9.5"
              step="0.1"
              value={magnitude}
              onChange={(e) => onMagnitudeChange(Number(e.target.value))}
              style={{ accentColor: theme.accent }}
              className="w-full"
            />
            <div className="flex justify-between text-xs mt-1" style={{ color: theme.muted }}>
              <span>5.0</span>
              <span style={{ color: theme.accent, fontWeight: 'bold' }}>{magnitude.toFixed(1)}</span>
              <span>9.5</span>
            </div>
          </div>

          {/* Fault Type */}
          <div>
            <label className="block text-sm font-semibold mb-3" style={{ color: theme.text }}>
              Tipe Sesar
            </label>
            <div className="grid grid-cols-3 gap-2">
              {faultTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => onFaultTypeChange(type.id)}
                  className="p-3 rounded-lg transition-all text-center"
                  style={{
                    background: faultType === type.id ? 'rgba(56, 189, 248, 0.14)' : 'rgba(56, 189, 248, 0.06)',
                    border: `2px solid ${faultType === type.id ? theme.accent : theme.border}`
                  }}
                >
                  <div className="text-lg mb-1">{type.icon}</div>
                  <div className="text-xs font-medium" style={{ color: theme.text }}>{type.label}</div>
                  <div className="text-xs mt-1" style={{ color: theme.muted }}>{type.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Depth */}
          <div>
            <label className="block text-sm font-semibold mb-2" style={{ color: theme.text }}>
              Kedalaman Hiposenter (km)
            </label>
            <input
              type="range"
              min="1"
              max="50"
              step="1"
              value={depth}
              onChange={(e) => onDepthChange(Number(e.target.value))}
              style={{ accentColor: theme.accent }}
              className="w-full"
            />
            <div className="flex justify-between text-xs mt-1" style={{ color: theme.muted }}>
              <span>1 km</span>
              <span style={{ color: theme.accent, fontWeight: 'bold' }}>{depth} km</span>
              <span>50 km</span>
            </div>
          </div>

          {/* Length */}
          <div>
            <label className="block text-sm font-semibold mb-2" style={{ color: theme.text }}>
              Panjang Sesar (km)
            </label>
            <input
              type="range"
              min="10"
              max="500"
              step="10"
              value={length}
              onChange={(e) => onLengthChange(Number(e.target.value))}
              style={{ accentColor: theme.accent }}
              className="w-full"
            />
            <div className="flex justify-between text-xs mt-1" style={{ color: theme.muted }}>
              <span>10 km</span>
              <span style={{ color: theme.accent, fontWeight: 'bold' }}>{length} km</span>
              <span>500 km</span>
            </div>
          </div>

          {/* Rake Angle */}
          <div>
            <label className="block text-sm font-semibold mb-2" style={{ color: theme.text }}>
              Sudut Rake (°)
            </label>
            <input
              type="range"
              min="-180"
              max="180"
              step="15"
              value={rake}
              onChange={(e) => onRakeChange(Number(e.target.value))}
              style={{ accentColor: theme.accent }}
              className="w-full"
            />
            <div className="flex justify-between text-xs mt-1" style={{ color: theme.muted }}>
              <span>-180°</span>
              <span style={{ color: theme.accent, fontWeight: 'bold' }}>{rake}°</span>
              <span>180°</span>
            </div>
            <div className="text-xs mt-1 text-center" style={{ color: theme.muted }}>
              {rake === 0 ? 'Strike-slip murni' :
               rake > 0 && rake <= 90 ? 'Thrust dominan' :
               rake < 0 && rake >= -90 ? 'Normal dominan' : 'Complex'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}