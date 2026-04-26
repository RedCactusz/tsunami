'use client';

import React, { useState } from 'react';

interface LayerControlProps {
  onLayerToggle?: (layerId: string, isVisible: boolean) => void;
  onBasemapChange?: (basemap: string) => void;
  onZoomPreset?: (preset: string) => void;
}

export default function LayerControl({
  onLayerToggle,
  onBasemapChange,
  onZoomPreset
}: LayerControlProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [activeBasemap, setActiveBasemap] = useState('satellite');
  // Design tokens - light theme
  const theme = {
    bg: '#ffffff',
    panel: '#ffffff',
    border: '#e2e8f0',
    border2: '#f1f5f9',
    accent: '#3b82f6',
    text: '#1e293b',
    text2: '#475569',
    muted: '#64748b',
  };
  const layerGroups = [
    {
      id: 'tsunami',
      title: 'Simulasi Tsunami',
      icon: '🌊',
      layers: [
        { id: 'inundation', label: 'Area Genangan', default: true },
        { id: 'wave_path', label: 'Jalur Gelombang', default: true },
        { id: 'impact_zones', label: 'Zona Dampak', default: true },
      ]
    },
    {
      id: 'network',
      title: 'Jaringan Evakuasi',
      icon: '🛣',
      layers: [
        { id: 'routes', label: 'Rute Evakuasi', default: true },
        { id: 'abm_agents', label: 'Agen Evakuasi', default: true },
        { id: 'network_roads', label: 'Jaringan Jalan', default: false },
      ]
    },
    {
      id: 'admin',
      title: 'Data Administrasi',
      icon: '🏛',
      layers: [
        { id: 'desa', label: 'Batas Desa', default: true },
        { id: 'tes', label: 'Titik Evakuasi', default: true },
        { id: 'roads', label: 'Jalan Utama', default: true },
        { id: 'coastline', label: 'Garis Pantai', default: true },
      ]
    }
  ];

  const basemaps = [
    { id: 'satellite', label: 'Satelit', icon: '🛰' },
    { id: 'osm', label: 'OpenStreetMap', icon: '🗺' },
    { id: 'terrain', label: 'Terrain', icon: '🏔' },
  ];

  const zoomPresets = [
    { id: 'bantul', label: 'Bantul', bounds: [[-8.05, 110.15], [-7.85, 110.45]] },
    { id: 'parangtritis', label: 'Parangtritis', bounds: [[-8.05, 110.25], [-7.95, 110.35]] },
    { id: 'full', label: 'Seluruh Area', bounds: [[-8.2, 110.0], [-7.7, 110.6]] },
  ];

  const handleLayerToggle = (layerId: string, checked: boolean) => {
    onLayerToggle?.(layerId, checked);
  };

  const handleBasemapChange = (basemapId: string) => {
    setActiveBasemap(basemapId);
    onBasemapChange?.(basemapId);
  };

  const handleZoomPreset = (presetId: string) => {
    onZoomPreset?.(presetId);
  };

  return (
    <div className="absolute top-4 right-4 z-[1000]">
      {!isOpen ? (
        // Bubble icon (default state)
        <button
          onClick={() => setIsOpen(true)}
          className="w-12 h-12 rounded-full flex items-center justify-center transition-all hover:shadow-xl"
          style={{
            background: '#3b82f6',
            border: `2px solid #2563eb`,
            color: '#ffffff',
            fontSize: '20px',
            boxShadow: `0 4px 12px rgba(59, 130, 246, 0.3)`
          }}
          title="Layer & Map Controls"
        >
          ⚙️
        </button>
      ) : (
        // Full popup (expanded state)
        <div className="w-80 rounded-lg shadow-2xl overflow-hidden" style={{
          background: theme.panel,
          border: `1px solid ${theme.border}`,
        }}>
          {/* Header */}
          <div className="p-3 flex items-center justify-between" style={{
            background: '#f8fafc',
            borderBottom: `1px solid ${theme.border2}`
          }}>
            <div className="flex items-center gap-2">
              <span className="text-lg">⚙️</span>
              <span className="text-sm font-semibold" style={{ color: theme.text }}>Layer Controls</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="w-6 h-6 flex items-center justify-center rounded transition-colors"
              style={{
                background: '#e2e8f0',
                color: theme.text2
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#cbd5e1'}
              onMouseLeave={(e) => e.currentTarget.style.background = '#e2e8f0'}
            >
              ✕
            </button>
          </div>

          {/* Tabbed Content */}
          <div className="max-h-96 overflow-y-auto">
            {/* Basemap Section */}
            <div style={{ borderBottom: `1px solid ${theme.border2}` }}>
              <div className="p-3" style={{ background: '#f8fafc', borderBottom: `1px solid ${theme.border2}` }}>
                <div className="flex items-center gap-2">
                  <span className="text-lg">🗺</span>
                  <span className="text-sm font-semibold" style={{ color: theme.text }}>Basemap</span>
                </div>
              </div>
              <div className="p-2">
                {basemaps.map((basemap) => (
                  <button
                    key={basemap.id}
                    onClick={() => handleBasemapChange(basemap.id)}
                    className="w-full text-left px-3 py-2.5 rounded-md text-sm transition-colors"
                    style={{
                      background: activeBasemap === basemap.id ? '#dbeafe' : 'transparent',
                      border: `1px solid ${activeBasemap === basemap.id ? '#3b82f6' : 'transparent'}`,
                      color: activeBasemap === basemap.id ? '#1d4ed8' : theme.text2
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span>{basemap.icon}</span>
                      <span>{basemap.label}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Zoom Presets Section */}
            <div style={{ borderBottom: `1px solid ${theme.border2}` }}>
              <div className="p-3" style={{ background: '#f8fafc', borderBottom: `1px solid ${theme.border2}` }}>
                <div className="flex items-center gap-2">
                  <span className="text-lg">🔍</span>
                  <span className="text-sm font-semibold" style={{ color: theme.text }}>Zoom Area</span>
                </div>
              </div>
              <div className="p-2">
                {zoomPresets.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => handleZoomPreset(preset.id)}
                    className="w-full text-left px-3 py-2.5 rounded-md text-sm transition-colors"
                    style={{ color: theme.text2 }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#f1f5f9'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Layer Groups Section */}
            {layerGroups.map((group) => (
              <div key={group.id} style={{ borderBottom: `1px solid ${theme.border2}` }}>
                <button
                  onClick={() => setExpandedGroup(expandedGroup === group.id ? null : group.id)}
                  className="w-full p-3 flex items-center gap-2 transition-colors"
                  style={{ background: '#f8fafc', borderBottom: `1px solid ${theme.border2}` }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#f1f5f9'}
                  onMouseLeave={(e) => e.currentTarget.style.background = '#f8fafc'}
                >
                  <span>{group.icon}</span>
                  <span className="text-sm font-semibold flex-1 text-left" style={{ color: theme.text }}>{group.title}</span>
                  <span className={`text-sm transition-transform ${expandedGroup === group.id ? 'rotate-180' : ''}`}>▼</span>
                </button>
                {expandedGroup === group.id && (
                  <div className="p-2">
                    {group.layers.map((layer) => (
                      <label key={layer.id} className="flex items-center gap-3 p-2.5 rounded-md cursor-pointer transition-colors" style={{ color: theme.text2 }} onMouseEnter={(e) => e.currentTarget.style.background = '#f1f5f9'} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                        <input
                          type="checkbox"
                          defaultChecked={layer.default}
                          onChange={(e) => handleLayerToggle(layer.id, e.target.checked)}
                          style={{ accentColor: theme.accent }}
                          className="w-4 h-4 rounded"
                        />
                        <span className="text-sm" style={{ color: theme.text2 }}>{layer.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}