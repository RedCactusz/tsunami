'use client';

import React, { useState } from 'react';

interface FaultSelectorProps {
  selectedFault: string | null;
  onSelectFault: (faultId: string) => void;
  className?: string;
}

const faultSources = [
  {
    category: 'Megathrust',
    icon: '🌊',
    faults: [
      { id: 'mega-1', name: 'M1 - Megathrust Barat Sumatra', magnitude: '8.5+ Mw', depth: '20-30 km', length: '500+ km' },
      { id: 'mega-7', name: 'M7 - Megathrust Sunda', magnitude: '8.5+ Mw', depth: '15-25 km', length: '400+ km' },
      { id: 'mega-8', name: 'M8 - Megathrust Jawa', magnitude: '8.0+ Mw', depth: '10-20 km', length: '300+ km' },
    ]
  },
  {
    category: 'Baribis Kendeng',
    icon: '🏔',
    faults: [
      { id: 'baribis-1', name: 'Baribis Kendeng F - Cirebon-1', magnitude: '6.5 Mw', depth: '8-12 km', length: '80 km' },
      { id: 'baribis-2', name: 'Baribis Kendeng F - Cirebon-2', magnitude: '6.6 Mw', depth: '8-12 km', length: '90 km' },
      { id: 'baribis-3', name: 'Baribis Kendeng F - Semarang', magnitude: '6.4 Mw', depth: '6-10 km', length: '70 km' },
    ]
  },
  {
    category: 'Strike-Slip Faults',
    icon: '⚡',
    faults: [
      { id: 'ciremai', name: 'Ciremai (Strike-slip)', magnitude: '6.6 Mw', depth: '5-15 km', length: '60 km' },
      { id: 'cimandiri', name: 'Cimandiri Fault', magnitude: '6.2 Mw', depth: '3-8 km', length: '45 km' },
      { id: 'lusi', name: 'Lusi Fault Zone', magnitude: '6.0 Mw', depth: '2-6 km', length: '35 km' },
    ]
  },
  {
    category: 'Subduction Zone',
    icon: '🔥',
    faults: [
      { id: 'sub-1', name: 'Subduction Jawa - Bali', magnitude: '7.5+ Mw', depth: '25-40 km', length: '200+ km' },
      { id: 'sub-2', name: 'Subduction Bali - Nusa Tenggara', magnitude: '7.0+ Mw', depth: '20-35 km', length: '150+ km' },
    ]
  }
];

export default function FaultSelector({ selectedFault, onSelectFault, className = '' }: FaultSelectorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Design tokens matching old index.html
  const theme = {
    panel: '#0a1628',
    border: 'rgba(56, 189, 248, 0.14)',
    border2: 'rgba(56, 189, 248, 0.08)',
    accent: '#38bdf8',
    text: '#ddeeff',
    text2: '#a8ccee',
    muted: 'rgba(148, 200, 240, 0.55)',
  };

  return (
    <div className={`rounded-lg shadow-lg overflow-hidden ${className}`} style={{
      background: theme.panel,
      border: `1px solid ${theme.border}`,
      backdropFilter: 'blur(8px)'
    }}>
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
              {selectedFault ? faultSources.flatMap(c => c.faults).find(f => f.id === selectedFault)?.name : 'Pilih Sumber Gempa'}
            </div>
            {selectedFault && (
              <div className="text-xs mt-1" style={{ color: theme.muted }}>
                {(() => {
                  const fault = faultSources.flatMap(c => c.faults).find(f => f.id === selectedFault);
                  return fault ? `${fault.magnitude} • ${fault.depth} • ${fault.length}` : '';
                })()}
              </div>
            )}
          </div>
        </div>
        <span className={`text-sm transition-transform ${isExpanded ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {isExpanded && (
        <div className="max-h-96 overflow-y-auto">
          {faultSources.map((category) => (
            <div key={category.category} style={{ borderBottom: `1px solid ${theme.border2}` }}>
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
                <span className="text-sm font-semibold flex-1 text-left">{category.category}</span>
                <span className={`text-sm transition-transform ${selectedCategory === category.category ? 'rotate-180' : ''}`}>▼</span>
              </button>

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
                      <div className="font-medium text-sm" style={{ color: theme.accent }}>{fault.name}</div>
                      <div className="text-xs mt-1 flex gap-4" style={{ color: theme.muted }}>
                        <span>📊 {fault.magnitude}</span>
                        <span>📏 {fault.depth}</span>
                        <span>📐 {fault.length}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}