'use client';

import React, { useState } from 'react';
import type { ABMParams } from '@/types';

interface ABMPanelProps {
  transportMode: 'foot' | 'motor' | 'car';
  onRunABM?: (params: ABMParams) => Promise<void>;
  isLoading?: boolean;
}

export default function ABMPanel({
  transportMode,
  onRunABM,
  isLoading = false,
}: ABMPanelProps) {
  const [warningTime, setWarningTime] = useState(20);
  const [duration, setDuration] = useState(120);
  const [floodHeight, setFloodHeight] = useState(5);

  const handleRunABM = async () => {
    if (!onRunABM) return;

    const params: ABMParams = {
      warning_time_min: warningTime,
      sim_duration_min: duration,
      flood_height_m: floodHeight,
      transport: transportMode,
    };

    await onRunABM(params);
  };

  return (
    <>
      <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
        Parameter ABM Evakuasi
      </div>

      <div className="grid grid-cols-2 gap-2 mb-4">
        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>⏰ Waktu Peringatan (mnt)</div>
          <input
            type="number"
            min={5}
            max={60}
            value={warningTime}
            onChange={(event) => setWarningTime(Number(event.target.value))}
            className="w-full"
            style={{ background: 'rgba(0, 15, 40, 0.55)', color: 'var(--text)', borderColor: 'var(--border)' }}
          />
        </div>
        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>⏱ Durasi Simulasi (mnt)</div>
          <input
            type="number"
            min={30}
            max={360}
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
            className="w-full"
            style={{ background: 'rgba(0, 15, 40, 0.55)', color: 'var(--text)', borderColor: 'var(--border)' }}
          />
        </div>
      </div>

      <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
        <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>
          🌊 Tinggi Banjir Inundasi (m) — dari hasil simulasi tsunami
        </div>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min="1"
            max="20"
            step="0.5"
            value={floodHeight}
            onChange={(event) => setFloodHeight(Number(event.target.value))}
            className="flex-1"
            style={{ accentColor: '#f87171' }}
          />
          <span className="text-sm font-bold" style={{ color: '#f87171', minWidth: '40px' }}>
            {floodHeight} m
          </span>
        </div>
      </div>

      <button
        type="button"
        onClick={handleRunABM}
        disabled={isLoading}
        className="w-full py-2 rounded-lg font-bold text-xs uppercase text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: 'linear-gradient(135deg, #1a0050, #7c3aed)',
          boxShadow: '0 4px 18px rgba(124, 58, 237, 0.3)',
          letterSpacing: '1px',
        }}
      >
        🤖 JALANKAN SIMULASI ABM
      </button>

      <div className="mt-4 text-xs text-center" style={{ color: 'var(--muted)' }}>
        Simulasi ABM belum dijalankan
      </div>
    </>
  );
}
