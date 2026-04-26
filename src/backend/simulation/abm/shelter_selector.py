import logging
from dataclasses import dataclass
import math
import os

try:
    import geopandas as gpd
    import pandas as pd
except ImportError:
    pass

logger = logging.getLogger(__name__)

@dataclass
class ShelterObj:
    shelter_id: str
    name: str
    lat: float
    lon: float
    capacity: int
    type: str = 'TES'  # 'TES' or 'PublicFacility'

def load_shelter_data(shapefile_path: str):
    if not os.path.exists(shapefile_path):
        return None
    gdf = gpd.read_file(shapefile_path)
    if gdf.crs is not None:
        gdf = gdf.to_crs(epsg=4326)
    return gdf

class ShelterSelector:
    def __init__(self, shelter_gdf, use_gpu=True):
        self.shelter_gdf = shelter_gdf
        self.use_gpu = use_gpu
        self.safe_shelters = []

    def add_shelter_source(self, additional_gdf):
        """Gabungkan sumber shelter tambahan (misal: Fasilitas Umum)"""
        if additional_gdf is not None:
            if self.shelter_gdf is None:
                self.shelter_gdf = additional_gdf
            else:
                self.shelter_gdf = gpd.GeoDataFrame(
                    pd.concat([self.shelter_gdf, additional_gdf], ignore_index=True),
                    crs=self.shelter_gdf.crs
                )
            logger.info(f"Added additional shelters. Total: {len(self.shelter_gdf)}")

    def filter_safe_shelters(self, inundation_polygon, min_distance_m=100):
        self.safe_shelters = []
        if self.shelter_gdf is None:
            return []
            
        for idx, row in self.shelter_gdf.iterrows():
            geom = row.geometry
            if geom is None: continue
            
            lat, lon = geom.centroid.y, geom.centroid.x
            
            # Simple check
            is_inundated = False
            if inundation_polygon is not None:
                if hasattr(inundation_polygon, 'contains'):
                    is_inundated = inundation_polygon.contains(geom.centroid)
                elif isinstance(inundation_polygon, list):
                    for poly in inundation_polygon:
                        if hasattr(poly, 'contains') and poly.contains(geom.centroid):
                            is_inundated = True
                            break
            
            if not is_inundated:
                # Ambil kapasitas dari berbagai kemungkinan nama kolom
                # TES_Bantul.shp menggunakan 'kapasitas' (huruf kecil)
                capacity = int(row.get('kapasitas', row.get('KAPASITAS', row.get('capacity', row.get('Capacity', 500)))))
                name = str(row.get('Nama', row.get('name', row.get('NAME', f"Shelter_{idx}"))))
                s_type = 'TES' if 'TES' in name.upper() or 'TES' in str(row.get('type', '')) else 'PublicFacility'
                
                self.safe_shelters.append(ShelterObj(
                    shelter_id=str(idx),
                    name=name,
                    lat=lat,
                    lon=lon,
                    capacity=capacity,
                    type=s_type
                ))
        return self.safe_shelters

    def assign_shelters_to_settlements(self, settlements, max_distance_km=5.0):
        assignments = {}
        for s in settlements:
            best_shelter = None
            best_dist = float('inf')
            for shelter in self.safe_shelters:
                # Haversine distance
                phi1, phi2 = math.radians(s['lat']), math.radians(shelter.lat)
                dphi = math.radians(shelter.lat - s['lat'])
                dlambda = math.radians(shelter.lon - s['lon'])
                a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                dist = 6371 * c
                if dist < best_dist:
                    best_dist = dist
                    best_shelter = shelter
            if best_shelter:
                assignments[s['settlement_id']] = best_shelter.shelter_id
        return assignments

    def get_shelter_by_id(self, shelter_id: str):
        for s in self.safe_shelters:
            if s.shelter_id == shelter_id:
                return s
        return None

    def get_summary_statistics(self):
        return {
            'total_safe_shelters': len(self.safe_shelters),
            'total_capacity': sum(s.capacity for s in self.safe_shelters),
            'types': {
                'TES': sum(1 for s in self.safe_shelters if s.type == 'TES'),
                'PublicFacility': sum(1 for s in self.safe_shelters if s.type == 'PublicFacility')
            }
        }
