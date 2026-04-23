'use client';

import React from 'react';

interface SafetyWeightSliderProps {
  value: number;
  onChange: (value: number) => void;
  className?: string;
}

const safetyLevels = [
  { value: 0, label: 'Cepat', description: 'Prioritas kecepatan, risiko tinggi', color: 'text-red-600', bgColor: 'bg-red-100' },
  { value: 25, label: 'Seimbang', description: 'Keseimbangan waktu dan keselamatan', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  { value: 50, label: 'Aman', description: 'Prioritas keselamatan, waktu lebih lama', color: 'text-green-600', bgColor: 'bg-green-100' },
  { value: 75, label: 'Sangat Aman', description: 'Rute teraman, waktu signifikan', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  { value: 100, label: 'Ultra Aman', description: 'Rute paling aman, waktu maksimal', color: 'text-purple-600', bgColor: 'bg-purple-100' },
];

export default function SafetyWeightSlider({ value, onChange, className = '' }: SafetyWeightSliderProps) {
  const currentLevel = safetyLevels.reduce((prev, curr) =>
    Math.abs(curr.value - value) < Math.abs(prev.value - value) ? curr : prev
  );

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
    <div className={`space-y-4 ${className}`}>
      <div className="text-sm font-semibold" style={{ color: theme.text }}>Bobot Keselamatan</div>

      {/* Slider */}
      <div className="px-2">
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full h-2 rounded-lg appearance-none cursor-pointer slider"
          style={{ accentColor: theme.accent }}
        />
        <style jsx>{`
          .slider::-webkit-slider-thumb {
            appearance: none;
            height: 20px;
            width: 20px;
            border-radius: 50%;
            background: ${theme.accent};
            cursor: pointer;
            border: 2px solid #0a1628;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          }
          .slider::-moz-range-thumb {
            height: 20px;
            width: 20px;
            border-radius: 50%;
            background: ${theme.accent};
            cursor: pointer;
            border: 2px solid #0a1628;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          }
        `}</style>
      </div>

      {/* Value display */}
      <div className="flex justify-between items-center text-sm">
        <span style={{ color: theme.muted }}>Risiko Tinggi</span>
        <div className="px-3 py-1 rounded-full text-xs font-bold" style={{
          background: 'rgba(56, 189, 248, 0.14)',
          color: theme.accent
        }}>
          {value}%
        </div>
        <span style={{ color: theme.muted }}>Ultra Aman</span>
      </div>

      {/* Current level info */}
      <div className="p-3 rounded-lg" style={{
        background: 'rgba(56, 189, 248, 0.08)',
        border: `2px solid ${theme.accent}`
      }}>
        <div className="font-semibold text-sm mb-1" style={{ color: theme.accent }}>
          {currentLevel.label}
        </div>
        <div className="text-xs" style={{ color: theme.text2 }}>
          {currentLevel.description}
        </div>
      </div>

      {/* Visual indicator */}
      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: theme.muted }}>Prioritas:</span>
        <div className="flex-1 flex gap-1">
          {safetyLevels.map((level, index) => (
            <div
              key={level.value}
              className="flex-1 h-2 rounded-full transition-colors"
              style={{
                background: value >= level.value ? theme.accent : theme.border2
              }}
            />
          ))}
        </div>
      </div>

      {/* Impact preview */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="p-2 rounded border" style={{
          background: 'rgba(248, 113, 113, 0.08)',
          border: '1px solid rgba(248, 113, 113, 0.2)'
        }}>
          <div className="font-medium" style={{ color: '#f87171' }}>Waktu Tempuh</div>
          <div style={{ color: theme.text2 }}>
            {value < 25 ? '+0-10%' : value < 50 ? '+10-25%' : value < 75 ? '+25-50%' : '+50-100%'}
          </div>
        </div>
        <div className="p-2 rounded border" style={{
          background: 'rgba(52, 211, 153, 0.08)',
          border: '1px solid rgba(52, 211, 153, 0.2)'
        }}>
          <div className="font-medium" style={{ color: '#34d399' }}>Tingkat Aman</div>
          <div style={{ color: theme.text2 }}>
            {value < 25 ? 'Rendah' : value < 50 ? 'Sedang' : value < 75 ? 'Tinggi' : 'Sangat Tinggi'}
          </div>
        </div>
      </div>
    </div>
  );
}