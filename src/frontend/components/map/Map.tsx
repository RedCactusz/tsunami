'use client';

import type { ABMResult, DesaData, RoutingResult, SWEResult, TESData } from '@/types';
import { useEffect, useRef, useState } from 'react';
import { useABMAnimation } from '@/hooks/useABMAnimation';
import ExportPanel from './ExportPanel';
import LayerControl from './LayerControl';
import ServerStatus from './ServerStatus';
import ABMAgentsLayer from './ABMAgentsLayer';
import ABMAnimationControls from '../ui/ABMAnimationControls';

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
  onLayerToggle?: (layerId: string, isVisible: boolean) => void;
  onZoomPreset?: (preset: string) => void;
  onExport?: (type: string, format: string) => void;
  desaList?: DesaData[];
  tesList?: TESData[];
  sweResult?: SWEResult | null;
  routingResult?: RoutingResult | null;
  abmResult?: ABMResult | null;
  customEpicenter?: { lat: number; lon: number } | null;
  isPickingEpicenter?: boolean;
  onEpicenterSelect?: (coords: { lat: number; lon: number }) => void;
  customOrigin?: { lat: number; lon: number } | null;
  isPickingOrigin?: boolean;
  onOriginSelect?: (coords: { lat: number; lon: number }) => void;
  selectedFault?: string | null;  // ID of selected fault/megathrust
  faultData?: Record<string, {  // Fault metadata with view coordinates
    label: string;
    mw: number;
    category: string;
    recurrence: string;
    view_lat: number;
    view_lon: number;
    view_zoom: number;
  }>;
}

const defaultCenter: [number, number] = [-7.95, 110.35];

export default function MapComponent({
  onBasemapChange,
  onLayerToggle,
  onZoomPreset,
  onExport,
  desaList = [],
  tesList = [],
  sweResult,
  routingResult,
  abmResult,
  customEpicenter,
  isPickingEpicenter = false,
  onEpicenterSelect,
  customOrigin,
  isPickingOrigin = false,
  onOriginSelect,
  selectedFault,
  faultData,
}: MapProps) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [activeBasemap, setActiveBasemap] = useState<'osm' | 'satellite' | 'terrain'>('satellite');
  const [layerVisibility, setLayerVisibility] = useState({
    desa: false,  // Hidden by default - can be toggled via layer control
    tes: true,
    roads: true,
    coastline: true,
    inundation: true,
    wave_path: true,
    impact_zones: true,
    routes: true,
    abm_agents: true,
    network_roads: false,
    pemukiman: false,  // Hidden by default - settlements layer
  });

  const handleLayerToggle = (layerId: string, isVisible: boolean) => {
    setLayerVisibility(prev => ({
      ...prev,
      [layerId]: isVisible
    }));
    onLayerToggle?.(layerId, isVisible);
  };

  const handleBasemapChange = (basemap: string) => {
    setActiveBasemap(basemap as 'osm' | 'satellite' | 'terrain');
    onBasemapChange?.(basemap);
  };

  type ZoomPresetKey = 'bantul' | 'parangtritis' | 'full';

  const handleZoomPreset = (preset: string) => {
    if (!mapRef.current) return;

    const zoomBounds: Record<ZoomPresetKey, [number, number][]> = {
      bantul: [[-8.05, 110.15], [-7.85, 110.45]],
      parangtritis: [[-8.05, 110.25], [-7.95, 110.35]],
      full: [[-8.2, 110.0], [-7.7, 110.6]],
    };

    if (preset in zoomBounds) {
      const key = preset as ZoomPresetKey;
      mapRef.current.fitBounds(zoomBounds[key]);
    }

    onZoomPreset?.(preset);
  };

  const handleExport = (type: string, format: string) => {
    onExport?.(type, format);
  };

  const mapRef = useRef<any>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const basemapLayersRef = useRef<Record<string, any>>({});
  const currentBasemapRef = useRef<any>(null);
  const epicenterMarkerRef = useRef<any>(null);
  const originMarkerRef = useRef<any>(null);
  const tesGroupRef = useRef<any>(null);
  const desaGroupRef = useRef<any>(null);
  const pemukimanGroupRef = useRef<any>(null);
  const routesGroupRef = useRef<any>(null);
  const inundationGroupRef = useRef<any>(null);
  const faultHighlightRef = useRef<any>(null);  // For fault selection highlight

  // ABM Animation state
  const [showABMControls, setShowABMControls] = useState(false);

  // Initialize ABM animation hook
  const abmAnimation = useABMAnimation({
    frames: abmResult?.frames || [],
    autoPlay: false,
    initialSpeed: 2,
    onFrameChange: (frame, index) => {
      console.log(`[Map] ABM frame ${index}: ${frame.agents.length} agents at ${frame.time_min.toFixed(1)} min`);
    },
    onAnimationComplete: () => {
      console.log('[Map] ABM animation complete');
      setShowABMControls(true);
    },
  });

  // Show ABM controls when result is available
  useEffect(() => {
    if (abmResult && abmResult.frames && abmResult.frames.length > 0) {
      setShowABMControls(true);
    }
  }, [abmResult]);

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

    basemapLayers.satellite.addTo(map);
    currentBasemapRef.current = basemapLayers.satellite;

    L.control.zoom({ position: 'bottomleft' }).addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      currentBasemapRef.current = null;
      epicenterMarkerRef.current = null;
      originMarkerRef.current = null;
      tesGroupRef.current = null;
      desaGroupRef.current = null;
      pemukimanGroupRef.current = null;
      inundationGroupRef.current = null;
      faultHighlightRef.current = null;
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

    const originIcon = L.divIcon({
      className: '',
      html: `<div style="width:28px;height:28px;background:radial-gradient(circle,#34d399,#10b981);border:2.5px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 2px 8px rgba(0,0,0,.35)"></div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
    });

    if (customEpicenter) {
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

    if (customOrigin) {
      const originLatLng = [customOrigin.lat, customOrigin.lon];

      if (!originMarkerRef.current) {
        const marker = L.marker(originLatLng, {
          icon: originIcon,
          draggable: true,
          zIndexOffset: 500,
        }).addTo(map);

        marker.bindTooltip('📍 Titik Asal Evakuasi (drag untuk ubah)', { permanent: false });
        marker.on('dragend', (event: any) => {
          const position = event.target.getLatLng();
          onOriginSelect?.({ lat: position.lat, lon: position.lng });
        });

        originMarkerRef.current = marker;
      } else {
        originMarkerRef.current.setLatLng(originLatLng);
      }
    } else if (originMarkerRef.current) {
      map.removeLayer(originMarkerRef.current);
      originMarkerRef.current = null;
    }
  }, [customEpicenter, customOrigin, onEpicenterSelect, onOriginSelect]);

  // 🎯 ZOOM & HIGHLIGHT FAULT: Zoom to selected fault with blinking highlight
  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    // Remove existing highlight
    if (faultHighlightRef.current) {
      map.removeLayer(faultHighlightRef.current);
      faultHighlightRef.current = null;
    }

    // Only proceed if we have a selected fault and fault data
    if (!selectedFault || !faultData || !faultData[selectedFault]) return;

    const fault = faultData[selectedFault];
    const { view_lat, view_lon, view_zoom } = fault;

    // Zoom to fault location
    map.setView([view_lat, view_lon], view_zoom, {
      animate: true,
      duration: 1.5
    });

    // Create blinking highlight marker
    const highlightIcon = L.divIcon({
      className: '',
      html: `<div style="
        width: 40px;
        height: 40px;
        background: radial-gradient(circle, rgba(56, 189, 248, 0.8), rgba(56, 189, 248, 0));
        border-radius: 50%;
        animation: pulse 1s ease-in-out infinite;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.8);
      "></div>
      <style>
        @keyframes pulse {
          0%, 100% { transform: scale(0.8); opacity: 1; }
          50% { transform: scale(1.2); opacity: 0.6; }
        }
      </style>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
    });

    const marker = L.marker([view_lat, view_lon], { icon: highlightIcon, zIndexOffset: 1000 }).addTo(map);
    faultHighlightRef.current = marker;

    // Remove highlight after 3 seconds
    const timeout = setTimeout(() => {
      if (faultHighlightRef.current) {
        map.removeLayer(faultHighlightRef.current);
        faultHighlightRef.current = null;
      }
    }, 3000);

    console.log(`[Map] Zoomed to fault ${selectedFault} at [${view_lat}, ${view_lon}] zoom ${view_zoom}`);

    return () => {
      clearTimeout(timeout);
      if (faultHighlightRef.current) {
        map.removeLayer(faultHighlightRef.current);
        faultHighlightRef.current = null;
      }
    };
  }, [selectedFault, faultData]);

  useEffect(() => {
    if (!mapRef.current) return;
    const container = mapRef.current.getContainer();
    container.style.cursor = isPickingEpicenter || isPickingOrigin ? 'crosshair' : '';
  }, [isPickingEpicenter, isPickingOrigin]);

  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    const handleClick = (event: any) => {
      const latlng = event.latlng;
      if (!latlng) return;
      if (isPickingOrigin) {
        onOriginSelect?.({ lat: latlng.lat, lon: latlng.lng });
        return;
      }
      if (!isPickingEpicenter) return;
      onEpicenterSelect?.({ lat: latlng.lat, lon: latlng.lng });
    };

    map.on('click', handleClick);
    return () => {
      map.off('click', handleClick);
    };
  }, [isPickingEpicenter, isPickingOrigin, onEpicenterSelect, onOriginSelect]);

  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    if (!tesGroupRef.current) {
      tesGroupRef.current = L.layerGroup().addTo(map);
    }

    tesGroupRef.current.clearLayers();
    if (layerVisibility.tes) {
      tesList.forEach((tes) => {
        const marker = L.marker([tes.lat, tes.lon], {
          icon: L.icon({
            iconUrl: '/Icon Titik Kumpul.png',
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
  }, [tesList, layerVisibility.tes]);

  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    if (!desaGroupRef.current) {
      desaGroupRef.current = L.layerGroup().addTo(map);
    }

    desaGroupRef.current.clearLayers();
    if (layerVisibility.desa) {
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
  }, [desaList, layerVisibility.desa]);

  // 🏘 PEMUKIMAN SETTLEMENTS: Load Pemukiman.geojson
  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    if (!pemukimanGroupRef.current) {
      pemukimanGroupRef.current = L.layerGroup().addTo(map);
    }

    pemukimanGroupRef.current.clearLayers();

    // Only load if layer visibility is true
    if (layerVisibility.pemukiman) {
      fetch('/data/Pemukiman.geojson')
        .then(res => res.json())
        .then(geojson => {
          if (!geojson?.features) return;

          geojson.features.forEach((feature: any) => {
            if (feature.geometry?.type !== 'Polygon' && feature.geometry?.type !== 'MultiPolygon') return;

            const geoJSONLayer = L.geoJSON(feature, {
              style: {
                color: '#f97316',
                fillColor: '#f97316',
                fillOpacity: 0.15,
                weight: 1.5,
              }
            });

            geoJSONLayer.bindTooltip(`
              <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 11px;">
                <b style="color: #f97316;">Pemukiman</b>
              </div>
            `, {
              sticky: true,
              direction: 'top',
            });

            pemukimanGroupRef.current.addLayer(geoJSONLayer);
          });

          console.log(`[Map] Loaded ${geojson.features.length} pemukiman settlements`);
        })
        .catch(err => {
          console.error('[Map] Failed to load Pemukiman.geojson:', err);
        });
    }
  }, [layerVisibility.pemukiman]);

  // 🎯 ZOOM TO TES BOUNDS: Fit map to TES locations on first load
  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    // Only zoom if we have TES data and haven't zoomed yet
    if (tesList.length > 0 && !tesGroupRef.current?.hasZoomed) {
      const bounds = L.latLngBounds(tesList.map(tes => [tes.lat, tes.lon]));

      // Add small padding
      map.fitBounds(bounds.pad(0.1));

      // Mark as zoomed to prevent repeated zooming
      if (tesGroupRef.current) {
        (tesGroupRef.current as any).hasZoomed = true;
      }

      console.log('[Map] Zoomed to TES bounds:', bounds);
    }
  }, [tesList.length]); // Only trigger when tesList length changes

  // 🚨 ROUTING VISUALIZATION: Draw evacuation routes as polylines
  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    if (!routesGroupRef.current) {
      routesGroupRef.current = L.layerGroup().addTo(map);
    }

    routesGroupRef.current.clearLayers();

    if (layerVisibility.routes && routingResult?.routes) {
      routingResult.routes.forEach((route) => {
        // Convert [lat, lon] to Leaflet coordinates
        const latlngs = route.route_path.map((coord) => [coord[0], coord[1]]);

        // Polyline styling based on route status
        const polylineOptions = {
          color: route.color || '#4ade80',
          weight: 3,
          opacity: 0.8,
          dashArray: route.status === 'darurat' ? '5, 5' : undefined, // Dashed for emergency routes
        };

        const polyline = L.polyline(latlngs, polylineOptions);

        // Popup with route info
        const popupContent = `
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b>${route.desa} → ${route.target_tes}</b><br>
            Jarak: ${route.distance_km.toFixed(1)} km<br>
            Waktu Jalan: ${route.walk_time_min.toFixed(0)} menit<br>
            Status: <span style="color: ${route.color}; font-weight: bold;">
              ${route.status === 'optimal' ? '✓ Optimal' : route.status === 'alternatif' ? '⚠ Alternatif' : '⛔ Darurat'}
            </span><br>
            Nilai: ${(route.score ? route.score * 100 : 0).toFixed(0)}%
          </div>
        `;

        polyline.bindPopup(popupContent);
        polyline.on('mouseover', () => polyline.setStyle({ weight: 5 }));
        polyline.on('mouseout', () => polyline.setStyle({ weight: 3 }));

        routesGroupRef.current.addLayer(polyline);
      });
    }
  }, [routingResult, layerVisibility.routes]);

  // 🌊 SWE INUNDATION VISUALIZATION: Render flood depth points
  useEffect(() => {
    if (!mapRef.current || !L) return;
    const map = mapRef.current;

    if (!inundationGroupRef.current) {
      inundationGroupRef.current = L.layerGroup().addTo(map);
    }

    inundationGroupRef.current.clearLayers();

    if (layerVisibility.inundation && sweResult?.inundation_geojson?.features) {
      const features = sweResult.inundation_geojson.features;

      features.forEach((feature: any) => {
        if (feature.geometry?.type !== 'Point') return;

        const [lon, lat] = feature.geometry.coordinates;
        const props = feature.properties || {};
        const floodDepth = props.flood_depth || 0;
        const risk = props.risk || 'RENDAH';
        const color = props.color || '#ffe650';
        const elev = props.elev_m || 0;
        const distKm = props.dist_km || 0;

        // Skip if flood depth is too small
        if (floodDepth < 0.05) return;

        // Circle size based on flood depth (larger = deeper)
        const radius = Math.min(25, 8 + floodDepth * 2);

        const circleMarker = L.circleMarker([lat, lon], {
          radius: radius,
          fillColor: color,
          color: '#fff',
          weight: 1.5,
          opacity: 0.9,
          fillOpacity: 0.7,
          stroke: false,
        });

        // Tooltip with flood information
        const tooltipContent = `
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px;">
            <b style="color: ${color};">🌊 Area Tergenang</b><br>
            <hr style="margin: 4px 0; border: none; border-top: 1px solid #ddd;">
            Kedalaman: <b>${floodDepth.toFixed(2)} m</b><br>
            Risiko: <b style="color: ${color};">${risk}</b><br>
            Elevasi: ${elev.toFixed(1)} m<br>
            Jarak dari pantai: ${distKm.toFixed(2)} km<br>
          </div>
        `;

        circleMarker.bindTooltip(tooltipContent, {
          permanent: false,
          direction: 'top',
          offset: [0, -radius - 5],
        });

        // Optional: Popup with more details on click
        const popupContent = `
          <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px; min-width: 200px;">
            <h3 style="margin: 0 0 8px 0; color: ${color}; font-size: 14px;">🌊 Detail Inundasi</h3>
            <table style="width: 100%; border-collapse: collapse;">
              <tr><td style="padding: 4px 0; color: #666;">Kedalaman:</td><td style="padding: 4px 0; font-weight: bold;">${floodDepth.toFixed(2)} m</td></tr>
              <tr><td style="padding: 4px 0; color: #666;">Risiko:</td><td style="padding: 4px 0;"><span style="color: ${color}; font-weight: bold;">${risk}</span></td></tr>
              <tr><td style="padding: 4px 0; color: #666;">Elevasi:</td><td style="padding: 4px 0;">${elev.toFixed(1)} m</td></tr>
              <tr><td style="padding: 4px 0; color: #666;">Jarak Pantai:</td><td style="padding: 4px 0;">${distKm.toFixed(2)} km</td></tr>
              <tr><td style="padding: 4px 0; color: #666;">Koordinat:</td><td style="padding: 4px 0;">${lat.toFixed(5)}, ${lon.toFixed(5)}</td></tr>
            </table>
          </div>
        `;

        circleMarker.bindPopup(popupContent);

        // Hover effect
        circleMarker.on('mouseover', () => {
          circleMarker.setStyle({
            weight: 2.5,
            fillOpacity: 0.9,
          });
        });
        circleMarker.on('mouseout', () => {
          circleMarker.setStyle({
            weight: 1.5,
            fillOpacity: 0.7,
          });
        });

        inundationGroupRef.current.addLayer(circleMarker);
      });

      console.log(`[Map] Rendered ${features.length} inundation points`);
    }
  }, [sweResult, layerVisibility.inundation]);

  return (
    <div className="flex-1 relative overflow-hidden">
      <div ref={mapContainerRef} className="absolute inset-0" />

      {/* Server Status Monitor */}
      <ServerStatus />

      {/* Layer Controls */}
      <LayerControl
        onLayerToggle={handleLayerToggle}
        onBasemapChange={handleBasemapChange}
        onZoomPreset={handleZoomPreset}
      />

      {/* Export Panel */}
      <ExportPanel onExport={handleExport} />

      {/* ABM Agents Layer */}
      {mapRef.current && abmResult && abmResult.frames && abmResult.frames.length > 0 && (
        <ABMAgentsLayer
          map={mapRef.current}
          frame={abmAnimation.currentFrame}
          visible={layerVisibility.abm_agents}
          onAgentClick={(agentId, agent) => {
            console.log('[Map] Agent clicked:', agentId, agent);
          }}
        />
      )}

      {/* ABM Animation Controls */}
      {showABMControls && abmResult && abmResult.frames && abmResult.frames.length > 0 && (
        <div className="absolute bottom-24 left-4 z-[1000] w-80">
          <ABMAnimationControls
            isPlaying={abmAnimation.isPlaying}
            currentFrame={abmAnimation.currentFrameIndex}
            totalFrames={abmAnimation.totalFrames}
            currentTime={abmAnimation.currentTime}
            progress={abmAnimation.progress}
            speed={abmAnimation.speed}
            canPlay={abmAnimation.canPlay}
            canPause={abmAnimation.canPause}
            canNext={abmAnimation.canNext}
            canPrevious={abmAnimation.canPrevious}
            onPlay={abmAnimation.play}
            onPause={abmAnimation.pause}
            onStop={abmAnimation.stop}
            onNext={abmAnimation.nextFrame}
            onPrevious={abmAnimation.previousFrame}
            onSeek={abmAnimation.seekToFrame}
            onSpeedChange={abmAnimation.setSpeed}
          />
        </div>
      )}
    </div>
  );
}
