'use client';

import React, { useEffect, useRef, useState, ComponentType } from 'react';
import dynamic from 'next/dynamic';
import type { DesaData, TESData, SWEResult, RoutingResult, ABMResult } from '@/types';

// Dynamically import Leaflet to prevent SSR issues
let L: any;
let isLeafletAvailable = false;

try {
  if (typeof window !== 'undefined') {
    L = require('leaflet');
    isLeafletAvailable = true;
  }
} catch (e) {
  console.warn('Leaflet not available:', e);
}

interface MapProps {
  onBasemapChange?: (basemap: string) => void;
  desaList?: DesaData[];
  tesList?: TESData[];
  sweResult?: SWEResult | null;
  routingResult?: RoutingResult | null;
  abmResult?: ABMResult | null;
}

const MapComponent: React.FC<MapProps> = ({ onBasemapChange, desaList, tesList, sweResult, routingResult, abmResult }) => {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const basemapLayersRef = useRef<any>({});
  const [currentBasemap, setCurrentBasemap] = useState('osm');
  const [showBasemapDropdown, setShowBasemapDropdown] = useState(false);

  const basemaps = [
    { id: 'osm', name: 'OpenStreetMap (OSM)', icon: '🗺' },
    { id: 'satellite', name: 'Satellite', icon: '🛰' },
    { id: 'terrain', name: 'Terrain', icon: '⛰' },
  ];

  // Zoom preset coordinates (Bantul, Yogyakarta area)
  const zoomPresets = [
    { label: '🏖 Pantai Bantul', id: 'bantul-coast', center: [-7.95, 110.35] as [number, number], zoom: 14 },
    { label: '🏙 Kab. Bantul', id: 'bantul-admin', center: [-7.88, 110.28] as [number, number], zoom: 12 },
    { label: '🗺 Yogyakarta', id: 'yogyakarta', center: [-7.80, 110.37] as [number, number], zoom: 11 },
    { label: '🌊 Laut Selatan Jawa', id: 'java-south', center: [-8.5, 110.5] as [number, number], zoom: 9 },
  ];

  // Initialize Leaflet map and basemap layers together
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current || !isLeafletAvailable || !L) return;

    try {
      // Create basemap layers first
      basemapLayersRef.current = {
        osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 20,
        }),
        satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
          attribution: '© Esri',
          maxZoom: 18,
        }),
        terrain: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
          attribution: '© Esri',
          maxZoom: 18,
        })
      };

      // Create map instance
      const map = L.map(mapContainerRef.current, {
        center: [-7.9, 110.37],
        zoom: 12,
        zoomControl: false,
      });
      mapRef.current = map;

      // Add OSM basemap by default
      basemapLayersRef.current.osm.addTo(map);

      // Add custom zoom control at bottom-left
      L.control.zoom({ position: 'bottomleft' }).addTo(map);

      return () => {
        if (mapRef.current) {
          mapRef.current.remove();
          mapRef.current = null;
        }
      };
    } catch (error) {
      console.error('Error initializing map:', error);
    }
  }, []);

  // Display TES markers when tesList changes
  useEffect(() => {
    if (!mapRef.current || !isLeafletAvailable || !L || !tesList?.length) return;

    try {
      // Create TES layer group if it doesn't exist
      let tesLayerGroup = (mapRef.current as any)._tesLayerGroup;
      if (!tesLayerGroup) {
        tesLayerGroup = L.layerGroup().addTo(mapRef.current);
        (mapRef.current as any)._tesLayerGroup = tesLayerGroup;
      }

      // Clear existing markers
      tesLayerGroup.clearLayers();

      // Add TES markers
      tesList.forEach((tes) => {
        const marker = L.marker([tes.lat, tes.lon], {
          icon: L.icon({
            iconUrl: '/Icon_Titik_Kumpul.png', // Icon path relative to public folder
            iconSize: [24, 24],
            iconAnchor: [12, 24],
            popupAnchor: [0, -24],
          })
        });

        marker.bindPopup(`
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: #38bdf8;">${tes.name}</b><br>
            Kapasitas: ${tes.kapasitas || '—'} orang<br>
            ID: ${tes.id}
          </div>
        `);

        tesLayerGroup.addLayer(marker);
      });

      console.log(`✅ TES markers displayed: ${tesList.length} locations`);
    } catch (error) {
      console.error('Error displaying TES markers:', error);
    }
  }, [tesList, isLeafletAvailable]);

  // Display desa boundaries when desaList changes
  useEffect(() => {
    if (!mapRef.current || !isLeafletAvailable || !L || !desaList?.length) return;

    try {
      // Create desa layer group if it doesn't exist
      let desaLayerGroup = (mapRef.current as any)._desaLayerGroup;
      if (!desaLayerGroup) {
        desaLayerGroup = L.layerGroup().addTo(mapRef.current);
        (mapRef.current as any)._desaLayerGroup = desaLayerGroup;
      }

      // Clear existing boundaries
      desaLayerGroup.clearLayers();

      // Add desa boundaries (simplified for now - just markers)
      desaList.forEach((desa) => {
        const marker = L.circleMarker([desa.lat, desa.lon], {
          color: '#38bdf8',
          fillColor: '#38bdf8',
          fillOpacity: 0.3,
          radius: 6,
          weight: 2,
        });

        marker.bindPopup(`
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: #38bdf8;">${desa.name}</b><br>
            Desa/Kelurahan
          </div>
        `);

        desaLayerGroup.addLayer(marker);
      });

      console.log(`✅ Desa markers displayed: ${desaList.length} locations`);
    } catch (error) {
      console.error('Error displaying desa markers:', error);
    }
  }, [desaList, isLeafletAvailable]);

  // Display TES markers when tesList changes
  useEffect(() => {
    if (!mapRef.current || !isLeafletAvailable || !L || !tesList?.length) return;

    try {
      // Create TES layer group if it doesn't exist
      let tesLayerGroup = (mapRef.current as any)._tesLayerGroup;
      if (!tesLayerGroup) {
        tesLayerGroup = L.layerGroup().addTo(mapRef.current);
        (mapRef.current as any)._tesLayerGroup = tesLayerGroup;
      }

      // Clear existing markers
      tesLayerGroup.clearLayers();

      // Add TES markers
      tesList.forEach((tes) => {
        const marker = L.marker([tes.lat, tes.lon], {
          icon: L.icon({
            iconUrl: '/Icon_Titik_Kumpul.png', // Icon path relative to public folder
            iconSize: [24, 24],
            iconAnchor: [12, 24],
            popupAnchor: [0, -24],
          })
        });

        marker.bindPopup(`
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: #38bdf8;">${tes.name}</b><br>
            Kapasitas: ${tes.kapasitas || '—'} orang<br>
            ID: ${tes.id}
          </div>
        `);

        tesLayerGroup.addLayer(marker);
      });

      console.log(`✅ TES markers displayed: ${tesList.length} locations`);
    } catch (error) {
      console.error('Error displaying TES markers:', error);
    }
  }, [tesList, isLeafletAvailable]);

  // Display desa boundaries when desaList changes
  useEffect(() => {
    if (!mapRef.current || !isLeafletAvailable || !L || !desaList?.length) return;

    try {
      // Create desa layer group if it doesn't exist
      let desaLayerGroup = (mapRef.current as any)._desaLayerGroup;
      if (!desaLayerGroup) {
        desaLayerGroup = L.layerGroup().addTo(mapRef.current);
        (mapRef.current as any)._desaLayerGroup = desaLayerGroup;
      }

      // Clear existing boundaries
      desaLayerGroup.clearLayers();

      // Add desa boundaries (simplified for now - just markers)
      desaList.forEach((desa) => {
        const marker = L.circleMarker([desa.lat, desa.lon], {
          color: '#38bdf8',
          fillColor: '#38bdf8',
          fillOpacity: 0.3,
          radius: 6,
          weight: 2,
        });

        marker.bindPopup(`
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: #38bdf8;">${desa.name}</b><br>
            Desa/Kelurahan
          </div>
        `);

        desaLayerGroup.addLayer(marker);
      });

      console.log(`✅ Desa markers displayed: ${desaList.length} locations`);
    } catch (error) {
      console.error('Error displaying desa markers:', error);
    }
  }, [desaList, isLeafletAvailable]);

  // Display TES markers when tesList changes
  useEffect(() => {
    if (!mapRef.current || !isLeafletAvailable || !L || !tesList?.length) return;

    try {
      // Create TES layer group if it doesn't exist
      let tesLayerGroup = (mapRef.current as any)._tesLayerGroup;
      if (!tesLayerGroup) {
        tesLayerGroup = L.layerGroup().addTo(mapRef.current);
        (mapRef.current as any)._tesLayerGroup = tesLayerGroup;
      }

      // Clear existing markers
      tesLayerGroup.clearLayers();

      // Add TES markers
      tesList.forEach((tes) => {
        const marker = L.marker([tes.lat, tes.lon], {
          icon: L.icon({
            iconUrl: '/Icon_Titik_Kumpul.png', // Icon path relative to public folder
            iconSize: [24, 24],
            iconAnchor: [12, 24],
            popupAnchor: [0, -24],
          })
        });

        marker.bindPopup(`
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: #38bdf8;">${tes.name}</b><br>
            Kapasitas: ${tes.kapasitas || '—'} orang<br>
            ID: ${tes.id}
          </div>
        `);

        tesLayerGroup.addLayer(marker);
      });

      console.log(`✅ TES markers displayed: ${tesList.length} locations`);
    } catch (error) {
      console.error('Error displaying TES markers:', error);
    }
  }, [tesList, isLeafletAvailable]);

  // Display desa boundaries when desaList changes
  useEffect(() => {
    if (!mapRef.current || !isLeafletAvailable || !L || !desaList?.length) return;

    try {
      // Create desa layer group if it doesn't exist
      let desaLayerGroup = (mapRef.current as any)._desaLayerGroup;
      if (!desaLayerGroup) {
        desaLayerGroup = L.layerGroup().addTo(mapRef.current);
        (mapRef.current as any)._desaLayerGroup = desaLayerGroup;
      }

      // Clear existing boundaries
      desaLayerGroup.clearLayers();

      // Add desa boundaries (simplified for now - just markers)
      desaList.forEach((desa) => {
        const marker = L.circleMarker([desa.lat, desa.lon], {
          color: '#38bdf8',
          fillColor: '#38bdf8',
          fillOpacity: 0.3,
          radius: 6,
          weight: 2,
        });

        marker.bindPopup(`
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: #38bdf8;">${desa.name}</b><br>
            Desa/Kelurahan
          </div>
        `);

        desaLayerGroup.addLayer(marker);
      });

      console.log(`✅ Desa markers displayed: ${desaList.length} locations`);
    } catch (error) {
      console.error('Error displaying desa markers:', error);
    }
  }, [desaList, isLeafletAvailable]);

  const handleZoomPreset = (preset: typeof zoomPresets[0]) => {
    if (mapRef.current) {
      mapRef.current.setView(preset.center, preset.zoom, { animate: true, duration: 1 });
    }
  };

  const handleBasemapChange = (basemapId: string) => {
    if (!mapRef.current || !L || !isLeafletAvailable) return;

    try {
      const basemapLayers = basemapLayersRef.current;

      // Remove all basemaps from map
      Object.entries(basemapLayers).forEach(([id, layer]) => {
        if (mapRef.current?.hasLayer(layer as L.Layer)) {
          mapRef.current.removeLayer(layer as L.Layer);
        }
      });

      // Add selected basemap
      const selectedLayer = basemapLayers[basemapId as keyof typeof basemapLayers];
      if (selectedLayer) {
        selectedLayer.addTo(mapRef.current);
        setCurrentBasemap(basemapId);
        setShowBasemapDropdown(false);
        onBasemapChange?.(basemapId);
      }
    } catch (error) {
      console.error('Error changing basemap:', error);
    }
  };

  return (
    <div className="relative flex-1 flex flex-col bg-gray-900 overflow-hidden" id="map-container">
      {/* Leaflet Map Container */}
      <div
        className="flex-1 relative"
        id="map"
        ref={mapContainerRef}
        style={{
          background: 'linear-gradient(135deg, #1a2a3a 0%, #0f1923 100%)',
          zIndex: 1
        }}
      />

      {/* ZOOM PRESETS - Top Left */}
      <div className="absolute top-3 left-3 z-50 flex flex-col gap-1">
        {zoomPresets.map(preset => (
          <button
            key={preset.id}
            className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-all hover:border-cyan-400 hover:text-cyan-400"
            style={{
              background: 'rgba(6, 13, 27, 0.85)',
              backdropFilter: 'blur(8px)',
              borderColor: 'rgba(56, 189, 248, 0.2)',
              color: 'var(--muted)'
            }}
            onClick={() => handleZoomPreset(preset)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* BASEMAP SWITCHER - Bottom Right */}
      <div className="absolute bottom-3 right-3 z-50">
        <div className="relative">
          <button
            onClick={() => setShowBasemapDropdown(!showBasemapDropdown)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border font-bold text-xs transition-all"
            style={{
              background: 'rgba(6, 13, 27, 0.9)',
              backdropFilter: 'blur(10px)',
              borderColor: 'rgba(56, 189, 248, 0.3)',
              color: 'var(--accent)',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            {basemaps.find(b => b.id === currentBasemap)?.icon} {basemaps.find(b => b.id === currentBasemap)?.name}
            <span className="text-xs opacity-60">▲</span>
          </button>

          {showBasemapDropdown && (
            <div className="absolute bottom-full right-0 mb-2 rounded-lg border p-2 grid grid-cols-3 gap-2" style={{
              background: 'rgba(6, 13, 27, 0.96)',
              backdropFilter: 'blur(14px)',
              borderColor: 'var(--border)',
              boxShadow: 'var(--shadow)',
              width: '240px'
            }}>
              {basemaps.map(basemap => (
                <button
                  key={basemap.id}
                  onClick={() => handleBasemapChange(basemap.id)}
                  className="p-3 rounded-md border-2 text-center transition-all hover:border-cyan-400"
                  style={{
                    borderColor: currentBasemap === basemap.id ? 'var(--accent)' : 'rgba(56, 189, 248, 0.15)',
                    background: currentBasemap === basemap.id ? 'rgba(56, 189, 248, 0.15)' : 'rgba(0, 15, 40, 0.5)'
                  }}
                >
                  <div className="text-2xl mb-1">{basemap.icon}</div>
                  <div className="text-xs font-semibold" style={{
                    color: currentBasemap === basemap.id ? 'var(--accent)' : 'var(--muted)'
                  }}>
                    {basemap.name.split('(')[0].trim()}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* EPISENTRUM HINT - Bottom Center */}
      <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-40 rounded-lg border px-4 py-2 text-center text-xs max-w-sm" style={{
        background: 'rgba(6, 13, 27, 0.9)',
        backdropFilter: 'blur(10px)',
        borderColor: 'rgba(56, 189, 248, 0.35)',
        color: 'rgba(220, 240, 255, 0.92)',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6)',
        lineHeight: '1.5'
      }}>
        <div>
          🖱 Klik di <b style={{ color: 'var(--accent)' }}>LAUT SELATAN JAWA</b> untuk menetapkan episentrum gempa
        </div>
        <div style={{
          color: 'rgba(200, 232, 255, 0.5)',
          fontSize: '10px',
          marginTop: '4px'
        }}>
          Zona Megathrust: sekitar 8°–10°S | Patahan Aktif: pilih tab "Patahan"
        </div>
      </div>
    </div>
  );
};

export default MapComponent;
