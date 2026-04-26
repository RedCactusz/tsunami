'use client';

import React, { useState } from 'react';
import type { SimulationParams, RoutingParams, ABMParams, SWEResult, RoutingResult, ABMResult, TESData } from '@/types';
import SourceSelector from '@/components/dashboard/controls/SourceSelector';
import SimulationParameters from '@/components/dashboard/controls/SimulationParameters';
import FaultSelector from '@/components/dashboard/controls/FaultSelector';
import DetailedParameterControls from '@/components/dashboard/controls/DetailedParameterControls';
import { SimulationProgress } from '@/components/ui/ProgressBar';
import RouteAnalysisPanel from '@/components/dashboard/controls/RouteAnalysisPanel';
import ABMPanel from '@/components/dashboard/controls/ABMPanel';
import TransportModeSelector from '@/components/dashboard/controls/TransportModeSelector';
import SafetyWeightSlider from '@/components/dashboard/controls/SafetyWeightSlider';

interface UnifiedPanelProps {
  onSimulationRun?: (params: SimulationParams) => Promise<void>;
  onAnalyzeRoutes?: (params: RoutingParams) => Promise<void>;
  onRunABM?: (params: ABMParams) => Promise<void>;
  isLoading?: boolean;
  sweResult?: SWEResult | null;
  routingResult?: RoutingResult | null;
  abmResult?: ABMResult | null;
  tesList?: TESData[];
  hasSimulated?: boolean;
  customEpicenter?: { lat: number; lon: number } | null;
  isPickingEpicenter?: boolean;
  onPickEpicenterToggle?: () => void;
  onResetEpicenter?: () => void;
  customOrigin?: { lat: number; lon: number } | null;
  isPickingOrigin?: boolean;
  onPickOriginToggle?: () => void;
  onResetOrigin?: () => void;
}

type TabType = 'simulation' | 'routing';

export default function UnifiedPanel({
  onSimulationRun,
  onAnalyzeRoutes,
  onRunABM,
  isLoading = false,
  sweResult,
  routingResult,
  abmResult,
  tesList = [],
  hasSimulated = false,
  customEpicenter,
  isPickingEpicenter = false,
  onPickEpicenterToggle,
  onResetEpicenter,
  customOrigin,
  isPickingOrigin = false,
  onPickOriginToggle,
  onResetOrigin,
}: UnifiedPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('simulation');
  const [routingActiveTab, setRoutingActiveTab] = useState<'network' | 'abm'>('network');
  const [transportMode, setTransportMode] = useState<'foot' | 'motor' | 'car'>('foot');
  const [safetyWeight, setSafetyWeight] = useState(25);

  // Sidebar states
  const [magnitude, setMagnitude] = useState(7.5);
  const [faultType, setFaultType] = useState<'vertical' | 'horizontal' | 'thrust'>('vertical');
  const [selectedFault, setSelectedFault] = useState<string | null>(null);
  const [sourceMode, setSourceMode] = useState<'fault' | 'mega' | 'custom'>('fault');
  const magnitudePresets = [6, 6.5, 7, 7.5, 8, 8.5, 9];

  // Detailed parameters
  const [depth, setDepth] = useState(15);
  const [length, setLength] = useState(100);
  const [rake, setRake] = useState(0);

  // Simulation progress
  const [simulationStep, setSimulationStep] = useState(0);
  const simulationSteps = [
    'Initializing simulation parameters',
    'Loading fault geometry',
    'Calculating seismic source',
    'Running tsunami propagation',
    'Computing inundation areas',
    'Generating impact assessment',
    'Finalizing results'
  ];

  const handleRunSimulation = async () => {
    if (!onSimulationRun) return;

    setSimulationStep(0);

    const params: SimulationParams = {
      magnitude,
      fault_type: faultType as 'vertical' | 'horizontal',
      fault_id: sourceMode === 'custom' ? null : selectedFault,
      source_mode: sourceMode,
      depth_km: depth,
      ...(sourceMode === 'custom' && customEpicenter
        ? {
            lat: customEpicenter.lat,
            lon: customEpicenter.lon,
          }
        : {}),
    };

    // Simulate progress steps
    for (let i = 0; i < simulationSteps.length; i++) {
      setSimulationStep(i + 1);
      await new Promise(resolve => setTimeout(resolve, 800));
    }

    try {
      await onSimulationRun(params);
    } catch (error) {
      console.error('Simulation failed:', error);
    }
  };

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col border-r overflow-y-auto h-screen"
      style={{
        background: 'var(--panel)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Tab Navigation */}
      <div className="p-3 flex-shrink-0 border-b flex items-center justify-between"
        style={{
          background: 'rgba(6, 13, 27, 0.8)',
          borderColor: 'var(--border)',
        }}
      >
        <div className="flex gap-2 w-full">
          <button
            onClick={() => setActiveTab('simulation')}
            className="flex-1 text-xs px-3 py-2 rounded font-semibold border transition-all"
            style={{
              background: activeTab === 'simulation' ? 'rgba(56, 189, 248, 0.18)' : 'rgba(0, 18, 45, 0.6)',
              borderColor: activeTab === 'simulation' ? 'var(--accent)' : 'var(--border)',
              color: activeTab === 'simulation' ? 'var(--accent)' : 'var(--muted)',
            }}
          >
            🌊 Simulasi
          </button>
          <button
            onClick={() => setActiveTab('routing')}
            className="flex-1 text-xs px-3 py-2 rounded font-semibold border transition-all"
            style={{
              background: activeTab === 'routing' ? 'rgba(56, 189, 248, 0.18)' : 'rgba(0, 18, 45, 0.6)',
              borderColor: activeTab === 'routing' ? 'var(--accent)' : 'var(--border)',
              color: activeTab === 'routing' ? 'var(--accent)' : 'var(--muted)',
            }}
          >
            🚩 Evakuasi
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {/* SIMULATION TAB */}
        {activeTab === 'simulation' && (
          <div className="space-y-4">
            <div className="pb-4 border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--accent)' }}>
                Pemodelan Tsunami
              </div>
              <div className="text-xs" style={{ color: 'var(--muted)' }}>
                Simulasi Gelombang & Dampak
              </div>
            </div>

            <SourceSelector
              sourceMode={sourceMode}
              onSourceModeChange={setSourceMode}
              selectedFault={selectedFault}
              onSelectFault={setSelectedFault}
              customEpicenter={customEpicenter || null}
              isPickingEpicenter={isPickingEpicenter}
              onPickEpicenterToggle={onPickEpicenterToggle || (() => {})}
              onResetEpicenter={onResetEpicenter || (() => {})}
            />

            <SimulationParameters
              magnitude={magnitude}
              onMagnitudeChange={setMagnitude}
              magnitudePresets={magnitudePresets}
              faultType={faultType as 'vertical' | 'horizontal'}
              onFaultTypeChange={(value) => setFaultType(value as 'vertical' | 'horizontal' | 'thrust')}
              sourceMode={sourceMode}
              customEpicenter={customEpicenter || null}
              isLoading={isLoading}
              onRunSimulation={handleRunSimulation}
            />

            {sourceMode !== 'custom' && (
              <FaultSelector
                selectedFault={selectedFault}
                onSelectFault={setSelectedFault}
              />
            )}

            <DetailedParameterControls
              magnitude={magnitude}
              onMagnitudeChange={setMagnitude}
              faultType={faultType}
              onFaultTypeChange={setFaultType}
              depth={depth}
              length={length}
              rake={rake}
              onDepthChange={setDepth}
              onLengthChange={setLength}
              onRakeChange={setRake}
            />

            {sweResult && (
              <div className="p-3 rounded-lg border" style={{
                background: 'rgba(52, 211, 153, 0.08)',
                borderColor: 'rgba(52, 211, 153, 0.18)',
              }}>
                <div className="text-xs font-semibold mb-2" style={{ color: '#44ff88' }}>
                  ✓ Hasil Simulasi Tersedia
                </div>
                <div className="text-xs space-y-1" style={{ color: 'var(--muted)' }}>
                  <p>Max Wave: {sweResult.max_inundation_m?.toFixed(2) || 'N/A'} m</p>
                  <p>Area: {sweResult.affected_area_km2?.toFixed(2) || 'N/A'} km²</p>
                </div>
              </div>
            )}

            {isLoading && (
              <SimulationProgress 
                currentStep={simulationStep} 
                totalSteps={simulationSteps.length}
                stepLabels={simulationSteps}
                isRunning={isLoading}
              />
            )}
          </div>
        )}

        {/* ROUTING TAB */}
        {activeTab === 'routing' && (
          <div className="space-y-4">
            <div className="pb-4 border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: '#44ff88' }}>
                Rute Evakuasi
              </div>
              <div className="text-xs" style={{ color: 'var(--muted)' }}>
                Analisis Jaringan · DEM + Lereng
              </div>
            </div>

            {/* Sub-tabs for routing */}
            <div className="flex gap-2">
              {(['network', 'abm'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setRoutingActiveTab(tab)}
                  className="flex-1 text-xs px-2 py-1 rounded font-semibold border transition-all"
                  style={{
                    background: routingActiveTab === tab ? 'rgba(56, 189, 248, 0.18)' : 'rgba(0, 18, 45, 0.6)',
                    borderColor: routingActiveTab === tab ? 'var(--accent)' : 'var(--border)',
                    color: routingActiveTab === tab ? 'var(--accent)' : 'var(--muted)',
                  }}
                >
                  {tab === 'network' ? '🛣 Rute' : '🤖 ABM'}
                </button>
              ))}
            </div>

            {routingActiveTab === 'network' && (
              <div className="space-y-3">
                <TransportModeSelector
                  selectedMode={transportMode}
                  onModeChange={setTransportMode}
                />
                <SafetyWeightSlider
                  value={safetyWeight}
                  onChange={setSafetyWeight}
                />
                <RouteAnalysisPanel
                  transportMode={transportMode}
                  onTransportModeChange={setTransportMode}
                  safetyWeight={safetyWeight}
                  onSafetyWeightChange={setSafetyWeight}
                  onAnalyzeRoutes={onAnalyzeRoutes}
                  isLoading={isLoading}
                  tesList={tesList}
                  customOrigin={customOrigin || null}
                  isPickingOrigin={isPickingOrigin}
                  onPickOriginToggle={onPickOriginToggle || (() => {})}
                  onResetOrigin={onResetOrigin || (() => {})}
                />
              </div>
            )}

            {routingActiveTab === 'abm' && (
              <ABMPanel
                transportMode={transportMode}
                onRunABM={onRunABM}
                isLoading={isLoading}
                hasSimulated={hasSimulated}
              />
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
