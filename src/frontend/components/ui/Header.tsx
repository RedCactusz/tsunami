'use client';

import React from 'react';

export default function Header() {
  return (
    <header
      className="h-14 flex-shrink-0 px-6 flex items-center justify-between border-b"
      style={{
        background: '#ffffff',
        borderColor: '#e2e8f0',
      }}
    >
      {/* Logo Section */}
      <div className="flex items-center gap-3">
        <img
          src="/Logo UGM.png"
          alt="Logo UGM"
          className="h-10 w-auto object-contain"
        />
        <div className="ml-2">
          <h1 className="text-lg font-bold" style={{ color: '#1e293b' }}>
            WebGIS Tsunami
          </h1>
          <p className="text-xs" style={{ color: '#64748b' }}>
            Sistem Informasi Pemodelan Tsunami & Evakuasi
          </p>
        </div>
      </div>

      {/* Badge */}
      <div className="flex items-center gap-2">
        <div
          className="px-3 py-1.5 rounded-full text-xs font-medium"
          style={{
            background: '#fef3c7',
            color: '#78350f'
          }}
        >
          🌊 Simulasi & Evakuasi
        </div>
      </div>
    </header>
  );
}
