'use client';

import React, { useState } from 'react';
import type { RoutingParams, ABMParams, RoutingResult, ABMResult, TESData } from '@/types';

interface RightPanelProps {
  onAnalyzeRoutes?: (params: RoutingParams) => Promise<void>;
  onRunABM?: (params: ABMParams) => Promise<void>;
  isLoading?: boolean;
  routingResult?: RoutingResult | null;
  abmResult?: ABMResult | null;
  tesList?: TESData[];
  hasSimulated?: boolean;
}

export default function RightPanel({ onAnalyzeRoutes, onRunABM, isLoading = false, routingResult, abmResult, tesList = [], hasSimulated = false }: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<'network' | 'abm'>('network');
  const [transportMode, setTransportMode] = useState<'foot' | 'motor' | 'car'>('foot');
  const [safetyWeight, setSafetyWeight] = useState(25);

  const transportModes = [
    { id: 'foot', label: 'Jalan Kaki', speed: '~4 km/j', icon: '🚶' },
    { id: 'motor', label: 'Motor', speed: '~30 km/j', icon: '🏍' },
    { id: 'car', label: 'Mobil', speed: '~40 km/j', icon: '🚗' },
  ];

  const tes = [
    { id: 'tes-1', name: 'TES-01 — TES Masjid Al Huda', capacity: 150 },
    { id: 'tes-2', name: 'TES-02 — TES BPP Srandakan', capacity: 200 },
    { id: 'tes-3', name: 'TES-03 — TES SD Muh Gunturgeni', capacity: 180 },
  ];

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col border-l overflow-y-auto h-screen"
      style={{
        background: 'var(--panel)',
        borderColor: 'var(--border)'
      }}
    >
      {/* HEADER PANEL */}
      <div className="p-3 flex-shrink-0 border-b flex items-center gap-2"
        style={{
          background: 'rgba(3, 46, 25, 0.25)',
          borderColor: 'rgba(52, 211, 153, 0.18)'
        }}
      >
        <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{
          background: 'linear-gradient(135deg, #004d20, #00cc66)'
        }}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 64 64" className="fill-white">
            <path d="M8,54 L8,22 L32,8 L56,22 L56,54" stroke="white" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <div className="text-xs font-bold uppercase tracking-widest" style={{ color: '#44ff88' }}>
            RUTE EVAKUASI
          </div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>
            Analisis Jaringan · DEM + Lereng
          </div>
        </div>
        
        {/* Tab Switcher */}
        <div className="ml-auto flex gap-1">
          {(['network', 'abm'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="text-xs px-2 py-1 rounded font-semibold border transition-all"
              style={{
                background: activeTab === tab ? 'rgba(56, 189, 248, 0.18)' : 'rgba(0, 18, 45, 0.6)',
                borderColor: activeTab === tab ? 'var(--accent)' : 'var(--border)',
                color: activeTab === tab ? 'var(--accent)' : 'var(--muted)'
              }}
            >
              {tab === 'network' ? '🛣 Rute' : '🤖 ABM'}
            </button>
          ))}
        </div>
      </div>

      {/* SCROLLABLE CONTENT */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        
        {/* NETWORK ANALYSIS PANEL */}
        {activeTab === 'network' && (
          <>
            {/* OSM Roads Status */}
            <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
              <div className="flex items-center gap-2 p-2 rounded-md mb-3" style={{
                background: 'rgba(0, 18, 45, 0.6)',
                border: '1px solid var(--border2)'
              }}>
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{
                  background: '#4ade80',
                  boxShadow: '0 0 6px #4ade80'
                }}></div>
                <span className="flex-1 text-xs" style={{ color: 'var(--muted)' }}>
                  Data jalan OSM dimuat
                </span>
                <button className="text-xs px-2 py-1 rounded border font-semibold transition-all" style={{
                  background: 'rgba(56, 189, 248, 0.12)',
                  borderColor: 'rgba(56, 189, 248, 0.25)',
                  color: 'var(--accent)'
                }}>
                  🔄 Muat
                </button>
              </div>
            </div>

            {/* Origin & Destination */}
            <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
              <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
                Titik Asal & Tujuan
              </div>
              
              <div className="mb-2">
                <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>📍 Titik Asal (Zona Bahaya)</div>
                <button className="w-full flex items-center gap-2 px-2 py-2 rounded-md border-2 border-dashed font-semibold text-xs" style={{
                  borderColor: 'var(--accent)',
                  background: 'rgba(56, 189, 248, 0.12)',
                  color: 'var(--accent)'
                }}>
                  🖱️ Klik peta untuk tentukan titik asal
                </button>
              </div>

              <div>
                <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>🏁 Titik Tujuan (TES)</div>
                <select className="w-full text-xs">
                  <option>— Pilih TES —</option>
                  {tes.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Transport Mode */}
            <div className="mb-4 pb-4 border-b" style={{ borderColor: 'var(--border2)' }}>
              <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
                Moda Transportasi
              </div>
              <div className="grid grid-cols-3 gap-2">
                {transportModes.map(mode => (
                  <button
                    key={mode.id}
                    onClick={() => setTransportMode(mode.id as any)}
                    className="p-2 rounded-md border text-xs font-bold text-center transition-all"
                    style={{
                      background: transportMode === mode.id ? 'rgba(56, 189, 248, 0.14)' : 'rgba(0, 15, 40, 0.5)',
                      borderColor: transportMode === mode.id ? 'var(--accent)' : 'var(--border)',
                      color: transportMode === mode.id ? 'var(--accent)' : 'var(--muted)'
                    }}
                  >
                    <div className="text-lg mb-1">{mode.icon}</div>
                    {mode.label}
                  </button>
                ))}
              </div>
              <div className="mt-2 text-xs p-2 rounded-md" style={{
                background: 'rgba(0, 18, 45, 0.5)',
                color: 'var(--muted)',
                lineHeight: '1.7'
              }}>
                🚶 <b style={{ color: 'var(--accent)' }}>Jalan Kaki</b> — Kecepatan ~4 km/j. Jalur kaki lebih fleksibel.
              </div>
            </div>

            {/* Analysis Method */}
            <div className="mb-4 pb-4">
              <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
                Metode Analisis
              </div>
              
              <div className="p-2 rounded-md mb-2" style={{
                background: 'rgba(56, 189, 248, 0.07)',
                border: '1px solid rgba(56, 189, 248, 0.2)'
              }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">🛣</span>
                  <span className="text-xs font-bold" style={{ color: 'var(--accent)' }}>Jalur Terpendek + DEM</span>
                  <span className="ml-auto text-xs px-2 py-1 rounded" style={{
                    background: 'rgba(74, 222, 128, 0.15)',
                    color: '#4ade80'
                  }}>✓ Aktif</span>
                </div>
                <div className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>
                  Network analysis dengan <b style={{ color: 'var(--text)' }}>composite cost</b>: bobot jarak, waktu tempuh, <b style={{ color: '#34d399' }}>elevasi DEM</b>, dan <b style={{ color: '#a78bfa' }}>kemiringan lereng</b>.
                </div>
              </div>

              {/* Safety Weight Slider */}
              <div className="mb-3">
                <div className="flex justify-between items-center text-xs mb-1">
                  <span>⛰ Prioritas Elevasi & Slope</span>
                  <span style={{ color: 'var(--accent)', fontWeight: 'bold' }}>{safetyWeight}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="60"
                  value={safetyWeight}
                  onChange={(e) => setSafetyWeight(parseInt(e.target.value))}
                  className="w-full"
                  style={{ accentColor: '#4ade80' }}
                />
              </div>

              {/* Analyze Button */}
              <button
                onClick={onAnalyzeRoutes}
                className="w-full py-2 rounded-lg font-bold text-xs uppercase text-white transition-all"
                style={{
                  background: 'linear-gradient(135deg, #064e3b, #059669)',
                  boxShadow: '0 4px 18px rgba(5, 150, 105, 0.3)',
                  letterSpacing: '1px'
                }}
              >
                🛣 ANALISIS RUTE EVAKUASI
              </button>
            </div>

            {/* TES Data */}
            <div className="pb-4">
              <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>
                Titik Evakuasi Sementara (TES)
                <span className="float-right font-bold" style={{ color: 'var(--ok)' }}>2.450</span>
              </div>
              <div className="flex flex-col gap-2 max-h-40 overflow-y-auto">
                {tes.map(t => (
                  <div
                    key={t.id}
                    className="p-2 rounded-md border text-xs cursor-pointer transition-all"
                    style={{
                      background: 'rgba(0, 15, 40, 0.4)',
                      borderColor: 'rgba(56, 189, 248, 0.08)',
                      color: 'var(--text)'
                    }}
                  >
                    <div className="font-semibold">{t.name}</div>
                    <div style={{ color: 'var(--muted)', marginTop: '2px' }}>
                      Kapasitas: {t.capacity} orang
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* ABM PANEL */}
        {activeTab === 'abm' && (
          <>
            <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
              Parameter ABM Evakuasi
            </div>

            <div className="grid grid-cols-2 gap-2 mb-4">
              <div>
                <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>⏰ Waktu Peringatan (mnt)</div>
                <input type="number" defaultValue={20} min={5} max={60} className="w-full" />
              </div>
              <div>
                <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>⏱ Durasi Simulasi (mnt)</div>
                <input type="number" defaultValue={120} min={30} max={360} className="w-full" />
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
                  defaultValue="5"
                  className="flex-1"
                  style={{ accentColor: '#f87171' }}
                />
                <span className="text-sm font-bold" style={{ color: '#f87171', minWidth: '40px' }}>
                  5 m
                </span>
              </div>
            </div>

            <button
              onClick={onRunABM}
              className="w-full py-2 rounded-lg font-bold text-xs uppercase text-white transition-all"
              style={{
                background: 'linear-gradient(135deg, #1a0050, #7c3aed)',
                boxShadow: '0 4px 18px rgba(124, 58, 237, 0.3)',
                letterSpacing: '1px'
              }}
            >
              🤖 JALANKAN SIMULASI ABM
            </button>

            <div className="mt-4 text-xs text-center" style={{ color: 'var(--muted)' }}>
              Simulasi ABM belum dijalankan
            </div>
          </>
        )}

      </div>
    </aside>
  );
}
