'use client';

import React, { useEffect, useRef, useState } from 'react';
import type { DesaData, TESData, SWEResult, RoutingResult, ABMResult } from '@/types';

let L: any;
const isBrowser = typeof window !== 'undefined';
if (isBrowser) {
  try {
    L = require('leaflet');
  } catch (error) {
    console.warn('Leaflet import failed:', error);
  }
}

interface MapProps {
  onBasemapChange?: (basemap: string) => void;
  desaList?: DesaData[];
  tesList?: TESData[];
  sweResult?: SWEResult | null;
  routingResult?: RoutingResult | null;
  abmResult?: ABMResult | null;
  customEpicenter?: { lat: number; lon: number } | null;
  isPickingEpicenter?: boolean;
  onEpicenterSelect?: (coords: { lat: number; lon: number }) => void;
}

const defaultCenter: [number, number] = [-7.9, 110.37];

export default function MapComponent({
  onBasemapChange,
  desaList = [],
  tesList = [],
  sweResult,
  routingResult,
  abmResult,
  customEpicenter,
  isPickingEpicenter = false,
  onEpicenterSelect,
}: MapProps) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [activeBasemap, setActiveBasemap] = useState<'osm' | 'satellite' | 'terrain'>('osm');
  const [showTES, setShowTES] = useState(true);
  const [showDesa, setShowDesa] = useState(true);
  const [showEpicenter, setShowEpicenter] = useState(true);

  const mapRef = useRef<any>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const basemapLayersRef = useRef<Record<string, any>>({});
  const currentBasemapRef = useRef<any>(null);
  const epicenterMarkerRef = useRef<any>(null);
  const tesGroupRef = useRef<any>(null);
  const desaGroupRef = useRef<any>(null);

  useEffect(() => {
    if (!mapContainerRef.current || !isBrowser || mapRef.current || !L) return;

    const basemapLayers = {
      osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 20,
      }),
      satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: '© Esri',
        maxZoom: 18,
      }),
      terrain: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
        attribution: '© Esri',
        maxZoom: 18,
      }),
    };

    basemapLayersRef.current = basemapLayers;

    const map = L.map(mapContainerRef.current, {
      center: defaultCenter,
      zoom: 12,
      zoomControl: false,
    });

    basemapLayers.osm.addTo(map);
    currentBasemapRef.current = basemapLayers.osm;

    L.control.zoom({ position: 'bottomleft' }).addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      currentBasemapRef.current = null;
      epicenterMarkerRef.current = null;
      tesGroupRef.current = null;
      desaGroupRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;
    const nextLayer = basemapLayersRef.current[activeBasemap];
    if (!nextLayer || currentBasemapRef.current === nextLayer) return;

    map.removeLayer(currentBasemapRef.current);
    nextLayer.addTo(map);
    currentBasemapRef.current = nextLayer;
    onBasemapChange?.(activeBasemap);
  }, [activeBasemap, onBasemapChange]);

  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    const tooltipIcon = L.divIcon({
      className: '',
      html: `<div style="width:28px;height:28px;background:radial-gradient(circle,#f87171,#dc2626);border:2.5px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 2px 8px rgba(0,0,0,.5)"></div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
    });

    if (customEpicenter && showEpicenter) {
      const latlng = [customEpicenter.lat, customEpicenter.lon];

      if (!epicenterMarkerRef.current) {
        const marker = L.marker(latlng, {
          icon: tooltipIcon,
          draggable: true,
          zIndexOffset: 500,
        }).addTo(map);

        marker.bindTooltip('📍 Titik Episentrum (drag untuk ubah)', { permanent: false });
        marker.on('dragend', (event: any) => {
          const position = event.target.getLatLng();
          onEpicenterSelect?.({ lat: position.lat, lon: position.lng });
        });

        epicenterMarkerRef.current = marker;
      } else {
        epicenterMarkerRef.current.setLatLng(latlng);
      }
    } else if (epicenterMarkerRef.current) {
      map.removeLayer(epicenterMarkerRef.current);
      epicenterMarkerRef.current = null;
    }
  }, [customEpicenter, showEpicenter, onEpicenterSelect]);

  useEffect(() => {
    if (!mapRef.current) return;
    const container = mapRef.current.getContainer();
    container.style.cursor = isPickingEpicenter ? 'crosshair' : '';
  }, [isPickingEpicenter]);

  useEffect(() => {
    if (!mapRef.current || !L || !onEpicenterSelect) return;
    const map = mapRef.current;

    const handleClick = (event: any) => {
      if (!isPickingEpicenter) return;
      const latlng = event.latlng;
      if (!latlng) return;
      onEpicenterSelect({ lat: latlng.lat, lon: latlng.lng });
    };

    map.on('click', handleClick);
    return () => {
      map.off('click', handleClick);
    };
  }, [isPickingEpicenter, onEpicenterSelect]);

  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    if (!tesGroupRef.current) {
      tesGroupRef.current = L.layerGroup().addTo(map);
    }

    tesGroupRef.current.clearLayers();
    if (showTES) {
      tesList.forEach((tes) => {
        const marker = L.marker([tes.lat, tes.lon], {
          icon: L.icon({
            iconUrl: '/Icon_Titik_Kumpul.png',
            iconSize: [24, 24],
            iconAnchor: [12, 24],
            popupAnchor: [0, -24],
          }),
        });
        marker.bindPopup(`
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: #38bdf8;">${tes.name}</b><br>
            Kapasitas: ${tes.kapasitas || '—'} orang<br>
            ID: ${tes.id}
          </div>
        `);
        tesGroupRef.current.addLayer(marker);
      });
    }
  }, [tesList, showTES]);

  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    if (!desaGroupRef.current) {
      desaGroupRef.current = L.layerGroup().addTo(map);
    }

    desaGroupRef.current.clearLayers();
    if (showDesa) {
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
        desaGroupRef.current.addLayer(marker);
      });
    }
  }, [desaList, showDesa]);

  return (
    <div className="flex-1 relative overflow-hidden">
      <div ref={mapContainerRef} className="absolute inset-0" />
      <div className="absolute top-4 left-4" style={{ zIndex: 1000 }}>
        {panelOpen ? (
          <div className="rounded-3xl border border-white/15 bg-slate-950/90 shadow-2xl backdrop-blur-lg text-sm text-slate-100" style={{ width: 292 }}>
            <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-white/10">
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-cyan-300">Kontrol Peta</div>
                <div className="text-[13px] text-slate-300">Basemap & Layer</div>
              </div>
              <button
                type="button"
                onClick={() => setPanelOpen(false)}
                className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 hover:bg-white/10"
              >
                ×
              </button>
            </div>

            <div className="space-y-4 px-4 py-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 mb-2">Basemap</div>
                <div className="grid grid-cols-3 gap-2">
                  {(['osm', 'satellite', 'terrain'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setActiveBasemap(mode)}
                      className="rounded-2xl border px-2.5 py-2 text-[12px] font-semibold transition-all"
                      style={{
                        background: activeBasemap === mode ? 'rgba(56, 189, 248, 0.18)' : 'rgba(15, 23, 42, 0.9)',
                        borderColor: activeBasemap === mode ? '#38bdf8' : 'rgba(148, 163, 184, 0.16)',
                        color: activeBasemap === mode ? '#cffafe' : '#cbd5e1',
                      }}
                    >
                      {mode === 'osm' ? 'OSM' : mode === 'satellite' ? 'Satellite' : 'Terrain'}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 mb-2">Layer</div>
                <div className="grid gap-2">
                  <button
                    type="button"
                    onClick={() => setShowTES((prev) => !prev)}
                    className="flex items-center justify-between rounded-2xl border px-3 py-2 text-left text-sm font-semibold"
                    style={{
                      background: showTES ? 'rgba(16, 185, 129, 0.12)' : 'rgba(15, 23, 42, 0.9)',
                      borderColor: showTES ? '#34d399' : 'rgba(148, 163, 184, 0.16)',
                      color: showTES ? '#a7f3d0' : '#cbd5e1',
                    }}
                  >
                    <span>TES</span>
                    <span>{showTES ? 'ON' : 'OFF'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDesa((prev) => !prev)}
                    className="flex items-center justify-between rounded-2xl border px-3 py-2 text-left text-sm font-semibold"
                    style={{
                      background: showDesa ? 'rgba(56, 189, 248, 0.12)' : 'rgba(15, 23, 42, 0.9)',
                      borderColor: showDesa ? '#38bdf8' : 'rgba(148, 163, 184, 0.16)',
                      color: showDesa ? '#bae6fd' : '#cbd5e1',
                    }}
                  >
                    <span>Desa</span>
                    <span>{showDesa ? 'ON' : 'OFF'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowEpicenter((prev) => !prev)}
                    className="flex items-center justify-between rounded-2xl border px-3 py-2 text-left text-sm font-semibold"
                    style={{
                      background: showEpicenter ? 'rgba(248, 113, 113, 0.12)' : 'rgba(15, 23, 42, 0.9)',
                      borderColor: showEpicenter ? '#fca5a5' : 'rgba(148, 163, 184, 0.16)',
                      color: showEpicenter ? '#fed7d7' : '#cbd5e1',
                    }}
                  >
                    <span>Episentrum</span>
                    <span>{showEpicenter ? 'ON' : 'OFF'}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setPanelOpen(true)}
            className="flex h-14 w-14 items-center justify-center rounded-full border border-white/15 bg-slate-950/90 text-slate-100 shadow-2xl backdrop-blur-lg"
            style={{
              minWidth: 56,
              zIndex: 1001,
            }}
            title="Buka kontrol peta"
          >
            <span className="text-xl">☰</span>
          </button>
        )}
      </div>
    </div>
  );
}
