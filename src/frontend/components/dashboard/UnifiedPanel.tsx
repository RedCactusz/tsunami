'use client';

import React, { useState } from 'react';
import type { SimulationParams, RoutingParams, ABMParams, SWEResult, RoutingResult, ABMResult, TESData } from '@/types';
import SourceSelector from '@/components/dashboard/controls/SourceSelector';
import SimulationParameters from '@/components/dashboard/controls/SimulationParameters';
import FaultSelector from '@/components/dashboard/controls/FaultSelector';
// import DetailedParameterControls from '@/components/dashboard/controls/DetailedParameterControls'; // Hidden - Coming Soon
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
  faultData?: Record<string, {
    label: string;
    mw: number;
    category: string;
    recurrence: string;
    view_lat: number;
    view_lon: number;
    view_zoom: number;
  }>;
  onFaultSelect?: (faultId: string | null) => void;
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
  faultData,
  onFaultSelect,
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
  const [safetyWeight, setSafetyWeight] = useState(25); // Default value (slider hidden)

  // Sidebar states
  const [magnitude, setMagnitude] = useState(7.5);
  const [faultType, setFaultType] = useState<'vertical' | 'horizontal' | 'thrust'>('vertical');
  const [selectedFault, setSelectedFault] = useState<string | null>(null);
  const [sourceMode, setSourceMode] = useState<'fault' | 'mega' | 'custom'>('fault');
  const magnitudePresets = [6, 6.5, 7, 7.5, 8, 8.5, 9];

  // Detailed parameters (hidden - coming soon)
  // const [depth, setDepth] = useState(15);
  // const [length, setLength] = useState(100);
  // const [rake, setRake] = useState(0);
  const depth = 15;  // Default value for simulation
  const length = 100;  // Default value for simulation
  const rake = 0;  // Default value for simulation

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
      depth: depth,
      length: length,
      rake: rake,
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
    <aside className="w-72 flex-shrink-0 flex flex-col border-r overflow-y-auto h-screen bg-white"
      style={{
        borderColor: '#e2e8f0',
      }}
    >
      {/* Tab Navigation */}
      <div className="p-4 flex-shrink-0 border-b"
        style={{
          background: '#f8fafc',
          borderColor: '#e2e8f0',
        }}
      >
        <div className="flex gap-2 w-full">
          <button
            onClick={() => setActiveTab('simulation')}
            className="flex-1 text-sm px-4 py-2.5 rounded-lg font-medium transition-all"
            style={{
              background: activeTab === 'simulation' ? '#3b82f6' : '#ffffff',
              color: activeTab === 'simulation' ? '#ffffff' : '#475569',
              border: activeTab === 'simulation' ? '1px solid #3b82f6' : '1px solid #e2e8f0',
            }}
          >
            🌊 Simulasi
          </button>
          <button
            onClick={() => setActiveTab('routing')}
            className="flex-1 text-sm px-4 py-2.5 rounded-lg font-medium transition-all"
            style={{
              background: activeTab === 'routing' ? '#3b82f6' : '#ffffff',
              color: activeTab === 'routing' ? '#ffffff' : '#475569',
              border: activeTab === 'routing' ? '1px solid #3b82f6' : '1px solid #e2e8f0',
            }}
          >
            🚩 Evakuasi
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {/* SIMULATION TAB */}
        {activeTab === 'simulation' && (
          <div className="space-y-4">
            <div className="pb-4 border-b" style={{ borderColor: '#e2e8f0' }}>
              <div className="text-sm font-semibold mb-1" style={{ color: '#1e293b' }}>
                Pemodelan Tsunami
              </div>
              <div className="text-xs" style={{ color: '#64748b' }}>
                Simulasi Gelombang & Dampak
              </div>
            </div>

            <SourceSelector
              sourceMode={sourceMode}
              onSourceModeChange={setSourceMode}
              selectedFault={selectedFault}
              onSelectFault={(faultId) => {
                setSelectedFault(faultId);
                onFaultSelect?.(faultId);
              }}
              customEpicenter={customEpicenter || null}
              isPickingEpicenter={isPickingEpicenter}
              onPickEpicenterToggle={onPickEpicenterToggle || (() => {})}
              onResetEpicenter={onResetEpicenter || (() => {})}
            />

            {/* Patahan: Tampilkan FaultSelector untuk sesar aktif */}
            {sourceMode === 'fault' && (
              <FaultSelector
                selectedFault={selectedFault}
                onSelectFault={(faultId) => {
                  setSelectedFault(faultId);
                  onFaultSelect?.(faultId);
                }}
                category="fault"
              />
            )}

            {/* Megathrust: Tampilkan FaultSelector untuk megathrust */}
            {sourceMode === 'mega' && (
              <FaultSelector
                selectedFault={selectedFault}
                onSelectFault={(faultId) => {
                  setSelectedFault(faultId);
                  onFaultSelect?.(faultId);
                }}
                category="megathrust"
              />
            )}

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

            {/* Parameter Detail - COMING SOON (Hidden for now) */}
            {/*
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
            */}

            {sweResult && (
              <div className="p-4 rounded-lg border" style={{
                background: '#f0fdf4',
                borderColor: '#86efac',
              }}>
                <div className="text-xs font-semibold mb-3" style={{ color: '#166534' }}>
                  ✓ Hasil Simulasi Tersedia
                </div>
                <div className="text-xs space-y-2" style={{ color: '#475569' }}>
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
            <div className="pb-4 border-b" style={{ borderColor: '#e2e8f0' }}>
              <div className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: '#1e293b' }}>
                Rute Evakuasi
              </div>
              <div className="text-xs" style={{ color: '#64748b' }}>
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
                  className="flex-1 text-xs px-3 py-2 rounded-lg font-semibold border transition-all"
                  style={{
                    background: routingActiveTab === tab ? '#3b82f6' : '#f1f5f9',
                    borderColor: routingActiveTab === tab ? '#3b82f6' : '#cbd5e1',
                    color: routingActiveTab === tab ? '#ffffff' : '#1e293b',
                  }}
                >
                  {tab === 'network' ? '🛣 Rute' : '🤖 ABM'}
                </button>
              ))}
            </div>

            {routingActiveTab === 'network' && (
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
