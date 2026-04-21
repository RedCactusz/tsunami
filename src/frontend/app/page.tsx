"use client";

import React, { useState } from 'react';
import 'leaflet/dist/leaflet.css';

import Header from '@/components/ui/Header';
import Sidebar from '@/components/dashboard/Sidebar';
import MapComponent from '@/components/map/Map';
import BottomBar from '@/components/dashboard/BottomBar';
import RightPanel from '@/components/dashboard/RightPanel';

export default function WebGISPage() {
  const [simulationRunning, setSimulationRunning] = useState(false);

  const handleSimulationRun = () => {
    setSimulationRunning(true);
    console.log('Menjalankan simulasi tsunami...');
  };

  const handleAnalyzeRoutes = () => {
    console.log('Menganalisis rute evakuasi...');
  };

  const handleRunABM = () => {
    console.log('Menjalankan simulasi ABM...');
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* HEADER */}
      <Header />

      {/* MAIN 3-COLUMN LAYOUT */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* LEFT SIDEBAR */}
        <Sidebar onSimulationRun={handleSimulationRun} />

        {/* CENTER: MAP + BOTTOM BAR */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <MapComponent onBasemapChange={(basemap) => console.log('Basemap:', basemap)} />
          <BottomBar simulationActive={simulationRunning} />
        </div>

        {/* RIGHT PANEL */}
        <RightPanel onAnalyzeRoutes={handleAnalyzeRoutes} onRunABM={handleRunABM} />
      </div>
    </div>
  );
}
