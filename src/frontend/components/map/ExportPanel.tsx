'use client';

import React, { useState } from 'react';

interface ExportPanelProps {
  onExport?: (type: string, format: string) => void;
  className?: string;
}

export default function ExportPanel({ onExport, className = '' }: ExportPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<string>('');

  // Design tokens - light theme
  const theme = {
    panel: '#ffffff',
    border: '#e2e8f0',
    border2: '#f1f5f9',
    accent: '#3b82f6',
    text: '#1e293b',
    text2: '#475569',
    muted: '#64748b',
  };

  const exportOptions = [
    {
      id: 'tsunami',
      title: 'Hasil Simulasi Tsunami',
      icon: '🌊',
      formats: [
        { id: 'geojson', label: 'GeoJSON', description: 'Format vektor untuk GIS' },
        { id: 'shp', label: 'Shapefile', description: 'Format ESRI Shapefile' },
        { id: 'tiff', label: 'GeoTIFF', description: 'Format raster dengan georeferensi' },
        { id: 'png', label: 'PNG Map', description: 'Gambar peta dengan overlay' },
      ]
    },
    {
      id: 'routing',
      title: 'Analisis Rute Evakuasi',
      icon: '🛣',
      formats: [
        { id: 'geojson', label: 'GeoJSON', description: 'Rute dan titik waypoint' },
        { id: 'csv', label: 'CSV', description: 'Data tabular rute dan waktu' },
        { id: 'kml', label: 'KML', description: 'Format Google Earth' },
        { id: 'png', label: 'PNG Map', description: 'Visualisasi rute' },
      ]
    },
    {
      id: 'abm',
      title: 'Simulasi ABM',
      icon: '👥',
      formats: [
        { id: 'geojson', label: 'GeoJSON', description: 'Posisi agen dan lintasan' },
        { id: 'csv', label: 'CSV', description: 'Data temporal pergerakan agen' },
        { id: 'json', label: 'JSON', description: 'Data lengkap simulasi' },
        { id: 'png', label: 'PNG Animation', description: 'Animasi pergerakan agen' },
      ]
    }
  ];

  const handleExport = (type: string, format: string) => {
    onExport?.(type, format);
    setIsOpen(false);
    setSelectedType('');
  };

  return (
    <div className={`absolute bottom-8 right-4 z-[1000] ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="font-medium transition-colors px-4 py-2 rounded-lg shadow-lg"
        style={{
          background: '#3b82f6',
          border: `1px solid #2563eb`,
          color: '#ffffff'
        }}
      >
        <span className="text-lg">📤</span>
        <span> Export</span>
      </button>

      {isOpen && (
        <div className="absolute bottom-full right-0 mb-2 rounded-lg shadow-xl w-80 max-h-96 overflow-hidden" style={{
          background: theme.panel,
          border: `1px solid ${theme.border}`
        }}>
          <div className="p-4" style={{ borderBottom: `1px solid ${theme.border2}` }}>
            <h3 className="text-lg font-semibold" style={{ color: theme.text }}>Export Data</h3>
            <p className="text-sm mt-1" style={{ color: theme.muted }}>Pilih jenis data dan format export</p>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {exportOptions.map((option) => (
              <div key={option.id} style={{ borderBottom: `1px solid ${theme.border2}` }}>
                <button
                  onClick={() => setSelectedType(selectedType === option.id ? '' : option.id)}
                  className="w-full p-3 text-left flex items-center gap-3 transition-colors"
                  style={{
                    background: 'transparent',
                    color: theme.text2
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#f8fafc'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <span className="text-xl">{option.icon}</span>
                  <div className="flex-1">
                    <div className="font-medium" style={{ color: theme.text }}>{option.title}</div>
                  </div>
                  <span className={`text-sm transition-transform ${selectedType === option.id ? 'rotate-180' : ''}`}>
                    ▼
                  </span>
                </button>

                {selectedType === option.id && (
                  <div className="px-3 pb-3 space-y-2">
                    {option.formats.map((format) => (
                      <button
                        key={format.id}
                        onClick={() => handleExport(option.id, format.id)}
                        className="w-full text-left p-3 rounded-md transition-colors"
                        style={{
                          background: '#eff6ff',
                          border: `1px solid ${theme.border}`,
                          color: theme.text2
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#dbeafe';
                          e.currentTarget.style.borderColor = theme.accent;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#eff6ff';
                          e.currentTarget.style.borderColor = theme.border;
                        }}
                      >
                        <div className="font-medium" style={{ color: theme.text }}>{format.label}</div>
                        <div className="text-sm mt-1" style={{ color: theme.muted }}>{format.description}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="p-3" style={{ borderTop: `1px solid ${theme.border2}`, background: '#f8fafc' }}>
            <button
              onClick={() => setIsOpen(false)}
              className="w-full px-3 py-2 rounded-md transition-colors font-semibold"
              style={{
                background: '#e2e8f0',
                color: theme.text2
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#cbd5e1';
                e.currentTarget.style.color = theme.text;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#e2e8f0';
                e.currentTarget.style.color = theme.text2;
              }}
            >
              Tutup
            </button>
          </div>
        </div>
      )}
    </div>
  );
}