'use client';

import React, { useState, useEffect } from 'react';
import { getFaultList } from '@/services/api';

interface FaultSelectorProps {
  selectedFault: string | null;
  onSelectFault: (faultId: string) => void;
  className?: string;
  category?: 'fault' | 'megathrust'; // Filter category
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
  }>,
  filterCategory?: string
): FaultSource[] {
  const result: FaultSource[] = [];

  for (const [id, fault] of Object.entries(faults)) {
    // Filter by category jika specified
    if (filterCategory && fault.category !== filterCategory) {
      continue;
    }

    result.push({
      id,
      name: fault.label,
      magnitude: `M${fault.mw}`,
      category: fault.category,
      recurrence: fault.recurrence
    });
  }

  // Sort berdasarkan name
  result.sort((a, b) => a.name.localeCompare(b.name));

  return result;
}

export default function FaultSelector({ selectedFault, onSelectFault, className = '', category = 'fault' }: FaultSelectorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [faultSources, setFaultSources] = useState<FaultSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Icon dan label berdasarkan category
  const config = category === 'fault'
    ? { icon: '⚡', label: 'Sesar Aktif', apiCategory: 'fault' }
    : { icon: '🌊', label: 'Megathrust', apiCategory: 'megathrust' };

  // Load fault data saat component mount
  useEffect(() => {
    async function loadFaults() {
      try {
        setIsLoading(true);
        setError(null);
        const result = await getFaultList();
        const mapped = mapFaultData(result.faults, config.apiCategory);
        setFaultSources(mapped);
        console.log(`[FaultSelector] Loaded ${mapped.length} ${config.label} from ${result.source}`);
      } catch (err) {
        console.error('[FaultSelector] Failed to load faults:', err);
        setError(`Gagal memuat data ${config.label} dari backend`);
      } finally {
        setIsLoading(false);
      }
    }

    loadFaults();
  }, [config.apiCategory, config.label]);

  // Get selected fault info
  const selectedFaultInfo = faultSources.find(f => f.id === selectedFault);

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
        onMouseEnter={(e) => e.currentTarget.style.background = '#f8fafc'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">{config.icon}</span>
          <div className="text-left">
            <div className="font-semibold text-sm" style={{ color: theme.text }}>
              {selectedFaultInfo
                ? selectedFaultInfo.name
                : isLoading
                  ? `Memuat ${config.label}...`
                  : `Pilih ${config.label}`
              }
            </div>
            {selectedFaultInfo && (
              <div className="text-xs mt-1.5" style={{ color: theme.muted }}>
                {selectedFaultInfo.magnitude} • {selectedFaultInfo.category}
                {selectedFaultInfo.recurrence !== '—' && ` • ${selectedFaultInfo.recurrence}`}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && (
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
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
              <div className="text-sm">Memuat data {config.label} dari shapefile...</div>
            </div>
          ) : faultSources.length === 0 ? (
            <div className="p-8 text-center" style={{ color: theme.muted }}>
              {error ? (
                <>
                  <div className="text-sm" style={{ color: '#f87171' }}>⚠️ {error}</div>
                  <div className="text-xs mt-2 opacity-70">Pastikan backend berjalan dan data tersedia</div>
                </>
              ) : (
                <div className="text-sm">Tidak ada {config.label} tersedia</div>
              )}
            </div>
          ) : (
            <div className="p-2 space-y-1.5">
              {faultSources.map((fault) => (
                <button
                  key={fault.id}
                  onClick={() => {
                    onSelectFault(fault.id);
                    setIsExpanded(false);
                  }}
                  className="w-full text-left p-2.5 rounded-lg transition-colors"
                  style={{
                    background: selectedFault === fault.id ? '#dbeafe' : 'transparent',
                    border: `1px solid ${selectedFault === fault.id ? theme.border : 'transparent'}`,
                    color: theme.text2
                  }}
                  onMouseEnter={(e) => {
                    if (selectedFault !== fault.id) {
                      e.currentTarget.style.background = '#f1f5f9';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedFault !== fault.id) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <div className="font-medium text-sm" style={{ color: selectedFault === fault.id ? '#1d4ed8' : theme.accent }}>
                    {fault.name}
                  </div>
                  <div className="text-xs mt-1.5 flex gap-3" style={{ color: theme.muted }}>
                    <span>📊 {fault.magnitude}</span>
                    <span>🔄 {fault.recurrence}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Footer */}
          {!isLoading && faultSources.length > 0 && (
            <div className="p-2 text-center" style={{ borderTop: `1px solid ${theme.border2}` }}>
              <div className="text-xs" style={{ color: theme.muted }}>
                ✅ Data dari Backend Shapefile ({faultSources.length} {config.label})
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
