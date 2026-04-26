'use client';

import React, { useState, useEffect } from 'react';
import { getFaultList } from '@/services/api';

interface FaultSelectorProps {
  selectedFault: string | null;
  onSelectFault: (faultId: string) => void;
  className?: string;
}

interface FaultSource {
  id: string;
  name: string;
  magnitude: string;
  category: string;
  recurrence: string;
}

// Mapping fault data ke format UI
function mapFaultData(
  faults: Record<string, {
    label: string;
    mw: number;
    category: string;
    recurrence: string;
    view_lat: number;
    view_lon: number;
    view_zoom: number;
  }>
): { category: string; icon: string; faults: FaultSource[] }[] {
  const grouped: Record<string, FaultSource[]> = {};

  for (const [id, fault] of Object.entries(faults)) {
    const category = fault.category === 'megathrust' ? 'Megathrust' :
                    fault.category === 'fault' ? 'Sesar Aktif' : 'Lainnya';

    if (!grouped[category]) {
      grouped[category] = [];
    }

    grouped[category].push({
      id,
      name: fault.label,
      magnitude: `M${fault.mw}`,
      category: fault.category,
      recurrence: fault.recurrence
    });
  }

  // Convert ke array dengan icon
  const result = [
    {
      category: 'Megathrust',
      icon: '🌊',
      faults: grouped['Megathrust'] || []
    },
    {
      category: 'Sesar Aktif',
      icon: '⚡',
      faults: grouped['Sesar Aktif'] || []
    }
  ];

  // Sort faults dalam setiap category berdasarkan name
  result.forEach(cat => {
    cat.faults.sort((a, b) => a.name.localeCompare(b.name));
  });

  return result;
}

export default function FaultSelector({ selectedFault, onSelectFault, className = '' }: FaultSelectorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [faultSources, setFaultSources] = useState<{ category: string; icon: string; faults: FaultSource[] }[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Design tokens
  const theme = {
    panel: '#0a1628',
    border: 'rgba(56, 189, 248, 0.14)',
    border2: 'rgba(56, 189, 248, 0.08)',
    accent: '#38bdf8',
    text: '#ddeeff',
    text2: '#a8ccee',
    muted: 'rgba(148, 200, 240, 0.55)',
  };

  // Load fault data saat component mount
  useEffect(() => {
    async function loadFaults() {
      try {
        setIsLoading(true);
        setError(null);
        const result = await getFaultList();
        const mapped = mapFaultData(result.faults);
        setFaultSources(mapped);
        console.log(`[FaultSelector] Loaded ${Object.keys(result.faults).length} faults from ${result.source}`);
      } catch (err) {
        console.error('[FaultSelector] Failed to load faults:', err);
        setError('Gagal memuat data fault dari backend');
      } finally {
        setIsLoading(false);
      }
    }

    loadFaults();
  }, []);

  // Get selected fault info
  const selectedFaultInfo = faultSources
    .flatMap(c => c.faults)
    .find(f => f.id === selectedFault);

  return (
    <div className={`rounded-lg shadow-lg overflow-hidden ${className}`} style={{
      background: theme.panel,
      border: `1px solid ${theme.border}`,
      backdropFilter: 'blur(8px)'
    }}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between transition-colors"
        style={{
          borderBottom: `1px solid ${theme.border2}`,
          color: theme.text2
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.06)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">🏔️</span>
          <div className="text-left">
            <div className="font-semibold text-sm" style={{ color: theme.text }}>
              {selectedFaultInfo
                ? selectedFaultInfo.name
                : isLoading
                  ? 'Memuat fault...'
                  : 'Pilih Sumber Gempa'
              }
            </div>
            {selectedFaultInfo && (
              <div className="text-xs mt-1" style={{ color: theme.muted }}>
                {selectedFaultInfo.magnitude} • {selectedFaultInfo.category}
                {selectedFaultInfo.recurrence !== '—' && ` • ${selectedFaultInfo.recurrence}`}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && (
            <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          )}
          <span className={`text-sm transition-transform ${isExpanded ? 'rotate-180' : ''}`}>▼</span>
        </div>
      </button>

      {/* Fault List */}
      {isExpanded && (
        <div className="max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="p-8 text-center" style={{ color: theme.muted }}>
              <div className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-2" />
              <div className="text-sm">Memuat data fault dari shapefile...</div>
            </div>
          ) : faultSources.length === 0 ? (
            <div className="p-8 text-center" style={{ color: theme.muted }}>
              {error ? (
                <>
                  <div className="text-sm" style={{ color: '#f87171' }}>⚠️ {error}</div>
                  <div className="text-xs mt-2 opacity-70">Pastikan backend berjalan dan data fault tersedia</div>
                </>
              ) : (
                <div className="text-sm">Tidak ada fault tersedia</div>
              )}
            </div>
          ) : (
            faultSources.map((category) => (
              <div key={category.category} style={{ borderBottom: `1px solid ${theme.border2}` }}>
                {/* Category Header */}
                <button
                  onClick={() => setSelectedCategory(selectedCategory === category.category ? null : category.category)}
                  className="w-full p-3 flex items-center gap-2 transition-colors"
                  style={{
                    background: 'rgba(56, 189, 248, 0.06)',
                    borderBottom: `1px solid ${theme.border2}`,
                    color: theme.accent
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.12)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.06)'}
                >
                  <span className="text-lg">{category.icon}</span>
                  <span className="text-sm font-semibold flex-1 text-left">
                    {category.category}
                    <span className="ml-2 font-normal text-xs" style={{ color: theme.muted }}>
                      ({category.faults.length})
                    </span>
                  </span>
                  <span className={`text-sm transition-transform ${selectedCategory === category.category ? 'rotate-180' : ''}`}>▼</span>
                </button>

                {/* Fault List */}
                {selectedCategory === category.category && (
                  <div className="p-2 space-y-1">
                    {category.faults.map((fault) => (
                      <button
                        key={fault.id}
                        onClick={() => {
                          onSelectFault(fault.id);
                          setIsExpanded(false);
                        }}
                        className="w-full text-left p-3 rounded-md transition-colors"
                        style={{
                          background: selectedFault === fault.id ? 'rgba(56, 189, 248, 0.14)' : 'transparent',
                          border: `1px solid ${selectedFault === fault.id ? theme.border : 'transparent'}`,
                          color: theme.text2
                        }}
                        onMouseEnter={(e) => {
                          if (selectedFault !== fault.id) {
                            e.currentTarget.style.background = theme.border2;
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (selectedFault !== fault.id) {
                            e.currentTarget.style.background = 'transparent';
                          }
                        }}
                      >
                        <div className="font-medium text-sm" style={{ color: theme.accent }}>
                          {fault.name}
                        </div>
                        <div className="text-xs mt-1 flex gap-4" style={{ color: theme.muted }}>
                          <span>📊 {fault.magnitude}</span>
                          <span>🔄 {fault.recurrence}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}

          {/* Footer */}
          {!isLoading && faultSources.length > 0 && (
            <div className="p-2 text-center" style={{ borderTop: `1px solid ${theme.border2}` }}>
              <div className="text-xs" style={{ color: theme.muted }}>
                ✅ Data dari Backend Shapefile ({faultSources.flatMap(c => c.faults).length} fault)
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
