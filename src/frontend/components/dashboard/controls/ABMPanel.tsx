'use client';

import { useState } from 'react';
import type { ABMParams } from '@/types';

interface ABMPanelProps {
  transportMode: 'foot' | 'motor' | 'car';
  onRunABM?: (params: ABMParams) => Promise<void>;
  isLoading?: boolean;
  hasSimulated?: boolean;  // Apakah SWE sudah dijalankan
}

export default function ABMPanel({
  transportMode,
  onRunABM,
  isLoading = false,
  hasSimulated = false,
}: ABMPanelProps) {
  // Default parameters (backend uses constants)
  const warningTime = 20;  // Default: 20 minutes
  const duration = 120;     // Default: 120 minutes (2 hours)
  const floodHeight = 5;    // Default: 5 meters

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
      {/* Integration Status Banner */}
      <div className="mb-3 p-3 rounded-lg border text-xs"
        style={{
          background: hasSimulated
            ? 'rgba(34, 197, 94, 0.12)'
            : 'rgba(251, 191, 36, 0.12)',
          borderColor: hasSimulated
            ? 'rgba(34, 197, 94, 0.3)'
            : 'rgba(251, 191, 36, 0.3)',
        }}>
        <div className="flex items-center gap-2">
          <span className="text-lg">
            {hasSimulated ? '✅' : '⚠️'}
          </span>
          <div>
            <div className="font-bold" style={{
              color: hasSimulated ? '#22c55e' : '#fbbf24'
            }}>
              {hasSimulated
                ? 'Integrasi SWE Aktif'
                : 'Jalankan Simulasi SWE Dulu'}
            </div>
            <div style={{ color: '#64748b', marginTop: '2px' }}>
              {hasSimulated
                ? 'ABM akan menggunakan data tsunami untuk hazard-aware routing'
                : 'ABM akan berjalan tanpa data tsunami (simplified mode)'}
            </div>
          </div>
        </div>
      </div>

      <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: '#475569' }}>
        Parameter ABM Evakuasi
      </div>

      {/* Parameter inputs - Hidden (Backend uses constants)
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
      */}

      {/* Info panel - Parameter values */}
      <div className="mb-4 p-3 rounded-lg border text-xs space-y-2" style={{
        background: '#f3e8ff',
        borderColor: '#d8b4fe',
        color: '#581c87',
      }}>
        <div className="font-semibold mb-2" style={{ color: '#7c3aed' }}>📊 Parameter Simulasi (Default)</div>
        <div className="flex justify-between">
          <span style={{ color: '#6b21a8' }}>⏰ Waktu Peringatan:</span>
          <span className="font-bold" style={{ color: '#581c87' }}>{warningTime} menit</span>
        </div>
        <div className="flex justify-between">
          <span style={{ color: '#6b21a8' }}>⏱ Durasi Simulasi:</span>
          <span className="font-bold" style={{ color: '#581c87' }}>{duration} menit</span>
        </div>
        <div className="flex justify-between">
          <span style={{ color: '#6b21a8' }}>🌊 Tinggi Banjir:</span>
          <span className="font-bold" style={{ color: '#581c87' }}>{floodHeight} meter</span>
        </div>
      </div>

      <button
        type="button"
        onClick={handleRunABM}
        disabled={isLoading}
        className="w-full py-3.5 rounded-lg font-bold uppercase text-sm text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: 'linear-gradient(135deg, #7c3aed, #8b5cf6)',
          boxShadow: '0 4px 20px rgba(124, 58, 237, 0.3)',
          letterSpacing: '1px',
        }}
      >
        🤖 JALANKAN SIMULASI ABM
      </button>

      <div className="mt-3 text-xs text-center" style={{ color: '#94a3b8' }}>
        Simulasi ABM belum dijalankan
      </div>
    </>
  );
}
