from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.core.evacuation_abm import EvacuationABMSolver
import os

app = FastAPI(title="Tsunami Evacuation API")

# Inisialisasi Solver (Pastikan path ke data vektor benar)
VEKTOR_DIR = os.path.join(os.getcwd(), "..", "data")
solver = EvacuationABMSolver(vektor_dir=VEKTOR_DIR)

# Kita jalankan build_caches saat startup agar API cepat merespon
@app.on_event("startup")
async def startup_event():
    solver.build_caches()

class SimulationRequest(BaseModel):
    transport: str = "walking"
    speed_kmh: float = 5.0

@app.get("/")
def read_root():
    return {"message": "Tsunami Evacuation Simulation API is running"}

@app.post("/simulate")
async def run_simulation(request: SimulationRequest):
    try:
        # Menjalankan fungsi run_abm dari script asli kamu
        results = solver.run_abm(
            transport=request.transport,
            speed_kmh=request.speed_kmh
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))