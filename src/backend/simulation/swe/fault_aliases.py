"""
Fault Alias System
==================
Mapping fault ID dari frontend ke backend.
Frontend pakai ID format lama (baribis-1, baribis-2).
Backend pakai ID format baru dari shapefile (baribiskendengf_cirebon_1).
"""

# Alias mapping: frontend_id → backend_id
FAULT_ALIASES = {
    # Baribis Kendeng Fault
    'baribis-1': 'baribiskendengf_cirebon_1',
    'baribis-2': 'baribiskendengf_cirebon_2',
    'baribis-3': 'baribiskendengf_tampomas',
    'baribis-4': 'baribiskendengf_semarang',
    'baribis-5': 'baribiskendengf_rawapening',

    # Megathrust (legacy)
    'mega-1': 'sumatranfault',  # Megathrust Sumatera Barat
    'mega-7': 'sunda_trench',  # Megathrust Sunda
    'mega-8': 'java_trench',   # Megathrust Jawa
}

def resolve_fault_id(fault_id: str) -> str:
    """
    Resolve frontend fault ID ke backend fault ID.
    Jika tidak ada di alias, kembalikan fault_id asli.
    """
    return FAULT_ALIASES.get(fault_id, fault_id)


def build_aliases(faults: dict) -> dict:
    """
    Build fault entries untuk semua frontend alias.
    Menambahkan entry aliased ke fault dict.
    """
    aliased = {}

    for frontend_id, backend_id in FAULT_ALIASES.items():
        if backend_id in faults:
            # Copy fault data
            fault_data = faults[backend_id].copy()

            # Update label untuk frontend
            original_label = fault_data['label']
            if 'cirebon_1' in backend_id:
                fault_data['label'] = 'Baribis Kendeng F - Cirebon-1'
            elif 'cirebon_2' in backend_id:
                fault_data['label'] = 'Baribis Kendeng F - Cirebon-2'
            elif 'tampomas' in backend_id:
                fault_data['label'] = 'Baribis Kendeng F - Tampomas'
            elif 'semarang' in backend_id:
                fault_data['label'] = 'Baribis Kendeng F - Semarang'
            elif 'rawapening' in backend_id:
                fault_data['label'] = 'Baribis Kendeng F - Rawapening'

            aliased[frontend_id] = fault_data

    return aliased
