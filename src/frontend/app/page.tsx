"use client";

import 'leaflet/dist/leaflet.css';

import React, { useState } from 'react';
import BottomBar from '@/components/dashboard/BottomBar';
import UnifiedPanel from '@/components/dashboard/UnifiedPanel';
import MapComponent from '@/components/map/Map';
import Header from '@/components/ui/Header';

import { useSimulation } from '@/hooks/useSimulation';
import type { ABMParams, RoutingParams, SimulationParams } from '@/types';

export default function WebGISPage() {
  const sim = useSimulation();
  const [customEpicenter, setCustomEpicenter] = useState<{ lat: number; lon: number } | null>(null);
  const [isPickingEpicenter, setIsPickingEpicenter] = useState(false);
  const [customOrigin, setCustomOrigin] = useState<{ lat: number; lon: number } | null>(null);
  const [isPickingOrigin, setIsPickingOrigin] = useState(false);
  const [selectedFault, setSelectedFault] = useState<string | null>(null);

  const handleSimulationRun = async (params: SimulationParams) => {
    await sim.startSimulation(params);
  };

  const handleAnalyzeRoutes = async (params: RoutingParams) => {
    await sim.startRouting(params);
  };

  const handleRunABM = async (params: ABMParams) => {
    await sim.startABM(params);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden" style={{ background: 'var(--bg)' }}>

      <Header
        serverStatus={sim.serverStatus}
        onRefreshServer={sim.refreshServer}
      />

      {/* Loading Overlay */}
      {sim.isLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(6,13,27,0.75)', backdropFilter: 'blur(4px)' }}>
          <div className="flex flex-col items-center gap-4 px-8 py-6 rounded-xl border"
            style={{ background: 'var(--panel)', borderColor: 'var(--border)', boxShadow: 'var(--shadow)' }}>
            <div className="w-10 h-10 rounded-full border-4 animate-spin"
              style={{ borderColor: 'rgba(56,189,248,0.15)', borderTopColor: 'var(--accent)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text2)' }}>
              {sim.loadingMessage}
            </p>
          </div>
        </div>
      )}

      {/* Sidebar */}

      {/* Error Toast */}
      {sim.error && (
        <div className="fixed top-14 right-4 z-50 px-4 py-3 rounded-lg border text-sm font-semibold"
          style={{ background: 'rgba(248,65,65,0.12)', borderColor: 'rgba(248,113,113,0.35)', color: '#f87171', maxWidth: '360px' }}>
          ⚠ {sim.error}
          <button onClick={sim.resetResults} className="ml-3 underline text-xs opacity-70 hover:opacity-100">Tutup</button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden relative">
        <UnifiedPanel
          onSimulationRun={handleSimulationRun}
          onAnalyzeRoutes={handleAnalyzeRoutes}
          onRunABM={handleRunABM}
          isLoading={sim.isLoading}
          sweResult={sim.sweResult}
          routingResult={sim.routingResult}
          abmResult={sim.abmResult}
          tesList={sim.tesList}
          faultData={sim.faultData}
          hasSimulated={sim.hasSimulated}
          customEpicenter={customEpicenter}
          isPickingEpicenter={isPickingEpicenter}
          onPickEpicenterToggle={() => setIsPickingEpicenter((prev) => !prev)}
          onResetEpicenter={() => setCustomEpicenter(null)}
          customOrigin={customOrigin}
          isPickingOrigin={isPickingOrigin}
          onPickOriginToggle={() => setIsPickingOrigin((prev) => !prev)}
          onResetOrigin={() => setCustomOrigin(null)}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <MapComponent
            onBasemapChange={(basemap) => console.log('Basemap:', basemap)}
            onLayerToggle={(layerId, isVisible) => console.log('Layer:', layerId, isVisible)}
            onZoomPreset={(preset) => console.log('Zoom preset:', preset)}
            onExport={(type, format) => console.log('Export:', type, format)}
            desaList={sim.desaList}
            tesList={sim.tesList}
            sweResult={sim.sweResult}
            routingResult={sim.routingResult}
            abmResult={sim.abmResult}
            customEpicenter={customEpicenter}
            isPickingEpicenter={isPickingEpicenter}
            onEpicenterSelect={(coords) => {
              setCustomEpicenter(coords);
              setIsPickingEpicenter(false);
            }}
            customOrigin={customOrigin}
            isPickingOrigin={isPickingOrigin}
            onOriginSelect={(coords) => {
              setCustomOrigin(coords);
              setIsPickingOrigin(false);
            }}
            selectedFault={sim.selectedFault}
            faultData={sim.faultData}
          />
          {/* <BottomBar
            simulationActive={sim.hasSimulated}
            impactResult={sim.impactResult}
            sweResult={sim.sweResult}
            routingResult={sim.routingResult}
          /> */}
        </div>
      </div>
    </div>
  );
}
