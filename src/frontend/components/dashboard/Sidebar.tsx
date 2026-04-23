'use client';

import React, { useState } from 'react';
import type { SimulationParams, SWEResult, TESData } from '@/types';

interface SidebarProps {
  onSimulationRun?: (params: SimulationParams) => Promise<void>;
  isLoading?: boolean;
  sweResult?: SWEResult | null;
  tesList?: TESData[];
}

export default function Sidebar({ onSimulationRun, isLoading = false, sweResult, tesList = [] }: SidebarProps) {
  const [magnitude, setMagnitude] = useState(7.5);
  const [faultType, setFaultType] = useState<'vertical' | 'horizontal'>('vertical');
  const [selectedFault, setSelectedFault] = useState<string | null>(null);
  const [sourceMode, setSourceMode] = useState<'fault' | 'mega' | 'custom'>('fault');
  
  // Dummy data for faults
  const faults = [
    { id: 'baribis-1', name: 'Baribis Kendeng F - Cirebon-1', magnitude: '6.5 Mw' },
    { id: 'baribis-2', name: 'Baribis Kendeng F - Cirebon-2', magnitude: '6.6 Mw' },
    { id: 'ciremai', name: 'Ciremai (Strike-slip)', magnitude: '6.6 Mw' },
  ];

  const megathrust = [
    { id: 'mega-1', name: 'M1 - Megathrust Barat Sumatra', magnitude: '8.5+ Mw' },
    { id: 'mega-7', name: 'M7 - Megathrust Sunda', magnitude: '8.5+ Mw' },
  ];

  const magnitudePresets = [6, 6.5, 7, 7.5, 8, 8.5, 9];

  const handleRunSimulation = async () => {
    if (!onSimulationRun) return;
    
    const params: SimulationParams = {
      magnitude,
      fault_type: faultType,
      fault_id: selectedFault,
      source_mode: sourceMode,
    };
    
    await onSimulationRun(params);
  };

  return (
    <aside className="w-80 flex-shrink-0 flex flex-col border-r overflow-y-auto"
      style={{
        background: 'var(--panel)',
        borderColor: 'var(--border)',
      }}
    >
      {/* HEADER PANEL */}
      <div className="p-3 flex-shrink-0 border-b" style={{
        background: 'rgba(0, 30, 60, 0.35)',
        borderColor: 'rgba(56, 189, 248, 0.18)'
      }}>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{
            background: 'linear-gradient(135deg, #003060, #0077cc)'
          }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 64 64" className="fill-white">
              <path d="M4,36 Q12,24 20,36 Q28,48 36,36 Q44,24 52,36 Q58,44 62,36" stroke="white" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--accent)' }}>
              PEMODELAN TSUNAMI
            </div>
            <div className="text-xs" style={{ color: 'var(--muted)' }}>
              Simulasi Gelombang · Zona Inundasi
            </div>
          </div>
        </div>
      </div>

      {/* SCROLLABLE CONTENT */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        
        {/* SOURCE SELECTOR */}
        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
            Sumber Gempa
          </div>
          
          {/* Tabs */}
          <div className="flex gap-1 bg-opacity-50 bg-black rounded-md p-1 mb-3" style={{ background: 'rgba(0, 20, 50, 0.5)' }}>
            {(['fault', 'mega', 'custom'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setSourceMode(tab)}
                className={`flex-1 py-1.5 px-2 text-xs font-semibold rounded text-center transition-all ${
                  sourceMode === tab ? 'text-cyan-400' : 'text-gray-500 hover:text-gray-300'
                }`}
                style={{
                  background: sourceMode === tab ? 'rgba(56, 189, 248, 0.18)' : 'transparent',
                  color: sourceMode === tab ? 'var(--accent)' : 'var(--muted)',
                  boxShadow: sourceMode === tab ? 'inset 0 0 0 1px rgba(56, 189, 248, 0.3)' : 'none'
                }}
              >
                {tab === 'fault' && 'Patahan'}
                {tab === 'mega' && 'Megathrust'}
                {tab === 'custom' && 'Custom'}
              </button>
            ))}
          </div>

          {/* Fault List */}
          {sourceMode === 'fault' && (
            <div className="flex flex-col gap-1 max-h-40 overflow-y-auto pr-1">
              {faults.map(fault => (
                <button
                  key={fault.id}
                  onClick={() => setSelectedFault(fault.id)}
                  className="p-2.5 rounded-md border text-xs text-left transition-all"
                  style={{
                    background: selectedFault === fault.id ? 'rgba(56, 189, 248, 0.13)' : 'rgba(0, 20, 50, 0.4)',
                    borderColor: selectedFault === fault.id ? 'var(--accent)' : 'var(--border2)',
                    color: selectedFault === fault.id ? 'var(--accent)' : 'var(--text)'
                  }}
                >
                  <div className="font-semibold">{fault.name}</div>
                  <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{fault.magnitude}</div>
                </button>
              ))}
            </div>
          )}

          {/* Megathrust List */}
          {sourceMode === 'mega' && (
            <div className="flex flex-col gap-1 max-h-40 overflow-y-auto pr-1">
              {megathrust.map(mega => (
                <button
                  key={mega.id}
                  onClick={() => setSelectedFault(mega.id)}
                  className="p-2.5 rounded-md border text-xs text-left transition-all"
                  style={{
                    background: selectedFault === mega.id ? 'rgba(251, 146, 60, 0.12)' : 'rgba(30, 12, 0, 0.4)',
                    borderColor: selectedFault === mega.id ? 'var(--batnas)' : 'rgba(251, 146, 60, 0.1)',
                    color: selectedFault === mega.id ? 'var(--batnas)' : 'var(--text)'
                  }}
                >
                  <div className="font-semibold">{mega.name}</div>
                  <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{mega.magnitude}</div>
                </button>
              ))}
            </div>
          )}

          {/* Custom Mode */}
          {sourceMode === 'custom' && (
            <div className="text-xs p-2 rounded-md border" style={{
              background: 'rgba(0, 18, 45, 0.5)',
              borderColor: 'var(--border)',
              color: 'var(--muted)',
              lineHeight: '1.7'
            }}>
              📍 Klik di peta untuk menentukan episentrum<br/>
              <span style={{ color: 'var(--accent)' }}>Belum dipilih</span>
            </div>
          )}
        </div>

        {/* DEPTH PROBE */}
        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
            Probe Kedalaman (Hover Peta)
          </div>
          <div className="p-3 rounded-md border" style={{
            background: 'rgba(0, 18, 45, 0.55)',
            borderColor: 'var(--border)'
          }}>
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Koordinat</span>
              <span className="text-xs font-bold" style={{ color: 'var(--accent)' }}>—</span>
            </div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Kedalaman</span>
              <span className="text-sm font-bold" style={{ color: 'var(--accent)' }}>—</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Kec. gelombang</span>
              <span className="text-xs" style={{ color: 'var(--text)' }}>—</span>
            </div>
          </div>
        </div>

        {/* PARAMETERS */}
        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
            Parameter Gempa
          </div>

          {/* Magnitude Slider */}
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
              onChange={(e) => setMagnitude(parseFloat(e.target.value))}
              className="w-full"
            />
            
            {/* Presets */}
            <div className="flex gap-1 flex-wrap mt-2">
              {magnitudePresets.map(preset => (
                <button
                  key={preset}
                  onClick={() => setMagnitude(preset)}
                  className="px-2 py-1 rounded text-xs border font-semibold transition-all"
                  style={{
                    background: 'transparent',
                    borderColor: magnitude === preset ? 'var(--accent)' : 'var(--border)',
                    color: magnitude === preset ? 'var(--accent)' : 'var(--muted)'
                  }}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          {/* Fault Type */}
          <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
            Jenis Sesar
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            {(['vertical', 'horizontal'] as const).map(type => (
              <button
                key={type}
                onClick={() => setFaultType(type)}
                className="p-2 rounded border text-center text-xs font-semibold transition-all"
                style={{
                  background: faultType === type ? 'rgba(56, 189, 248, 0.14)' : 'rgba(0, 15, 40, 0.5)',
                  borderColor: faultType === type ? 'var(--accent)' : 'var(--border)',
                  color: faultType === type ? 'var(--accent)' : 'var(--muted)'
                }}
              >
                <div className="text-base mb-1">{type === 'vertical' ? '↕' : '↔'}</div>
                {type === 'vertical' ? 'Vertikal' : 'Horizontal'}
              </button>
            ))}
          </div>

          {/* Info Box */}
          <div className="text-xs p-2 rounded-md mb-3" style={{
            background: 'rgba(0, 20, 40, 0.5)',
            color: 'var(--muted)',
            lineHeight: '1.6'
          }}>
            ⚡ Vertikal → perpindahan lantai laut lebih besar → potensi tsunami lebih tinggi
          </div>

          {/* Run Button */}
          <button
            onClick={handleRunSimulation}
            disabled={isLoading}
            className="w-full py-3 rounded-lg font-bold uppercase text-sm text-white transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: 'linear-gradient(135deg, #005c99, #0088cc)',
              boxShadow: '0 4px 20px rgba(14, 165, 233, 0.3)',
              letterSpacing: '1px'
            }}
          >
            {isLoading ? '⏳ SIMULASI BERJALAN...' : '▶ JALANKAN SIMULASI (SWE NUMERIK)'}
          </button>
        </div>

        {/* LAYER TOGGLES PLACEHOLDER */}
        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
            Layer Peta
          </div>
          <div className="text-xs text-center py-4" style={{ color: 'var(--muted)' }}>
            Layer controls akan ditambahkan di sini
          </div>
        </div>

      </div>

      {/* FOOTER */}
      <div className="flex-shrink-0 border-t p-3 text-center" style={{
        borderColor: 'var(--border2)'
      }}>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          Laboratorium Geodesi & Geomatika UGM @ 2026
        </p>
      </div>
    </aside>
  );
}
