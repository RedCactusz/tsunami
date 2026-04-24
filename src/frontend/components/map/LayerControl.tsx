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
  // Design tokens matching old index.html
  const theme = {
    bg: '#060d1b',
    panel: '#0a1628',
    border: 'rgba(56, 189, 248, 0.14)',
    border2: 'rgba(56, 189, 248, 0.08)',
    accent: '#38bdf8',
    text: '#ddeeff',
    text2: '#a8ccee',
    muted: 'rgba(148, 200, 240, 0.55)',
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
            background: 'linear-gradient(135deg, rgb(55, 112, 137), rgb(0, 39, 55))',
            border: `2px solid ${theme.accent}`,
            color: theme.accent,
            fontSize: '20px',
            boxShadow: `0 0 12px rgba(56, 189, 248, 0.3)`
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
          backdropFilter: 'blur(8px)'
        }}>
          {/* Header */}
          <div className="p-3 flex items-center justify-between" style={{
            background: 'rgba(56, 189, 248, 0.06)',
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
                background: 'rgba(56, 189, 248, 0.08)',
                color: theme.text2
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.14)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.08)'}
            >
              ✕
            </button>
          </div>

          {/* Tabbed Content */}
          <div className="max-h-96 overflow-y-auto">
            {/* Basemap Section */}
            <div style={{ borderBottom: `1px solid ${theme.border2}` }}>
              <div className="p-3" style={{ background: 'rgba(56, 189, 248, 0.06)', borderBottom: `1px solid ${theme.border2}` }}>
                <div className="flex items-center gap-2">
                  <span className="text-lg">🗺</span>
                  <span className="text-sm font-semibold" style={{ color: theme.accent }}>Basemap</span>
                </div>
              </div>
              <div className="p-2">
                {basemaps.map((basemap) => (
                  <button
                    key={basemap.id}
                    onClick={() => handleBasemapChange(basemap.id)}
                    className="w-full text-left px-3 py-2 rounded-md text-sm transition-colors"
                    style={{
                      background: activeBasemap === basemap.id ? 'rgba(56, 189, 248, 0.14)' : 'transparent',
                      border: `1px solid ${activeBasemap === basemap.id ? 'rgba(56, 189, 248, 0.4)' : 'transparent'}`,
                      color: activeBasemap === basemap.id ? theme.accent : theme.text2
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
              <div className="p-3" style={{ background: 'rgba(56, 189, 248, 0.06)', borderBottom: `1px solid ${theme.border2}` }}>
                <div className="flex items-center gap-2">
                  <span className="text-lg">🔍</span>
                  <span className="text-sm font-semibold" style={{ color: theme.accent }}>Zoom Area</span>
                </div>
              </div>
              <div className="p-2">
                {zoomPresets.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => handleZoomPreset(preset.id)}
                    className="w-full text-left px-3 py-2 rounded-md text-sm transition-colors"
                    style={{ color: theme.text2 }}
                    onMouseEnter={(e) => e.currentTarget.style.background = theme.border2}
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
                  style={{ background: 'rgba(56, 189, 248, 0.06)', borderBottom: `1px solid ${theme.border2}` }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.12)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.06)'}
                >
                  <span>{group.icon}</span>
                  <span className="text-sm font-semibold flex-1 text-left" style={{ color: theme.accent }}>{group.title}</span>
                  <span className={`text-sm transition-transform ${expandedGroup === group.id ? 'rotate-180' : ''}`}>▼</span>
                </button>
                {expandedGroup === group.id && (
                  <div className="p-2">
                    {group.layers.map((layer) => (
                      <label key={layer.id} className="flex items-center gap-3 p-2 rounded-md cursor-pointer transition-colors" style={{ color: theme.text2 }} onMouseEnter={(e) => e.currentTarget.style.background = theme.border2} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
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