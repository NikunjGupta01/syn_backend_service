# app/models/GeofenceData.py

from odmantic import Field, Model
from datetime import datetime
from typing import List, Dict

class GeofenceData(Model):
    imei: str
    geofence_number: str
    geofence_id: str
    coordinates: List[Dict[str, float]]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "geofence_data"
    }
