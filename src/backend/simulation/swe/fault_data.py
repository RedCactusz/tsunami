# backend/simulation/core/fault_data.py
# ⚠️  FILE INI TIDAK BOLEH DIEKSPOS KE FRONTEND
# ⚠️  Jangan import di endpoint yang return ke client

"""
Sumber: InaFault Pusgen 2016 v1.2
Sheet: Java + Megathrust (2)
"""

# ── Java Faults (Sheet: Java) ─────────────────────────────────────
JAVA_FAULTS = {
    "cimandiri_cimandiri": {
        "name": "Cimandiri — Cimandiri",
        "type": "reverse",
        "strike": 90,   # E-W
        "dip": 45.0,    # 45S
        "rake": 90.0,
        "length_km": 23.0,
        "width_km": 28.0,
        "depth_top_km": 0.0,
        "mmax_design": 6.7,
        "slip_rate_myr": 0.0028,
        "epicenter_lat": -6.9,
        "epicenter_lon": 107.0,
        "historical": ["1844", "1879(M6.3)", "1900(M6.2)", "1982(M5.5)"],
        "source": "Pusgen2016_Java_No1",
    },
    "lembang": {
        "name": "Lembang",
        "type": "strike_slip",
        "strike": 90,   # E-W
        "dip": 90.0,
        "rake": 0.0,
        "length_km": 30.0,
        "width_km": 20.0,
        "depth_top_km": 0.0,
        "mmax_design": 6.8,
        "slip_rate_myr": 0.0048,
        "epicenter_lat": -6.83,
        "epicenter_lon": 107.62,
        "historical": [],
        "source": "Pusgen2016_Java_No4",
    },
    "opak": {
        "name": "Sesar Opak",
        "type": "strike_slip",
        "strike": 45,   # NE
        "dip": 60.0,    # 60E
        "rake": 0.0,
        "length_km": 45.0,
        "width_km": 20.0,
        "depth_top_km": 5.0,
        "mmax_design": 7.0,
        "slip_rate_myr": 0.0037,
        "epicenter_lat": -7.95,
        "epicenter_lon": 110.41,
        "historical": ["1867(M6.9)", "2006(M6.4)"],
        "source": "Pusgen2016_Java_No29",
    },
    "merapi_merbabu": {
        "name": "Merapi-Merbabu",
        "type": "strike_slip",
        "strike": 0,    # NS
        "dip": 90.0,
        "rake": 0.0,
        "length_km": 28.0,
        "width_km": 20.0,
        "depth_top_km": 5.0,
        "mmax_design": 6.8,
        "slip_rate_myr": 0.001,
        "epicenter_lat": -7.54,
        "epicenter_lon": 110.44,
        "historical": [],
        "source": "Pusgen2016_Java_No30",
    },
}

# ── Java Megathrust (Sheet: Megathrust + Java row 37) ─────────────
JAVA_MEGATHRUST = {
    "M9_200yr": {
        "name": "Java Megathrust — Jawa Tengah (200 tahun)",
        "segment": "M9",
        "type": "thrust",
        "strike": 270,  # E-W
        "dip": 15.0,    # USGSS Slab 1.0
        "rake": 90.0,
        "length_km": 280.0,
        "width_km": 200.0,
        "depth_top_km": 5.0,
        "mmax_design": 8.7,
        "slip_m": 8.0,          # 200 yr recurrence
        "Mo": 1.344e22,
        "epicenter_lat": -9.0,
        "epicenter_lon": 110.0,
        "slip_rate_myr": 0.04,
        "historical": ["1921(Mw8.1)", "1937(Mw7.2)", "1943(Mw8.1)"],
        "source": "Pusgen2016_Megathrust_M9",
        "scaling": "Strasser2010",
    },
    "M9_500yr": {
        "name": "Java Megathrust — Jawa Tengah (500 tahun)",
        "segment": "M9",
        "type": "thrust",
        "strike": 270,
        "dip": 15.0,
        "rake": 90.0,
        "length_km": 280.0,
        "width_km": 200.0,
        "depth_top_km": 5.0,
        "mmax_design": 8.9,
        "slip_m": 20.0,         # 500 yr recurrence
        "Mo": 3.360e22,
        "epicenter_lat": -9.0,
        "epicenter_lon": 110.0,
        "slip_rate_myr": 0.04,
        "historical": ["1921(Mw8.1)", "1937(Mw7.2)", "1943(Mw8.1)"],
        "source": "Pusgen2016_Megathrust_M9",
        "scaling": "Strasser2010",
    },
    "M8910_worst": {
        "name": "Java Megathrust — Multi-Segmen JB+JT+JTM (Worst Case)",
        "segment": "M8-9-10",
        "type": "thrust",
        "strike": 270,
        "dip": 15.0,
        "rake": 90.0,
        "length_km": 560.0,
        "width_km": 200.0,
        "depth_top_km": 5.0,
        "mmax_design": 9.1,
        "slip_m": 40.0,
        "Mo": 6.720e22,
        "epicenter_lat": -9.2,
        "epicenter_lon": 109.5,
        "slip_rate_myr": 0.04,
        "historical": [
            "1903(Mw8.1)", "1921(Mw8.1)",
            "1994(Mw7.7)", "2006(Mw7.8)"
        ],
        "source": "Pusgen2016_Megathrust_M8-9-10",
        "scaling": "Strasser2010",
    },
}

# ── Public labels ONLY — aman dikirim ke frontend ─────────────────
# Tidak mengandung parameter teknis sesar (strike, dip, rake, slip)
# Hanya label, Mw, kategori, dan titik pandang peta (view coordinates)
FAULT_PUBLIC_LABELS = {
    # Megathrust
    "M9_200yr":    {"label": "Java Megathrust Jawa Tengah",  "mw": 8.7, "category": "megathrust", "recurrence": "200 tahun",
                    "view_lat": -9.0,  "view_lon": 110.0, "view_zoom": 8},
    "M9_500yr":    {"label": "Java Megathrust Jawa Tengah",  "mw": 8.9, "category": "megathrust", "recurrence": "500 tahun",
                    "view_lat": -9.0,  "view_lon": 110.0, "view_zoom": 8},
    "M8910_worst": {"label": "Java Megathrust Multi-Segmen", "mw": 9.1, "category": "megathrust", "recurrence": "Worst Case",
                    "view_lat": -9.2,  "view_lon": 109.5, "view_zoom": 7},
    # Sesar darat
    "opak":        {"label": "Sesar Opak",      "mw": 7.0, "category": "fault", "recurrence": "—",
                    "view_lat": -7.95, "view_lon": 110.41, "view_zoom": 11},
    "lembang":     {"label": "Sesar Lembang",   "mw": 6.8, "category": "fault", "recurrence": "—",
                    "view_lat": -6.83, "view_lon": 107.62, "view_zoom": 12},
}
