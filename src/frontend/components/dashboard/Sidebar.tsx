'use client';

import React, { useState } from 'react';
import type { SimulationParams, SWEResult, TESData } from '@/types';
import SourceSelector from '@/components/dashboard/controls/SourceSelector';
import SimulationParameters from '@/components/dashboard/controls/SimulationParameters';
import FaultSelector from '@/components/dashboard/controls/FaultSelector';
import DetailedParameterControls from '@/components/dashboard/controls/DetailedParameterControls';
import { SimulationProgress } from '@/components/ui/ProgressBar';

interface SidebarProps {
  onSimulationRun?: (params: SimulationParams) => Promise<void>;
  isLoading?: boolean;
  sweResult?: SWEResult | null;
  tesList?: TESData[];
  customEpicenter?: { lat: number; lon: number } | null;
  isPickingEpicenter?: boolean;
  onPickEpicenterToggle?: () => void;
  onResetEpicenter?: () => void;
}

export default function Sidebar({
  onSimulationRun,
  isLoading = false,
  sweResult,
  tesList = [],
  customEpicenter,
  isPickingEpicenter = false,
  onPickEpicenterToggle,
  onResetEpicenter,
}: SidebarProps) {
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
      fault_type: faultType,
      fault_id: sourceMode === 'custom' ? null : selectedFault,
      source_mode: sourceMode,
      depth,
      length,
      rake,
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
      await new Promise(resolve => setTimeout(resolve, 800)); // Simulate step duration
    }

    await onSimulationRun(params);
    setSimulationStep(simulationSteps.length);
  };

  return (
    <aside
      className="w-80 flex-shrink-0 flex flex-col border-r overflow-y-auto"
      style={{
        background: 'var(--panel)',
        borderColor: 'var(--border)',
      }}
    >
      <div className="p-3 flex-shrink-0 border-b" style={{
        background: 'rgba(0, 30, 60, 0.35)',
        borderColor: 'rgba(56, 189, 248, 0.18)',
      }}>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{
            background: 'linear-gradient(135deg, #003060, #0077cc)',
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

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        <FaultSelector
          selectedFault={selectedFault}
          onSelectFault={setSelectedFault}
        />

        <SourceSelector
          sourceMode={sourceMode}
          onSourceModeChange={setSourceMode}
          selectedFault={selectedFault}
          onSelectFault={setSelectedFault}
          customEpicenter={customEpicenter ?? null}
          isPickingEpicenter={isPickingEpicenter}
          onPickEpicenterToggle={onPickEpicenterToggle ?? (() => undefined)}
          onResetEpicenter={onResetEpicenter ?? (() => undefined)}
        />

        <DetailedParameterControls
          magnitude={magnitude}
          onMagnitudeChange={setMagnitude}
          faultType={faultType}
          onFaultTypeChange={setFaultType}
          depth={depth}
          onDepthChange={setDepth}
          length={length}
          onLengthChange={setLength}
          rake={rake}
          onRakeChange={setRake}
        />

        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
            Probe Kedalaman (Hover Peta)
          </div>
          <div className="p-3 rounded-md border" style={{
            background: 'rgba(0, 18, 45, 0.55)',
            borderColor: 'var(--border)',
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

        {isLoading && (
          <SimulationProgress
            currentStep={simulationStep}
            totalSteps={simulationSteps.length}
            stepLabels={simulationSteps}
            isRunning={isLoading}
          />
        )}

        <SimulationParameters
          magnitude={magnitude}
          onMagnitudeChange={setMagnitude}
          faultType={faultType}
          onFaultTypeChange={setFaultType}
          magnitudePresets={magnitudePresets}
          sourceMode={sourceMode}
          customEpicenter={customEpicenter ?? null}
          isLoading={isLoading}
          onRunSimulation={handleRunSimulation}
        />

        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--muted)' }}>
            Layer Peta
          </div>
          <div className="text-xs text-center py-4" style={{ color: 'var(--muted)' }}>
            Layer controls akan ditambahkan di sini
          </div>
        </div>
      </div>

      <div className="flex-shrink-0 border-t p-3 text-center" style={{ borderColor: 'var(--border2)' }}>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          Laboratorium Geodesi & Geomatika UGM @ 2026
        </p>
      </div>
    </aside>
  );
}
