'use client';

import React from 'react';
import type { ServerStatus } from '@/types';

interface StatusBadgeProps {
  icon: React.ReactNode;
  label: string;
  status: 'online' | 'offline' | 'loading';
  title?: string;
}

interface HeaderProps {
  serverStatus?: ServerStatus;
  onRefreshServer?: () => Promise<ServerStatus>;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ icon, label, status, title }) => {
  const dotClass = {
    online: 'bg-emerald-400 shadow-[0_0_8px_#34d399]',
    offline: 'bg-gray-600',
    loading: 'bg-amber-400 shadow-[0_0_8px_#fbbf24]'
  }[status];

  return (
    <div 
      title={title}
      className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-slate-900 to-slate-800 border border-cyan-600 border-opacity-20 rounded-md backdrop-blur-sm hover:border-cyan-500 hover:border-opacity-40 transition-all duration-200 shadow-sm"
    >
      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${dotClass}`}></div>
      <span className="text-xs font-bold text-cyan-300 uppercase tracking-wide">{label}</span>
    </div>
  );
};

export default function Header({ serverStatus = 'offline', onRefreshServer }: HeaderProps) {
  // Status badges currently use hardcoded values - could be enhanced to use serverStatus and onRefreshServer
  return (
    <header className="flex-shrink-0 bg-gradient-to-r from-slate-900 from-90% to-slate-800 border-b border-cyan-600 border-opacity-14 px-6 py-3 flex items-center gap-4 z-50 shadow-sm"
      style={{
        background: 'linear-gradient(90deg, rgba(6,13,27,.98) 0%, rgba(10,22,44,.98) 100%)',
        boxShadow: 'var(--shadow-sm)'
      }}
    >
      {/* Logo Section */}
      <div className="flex items-center gap-3">
        <div className="flex gap-2 items-center">
          {/* Icon Risiko Bencana */}
          <div className="relative w-9 h-9 rounded-md overflow-hidden bg-gradient-to-br from-blue-700 to-cyan-600 flex-shrink-0 flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, #003060, #0077cc)',
              boxShadow: '0 0 14px rgba(14,165,233,.35)'
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 64 64" className="fill-white">
              <path d="M4,36 Q12,24 20,36 Q28,48 36,36 Q44,24 52,36 Q58,44 62,36" stroke="white" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M4,48 Q12,36 20,48 Q28,60 36,48 Q44,36 52,48 Q58,56 62,48" stroke="rgba(255,255,255,.45)" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        </div>

        <div className="border-r border-gray-500 border-opacity-30 h-6"></div>

        <div>
          <h1 className="text-sm font-bold text-white tracking-tight">
            SIMULASI EVAKUASI TSUNAMI <span className="text-cyan-400 font-normal">| WebGIS v2</span>
          </h1>
          <p className="text-xs text-cyan-300 opacity-70">Mini Project Komputasi Geospasial</p>
        </div>
      </div>

      {/* Status Badges - Right Side */}
      <div className="ml-auto flex items-center gap-2">
        <StatusBadge 
          label="SERVER DATA"
          status="online"
          title="Status Koneksi Server Bathymetry & DEM"
          icon={<div className="w-2 h-2 bg-emerald-400 rounded-full"></div>}
        />
        <StatusBadge 
          label="PRE-LOADING"
          status="loading"
          title="Status Pre-computasi Grid (GEBCO/BATNAS/DEM)"
          icon={<div className="w-2 h-2 bg-amber-400 rounded-full"></div>}
        />
        <StatusBadge 
          label="VEKTOR"
          status="offline"
          title="Status Layar Vektor (SHP)"
          icon={<div className="w-2 h-2 bg-gray-600 rounded-full"></div>}
        />
      </div>
    </header>
  );
}
