'use client';

import React, { useState } from 'react';
import type { RoutingParams, ABMParams, RoutingResult, ABMResult, TESData } from '@/types';
import RouteAnalysisPanel from '@/components/dashboard/controls/RouteAnalysisPanel';
import ABMPanel from '@/components/dashboard/controls/ABMPanel';
import TransportModeSelector from '@/components/dashboard/controls/TransportModeSelector';
import SafetyWeightSlider from '@/components/dashboard/controls/SafetyWeightSlider';

interface RightPanelProps {
  onAnalyzeRoutes?: (params: RoutingParams) => Promise<void>;
  onRunABM?: (params: ABMParams) => Promise<void>;
  isLoading?: boolean;
  routingResult?: RoutingResult | null;
  abmResult?: ABMResult | null;
  tesList?: TESData[];
  hasSimulated?: boolean;
  customOrigin?: { lat: number; lon: number } | null;
  isPickingOrigin?: boolean;
  onPickOriginToggle?: () => void;
  onResetOrigin?: () => void;
}

export default function RightPanel({ onAnalyzeRoutes, onRunABM, isLoading = false, routingResult, abmResult, tesList = [], hasSimulated = false, customOrigin, isPickingOrigin = false, onPickOriginToggle, onResetOrigin }: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<'network' | 'abm'>('network');
  const [transportMode, setTransportMode] = useState<'foot' | 'motor' | 'car'>('foot');
  const [safetyWeight, setSafetyWeight] = useState(25);

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col border-l overflow-y-auto h-screen"
      style={{
        background: 'var(--panel)',
        borderColor: 'var(--border)',
      }}
    >
      <div className="p-3 flex-shrink-0 border-b flex items-center gap-2"
        style={{
          background: 'rgba(3, 46, 25, 0.25)',
          borderColor: 'rgba(52, 211, 153, 0.18)',
        }}
      >
        <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{
          background: 'linear-gradient(135deg, #004d20, #00cc66)',
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

        <div className="ml-auto flex gap-1">
          {(['network', 'abm'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className="text-xs px-2 py-1 rounded font-semibold border transition-all"
              style={{
                background: activeTab === tab ? 'rgba(56, 189, 248, 0.18)' : 'rgba(0, 18, 45, 0.6)',
                borderColor: activeTab === tab ? 'var(--accent)' : 'var(--border)',
                color: activeTab === tab ? 'var(--accent)' : 'var(--muted)',
              }}
            >
              {tab === 'network' ? '🛣 Rute' : '🤖 ABM'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {activeTab === 'network' ? (
          <RouteAnalysisPanel
            transportMode={transportMode}
            onTransportModeChange={setTransportMode}
            safetyWeight={safetyWeight}
            onSafetyWeightChange={setSafetyWeight}
            onAnalyzeRoutes={onAnalyzeRoutes}
            isLoading={isLoading}
            tesList={tesList}
            customOrigin={customOrigin}
            isPickingOrigin={isPickingOrigin}
            onPickOriginToggle={onPickOriginToggle}
            onResetOrigin={onResetOrigin}
          />
        ) : (
          <ABMPanel
            transportMode={transportMode}
            onRunABM={onRunABM}
            isLoading={isLoading}
            hasSimulated={hasSimulated}
          />
        )}
      </div>
    </aside>
  );
}
