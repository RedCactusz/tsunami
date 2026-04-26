'use client';

import React from 'react';
import type { ImpactResult, SWEResult, RoutingResult } from '@/types';

interface BottomBarProps {
  simulationActive?: boolean;
  impactResult?: ImpactResult | null;
  sweResult?: SWEResult | null;
  routingResult?: RoutingResult | null;
}

const BottomBar: React.FC<BottomBarProps> = ({ simulationActive = false, impactResult, sweResult, routingResult }) => {
  return (
    <div className="flex-shrink-0 flex border-t overflow-hidden h-56"
      style={{
        background: 'rgba(6, 13, 27, 0.98)',
        borderColor: 'var(--border)'
      }}
    >
      {/* SECTION 1: Data Penduduk Table */}
      <div className="flex-1.4 flex flex-col border-r p-3"
        style={{ borderColor: 'var(--border2)' }}
      >
        <div className="text-xs font-bold uppercase mb-2 flex-shrink-0" style={{ color: 'var(--muted)' }}>
          🏘 Data Penduduk Terdampak per Desa
          <span className="text-xs ml-2 px-1.5 py-0.5 rounded text-cyan-400 border border-cyan-600 border-opacity-20" style={{ fontSize: '10px' }}>
            {simulationActive ? 'Simulasi Berjalan' : 'Menunggu Simulasi'}
          </span>
        </div>
        <div className="flex-1 overflow-y-auto text-xs">
          <table className="w-full border-collapse" style={{ fontSize: '10px' }}>
            <thead>
              <tr className="sticky top-0" style={{ 
                background: 'var(--panel2)',
                borderBottom: '1px solid ' + 'var(--border)'
              }}>
                <th className="text-left px-2 py-1" style={{ color: 'var(--muted)' }}>Desa</th>
                <th className="text-right px-2 py-1" style={{ color: 'var(--muted)' }}>Penduduk</th>
                <th className="text-right px-2 py-1" style={{ color: 'var(--muted)' }}>Terdampak</th>
                <th className="text-right px-2 py-1" style={{ color: 'var(--muted)' }}>%</th>
                <th className="text-center px-2 py-1" style={{ color: 'var(--muted)' }}>Zona</th>
              </tr>
            </thead>
            <tbody>
              {[
                { desa: 'Gadingsari', penduduk: 4250, terdampak: 2140, pct: 50, zona: 'Tinggi' },
                { desa: 'Srigading', penduduk: 3820, terdampak: 1910, pct: 50, zona: 'Sedang' },
                { desa: 'Tirtosari', penduduk: 3100, terdampak: 1550, pct: 50, zona: 'Rendah' },
              ].map((row, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid rgba(56, 189, 248, 0.04)' }}>
                  <td className="px-2 py-1" style={{ color: 'var(--text2)' }}>{row.desa}</td>
                  <td className="text-right px-2 py-1" style={{ color: 'var(--text2)' }}>{row.penduduk.toLocaleString('id-ID')}</td>
                  <td className="text-right px-2 py-1" style={{ color: 'var(--text2)' }}>{row.terdampak}</td>
                  <td className="text-right px-2 py-1" style={{ color: 'var(--text2)' }}>{row.pct}%</td>
                  <td className="text-center px-1 py-1">
                    <span className="text-xs px-1.5 py-0.5 rounded font-bold whitespace-nowrap" style={{
                      background: `rgba(${row.zona === 'Tinggi' ? '248,113,113' : row.zona === 'Sedang' ? '251,146,60' : '255,230,80'}, 0.15)`,
                      color: `${row.zona === 'Tinggi' ? '#f87171' : row.zona === 'Sedang' ? '#fb923c' : '#ffe650'}`
                    }}>
                      {row.zona}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* SECTION 2: Bar Chart Placeholder */}
      <div className="flex-1.2 flex flex-col border-r p-3"
        style={{ borderColor: 'var(--border2)' }}
      >
        <div className="text-xs font-bold uppercase mb-2" style={{ color: 'var(--muted)' }}>
          📊 Grafik Penduduk Terdampak
        </div>
        <div className="flex-1 flex items-center justify-center text-xs" style={{ color: 'var(--muted)' }}>
          [Chart Area - Chart.js akan dirender di sini]
        </div>
      </div>

      {/* SECTION 3: Donut Chart Placeholder */}
      <div className="flex-0.8 flex flex-col border-r p-3"
        style={{ borderColor: 'var(--border2)' }}
      >
        <div className="text-xs font-bold uppercase mb-2" style={{ color: 'var(--muted)' }}>
          🗂 Distribusi Zona Bahaya
        </div>
        <div className="flex-1 flex items-center justify-center text-xs" style={{ color: 'var(--muted)' }}>
          [Donut Chart]
        </div>
      </div>

      {/* SECTION 4: Summary */}
      <div className="flex-0.85 flex flex-col p-3">
        <div className="text-xs font-bold uppercase mb-2" style={{ color: 'var(--muted)' }}>
          📋 Ringkasan Dampak
        </div>
        <div className="grid grid-cols-2 gap-1 flex-1 mb-2">
          {[
            { value: '12.840', label: 'SANGAT TINGGI', color: '#ff4444' },
            { value: '18.430', label: 'ZONA TINGGI', color: '#ff6400' },
            { value: '11.340', label: 'ZONA SEDANG', color: '#ffb400' },
            { value: '5.222', label: 'ZONA RENDAH', color: '#ffe650' },
          ].map((stat, idx) => (
            <div
              key={idx}
              className="rounded-md p-1.5 text-center"
              style={{
                background: 'rgba(0, 18, 45, 0.6)',
                border: '1px solid var(--border2)'
              }}
            >
              <div className="text-sm font-bold" style={{ color: stat.color }}>{stat.value}</div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>{stat.label}</div>
            </div>
          ))}
        </div>
        <div className="rounded-md p-2 flex justify-between items-center" style={{
          background: 'rgba(56, 189, 248, 0.07)',
          border: '1px solid rgba(56, 189, 248, 0.18)'
        }}>
          <div>
            <div className="text-xs" style={{ color: 'var(--muted)' }}>TOTAL TERDAMPAK</div>
            <div className="text-base font-bold" style={{ color: 'var(--accent)' }}>47.832</div>
          </div>
          <div className="text-right">
            <div className="text-xs" style={{ color: 'var(--muted)' }}>DARI TOTAL</div>
            <div className="text-xs font-bold" style={{ color: '#fb923c' }}>53.5%</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BottomBar;
