"use client";

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import Image from 'next/image';
import 'leaflet/dist/leaflet.css';

// Import peta secara dinamis agar tidak error saat build (SSR)
const MapContainer = dynamic(() => import('react-leaflet').then(mod => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then(mod => mod.TileLayer), { ssr: false });

export default function WebGISPage() {
  return (
    <div className="flex flex-col h-screen w-full overflow-hidden">
      
      {/* HEADER: Tempat Logo BIG & UGM */}
      <header className="bg-white border-b z-50 px-6 py-3 flex justify-between items-center shadow-sm">
        <div className="flex items-center gap-4">
          <Image src="/assets/logos/Logo BIG.png" alt="BIG" width={45} height={45} />
          <Image src="/assets/logos/Logo UGM.png" alt="UGM" width={35} height={35} />
          <div className="h-8 w-[1px] bg-gray-300 mx-2"></div>
          <h1 className="text-lg font-bold text-gray-800 tracking-tight">
            SIMULASI EVAKUASI TSUNAMI <span className="text-blue-600 font-normal">| WebGIS v2</span>
          </h1>
        </div>
      </header>

      <div className="flex flex-1 relative">
        
        {/* SIDEBAR: Pindahkan isi index.html lama ke sini */}
        <aside className="w-80 bg-slate-50 border-r shadow-inner z-40 flex flex-col p-5 overflow-y-auto">
          <h2 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Parameter Simulasi</h2>
          
          <div className="space-y-4">
            {/* Contoh Input - Nanti sesuaikan dengan index.html lamamu */}
            <div>
              <label className="text-xs font-semibold text-gray-600">Kecepatan Jalan Kaki (km/jam)</label>
              <input type="number" defaultValue={5} className="w-full mt-1 p-2 border rounded-md bg-white text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>

            <button className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg transition-all shadow-md active:scale-95">
              Jalankan ABM
            </button>
          </div>

          <div className="mt-auto pt-6 border-t">
            <p className="text-[10px] text-gray-400 text-center">Laboratorium Geodesi & Geomatika UGM @ 2026</p>
          </div>
        </aside>

        {/* MAP AREA */}
        <main className="flex-1 z-30">
          <MapContainer 
            center={[-7.9, 110.3]} // Sesuaikan dengan lokasi penelitianmu
            zoom={13} 
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </MapContainer>
        </main>
        
      </div>
    </div>
  );
}
