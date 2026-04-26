'use client';

import { useEffect, useRef } from 'react';
import type { ABMFrame } from '@/types';

// Only import Leaflet on client side
let L: any;
if (typeof window !== 'undefined') {
  try {
    L = require('leaflet');
  } catch (error) {
    console.warn('Leaflet import failed:', error);
  }
}

// Custom icons for different agent statuses
const createAgentIcon = (status: 'evacuating' | 'safe' | 'trapped', transport: 'foot' | 'motor' | 'car' = 'foot') => {
  const colors = {
    evacuating: '#f59e0b', // orange
    safe: '#10b981',       // green
    trapped: '#ef4444',    // red
  };

  const sizes = {
    foot: 8,
    motor: 10,
    car: 12,
  };

  const color = colors[status];
  const size = sizes[transport];

  // Create SVG icon
  const svgHtml = `
    <svg width="${size * 2}" height="${size * 2}" viewBox="0 0 ${size * 2} ${size * 2}">
      <circle
        cx="${size}"
        cy="${size}"
        r="${size}"
        fill="${color}"
        stroke="#fff"
        stroke-width="2"
        opacity="${status === 'trapped' ? 0.7 : 0.9}"
      />
      ${status === 'safe' ? `
        <path
          d="M ${size - 3} ${size} L ${size} ${size + 3} L ${size + 3} ${size - 3}"
          stroke="#fff"
          stroke-width="2"
          fill="none"
        />
      ` : ''}
      ${status === 'trapped' ? `
        <path
          d="M ${size - 3} ${size - 3} L ${size + 3} ${size + 3} M ${size + 3} ${size - 3} L ${size - 3} ${size + 3}"
          stroke="#fff"
          stroke-width="2"
          fill="none"
        />
      ` : ''}
    </svg>
  `;

  return L.divIcon({
    html: svgHtml,
    className: 'abm-agent-marker',
    iconSize: [size * 2, size * 2],
    iconAnchor: [size, size],
    popupAnchor: [0, -size - 5],
  });
};

interface ABMAgentsLayerProps {
  map: L.Map;
  frame: ABMFrame | null;
  visible: boolean;
  transportMode?: 'foot' | 'motor' | 'car';
  onAgentClick?: (agentId: string, agent: any) => void;
}

export default function ABMAgentsLayer({
  map,
  frame,
  visible,
  transportMode = 'foot',
  onAgentClick,
}: ABMAgentsLayerProps) {
  const agentsLayerRef = useRef<L.LayerGroup | null>(null);
  const previousFrameRef = useRef<ABMFrame | null>(null);

  // Initialize layer group
  useEffect(() => {
    if (!map || !L) return;

    const layerGroup = L.layerGroup().addTo(map);
    agentsLayerRef.current = layerGroup;

    return () => {
      layerGroup.remove();
      agentsLayerRef.current = null;
    };
  }, [map]);

  // Update agents when frame changes
  useEffect(() => {
    if (!agentsLayerRef.current || !visible || !L) return;

    const layerGroup = agentsLayerRef.current;

    // Clear previous markers
    layerGroup.clearLayers();

    if (!frame || frame.agents.length === 0) return;

    // Check if we should animate (smooth transition) or just show new positions
    const shouldAnimate = previousFrameRef.current !== null &&
                        previousFrameRef.current !== frame;

    // Add markers for each agent
    frame.agents.forEach((agent) => {
      const icon = createAgentIcon(agent.status, transportMode);

      const marker = L.marker([agent.lat, agent.lon], {
        icon,
        opacity: agent.status === 'trapped' ? 0.7 : 1,
      });

      // Tooltip with agent info
      const tooltipContent = `
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 11px; min-width: 150px;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <div style="width: 8px; height: 8px; border-radius: 50%; background: ${
              agent.status === 'safe' ? '#10b981' :
              agent.status === 'trapped' ? '#ef4444' : '#f59e0b'
            };"></div>
            <strong style="font-size: 12px;">Agent ${agent.id.split('_').slice(-2).join('_')}</strong>
          </div>
          <hr style="margin: 4px 0; border: none; border-top: 1px solid #ddd;">
          <div style="display: grid; grid-template-columns: 80px 1fr; gap: 2px;">
            <span style="color: #666;">Status:</span>
            <strong style="color: ${
              agent.status === 'safe' ? '#10b981' :
              agent.status === 'trapped' ? '#ef4444' : '#f59e0b'
            }; text-transform: capitalize;">${agent.status}</strong>
            <span style="color: #666;">Position:</span>
            <span>${agent.lat.toFixed(5)}, ${agent.lon.toFixed(5)}</span>
          </div>
        </div>
      `;

      marker.bindTooltip(tooltipContent, {
        permanent: false,
        direction: 'top',
        offset: [0, -10],
        opacity: 0.9,
      });

      // Click handler
      if (onAgentClick) {
        marker.on('click', () => {
          onAgentClick(agent.id, agent);
        });
      }

      layerGroup.addLayer(marker);
    });

    // Store current frame for next comparison
    previousFrameRef.current = frame;

    console.log(`[ABMAgentsLayer] Rendered ${frame.agents.length} agents for frame at ${frame.time_min.toFixed(1)} min`);
  }, [frame, visible, transportMode, onAgentClick]);

  // Toggle visibility
  useEffect(() => {
    if (!agentsLayerRef.current || !map) return;

    if (visible) {
      agentsLayerRef.current.addTo(map);
    } else {
      map.removeLayer(agentsLayerRef.current);
    }
  }, [visible, map]);

  return null; // This component doesn't render anything directly
}
