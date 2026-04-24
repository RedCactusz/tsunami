'use client';

import React, { useState, useEffect } from 'react';

interface ServerStatusProps {
  className?: string;
}

interface ServerStatus {
  backend: 'online' | 'offline' | 'error';
  simulation: 'ready' | 'running' | 'error';
  lastUpdate: string;
}

export default function ServerStatus({ className = '' }: ServerStatusProps) {
  const [status, setStatus] = useState<ServerStatus>({
    backend: 'offline',
    simulation: 'ready',
    lastUpdate: new Date().toLocaleTimeString()
  });
  const [isExpanded, setIsExpanded] = useState(false);

  // Design tokens matching old index.html
  const theme = {
    panel: '#0a1628',
    border: 'rgba(56, 189, 248, 0.14)',
    border2: 'rgba(56, 189, 248, 0.08)',
    accent: '#38bdf8',
    text: '#ddeeff',
    text2: '#a8ccee',
    muted: 'rgba(148, 200, 240, 0.55)',
    ok: '#34d399',
    warn: '#fbbf24',
    danger: '#f87171',
  };

  const checkServerStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/status');
      if (response.ok) {
        const data = await response.json();
        setStatus({
          backend: 'online',
          simulation: data.simulation_status || 'ready',
          lastUpdate: new Date().toLocaleTimeString()
        });
      } else {
        setStatus(prev => ({
          ...prev,
          backend: 'error',
          lastUpdate: new Date().toLocaleTimeString()
        }));
      }
    } catch (error) {
      setStatus(prev => ({
        ...prev,
        backend: 'offline',
        lastUpdate: new Date().toLocaleTimeString()
      }));
    }
  };

  useEffect(() => {
    checkServerStatus();
    const interval = setInterval(checkServerStatus, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
      case 'ready':
        return 'bg-green-500';
      case 'running':
        return 'bg-yellow-500';
      case 'offline':
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'online':
        return 'Online';
      case 'offline':
        return 'Offline';
      case 'error':
        return 'Error';
      case 'ready':
        return 'Ready';
      case 'running':
        return 'Running';
      default:
        return status;
    }
  };

  return (
    <div className={`absolute top-4 left-4 z-[1000] ${className}`}>
      <div className="rounded-lg shadow-lg overflow-hidden" style={{
        background: theme.panel,
        border: `1px solid ${theme.border}`,
        backdropFilter: 'blur(8px)'
      }}>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full p-3 flex items-center justify-between hover:bg-opacity-50 transition-colors"
          style={{
            background: 'rgba(56, 189, 248, 0.06)',
            color: theme.text2
          }}
        >
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${
              status.backend === 'online' ? 'bg-green-500' :
              status.backend === 'error' ? 'bg-yellow-500' :
              'bg-red-500'
            }`}></div>
            <span className="text-sm font-semibold">Server Status</span>
          </div>
          <span className={`text-sm transition-transform ${isExpanded ? 'rotate-180' : ''}`}>▼</span>
        </button>

        {isExpanded && (
          <div className="p-3" style={{ borderTop: `1px solid ${theme.border2}` }}>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: theme.muted }}>Backend:</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    status.backend === 'online' ? 'bg-green-500' :
                    status.backend === 'error' ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}></div>
                  <span className="text-sm font-medium" style={{ color: theme.text2 }}>
                    {status.backend === 'online' ? 'Online' : status.backend === 'error' ? 'Error' : 'Offline'}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: theme.muted }}>Simulation:</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    status.simulation === 'ready' ? 'bg-green-500' :
                    status.simulation === 'running' ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}></div>
                  <span className="text-sm font-medium" style={{ color: theme.text2 }}>
                    {status.simulation === 'running' ? 'Running' : status.simulation === 'ready' ? 'Ready' : 'Error'}
                  </span>
                </div>
              </div>

              <div style={{ paddingTop: '8px', borderTop: `1px solid ${theme.border2}` }}>
                <div className="text-xs" style={{ color: theme.muted }}>
                  Last update: {status.lastUpdate}
                </div>
              </div>

              <button
                onClick={checkServerStatus}
                className="w-full px-3 py-1 text-sm rounded-md transition-colors"
                style={{
                  background: 'rgba(56, 189, 248, 0.12)',
                  color: theme.accent,
                  border: `1px solid ${theme.border}`
                }}
              >
                Refresh Status
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}