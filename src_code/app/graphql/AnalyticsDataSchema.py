# app/graphql/AnalyticsDataSchema.py
import strawberry
from bson import ObjectId
from dateutil import parser
from zoneinfo import ZoneInfo
from app.models import get_db
from statistics import stdev, mean
from collections import defaultdict
from math import radians, sin, cos, atan2, sqrt
from app.models.AnalyticsData import AnalyticsData
from datetime import datetime, timedelta, timezone
from app.controllers.AnalyticsDataController import serialize

IST = ZoneInfo("Asia/Kolkata")

# -----------------------------
# TIMESTAMP UTIL
# -----------------------------
def parse_iso_to_ist(dt_str):
    if not dt_str:
        return None
    try:
        dt = parser.parse(str(dt_str))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except:
        return None

# -----------------------------
# HAVERSINE
# -----------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    try:
        lat1 = float(lat1); lon1 = float(lon1)
        lat2 = float(lat2); lon2 = float(lon2)
    except:
        return 0.0

    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat/2)**2 +
        cos(radians(lat1)) * cos(radians(lat2)) *
        sin(dlon/2)**2
    )
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


# -----------------------------
# MAIN ANALYTICS CALC — LAST 24 HOURS
# -----------------------------
async def compute_distance_last_24_hours(db, imei):
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    cutoff = now_ist - timedelta(hours=24)

    recs = await db.find(AnalyticsData, {"imei": imei})
    if not recs:
        return []

    points = []
    for r in recs:
        raw_ts = (
            getattr(r, "device_timestamp", None)
            or getattr(r, "deviceTimestamp", None)
            or getattr(r, "timestamp", None)
        )

        dt = parse_iso_to_ist(raw_ts)
        if not dt or dt < cutoff:
            continue

        points.append({
            "dt": dt,
            "lat": getattr(r, "latitude", None),
            "lon": getattr(r, "longitude", None),
        })

    if not points:
        return []

    points.sort(key=lambda x: x["dt"])

    # Remove consecutive identical points
    unique_pts = []
    last = (None, None)

    for p in points:
        lat, lon = p["lat"], p["lon"]
        try:
            latf, lonf = float(lat), float(lon)
        except:
            unique_pts.append(p)
            last = (lat, lon)
            continue

        if last == (latf, lonf):
            continue

        unique_pts.append(p)
        last = (latf, lonf)

    if len(unique_pts) < 2:
        return []

    buckets = defaultdict(float)
    running = 0.0

    for i in range(1, len(unique_pts)):
        a = unique_pts[i-1]
        b = unique_pts[i]

        if not a["lat"] or not a["lon"] or not b["lat"] or not b["lon"]:
            continue

        dist = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
        hour_key = b["dt"].replace(minute=0, second=0, microsecond=0)
        buckets[hour_key] += dist

    out = []
    current = cutoff.replace(minute=0, second=0, microsecond=0)

    for i in range(24):
        slot = current + timedelta(hours=i + 1)
        dist = round(buckets.get(slot, 0.0), 3)
        running += dist
        out.append({
            "hour": slot.strftime("%H:00"),
            "dateHour": slot.isoformat(),
            "distance": dist,
            "cumulative": round(running, 3)
        })

    return out

@strawberry.type
class AnalyticsDataType:
    id: str | None
    topic: str | None
    imei: str | None
    interval: int | None

    geoid: str | None
    packet: str | None

    latitude: str | None
    longitude: str | None
    speed: float | None

    battery: str | None
    signal: str | None
    alert: str | None

    # PRIMARY field used by frontend for sorting/display
    timestamp: str | None

    deviceTimestamp: str | None
    deviceRawTimestamp: str | None

    rawPacket: str | None
    rawImei: str | None
    rawAlert: str | None
    rawTemperature: str | None
    rawSpeed: str | None
    rawSignal: str | None
    rawBattery: str | None
    rawGeoid: str | None
    rawLatitude: str | None
    rawLongitude: str | None
    rawInterval: str | None
    rawBody: str | None
    rawPhone1: str | None
    rawPhone2: str | None
    rawControlPhone: str | None
    rawNormalSendingInterval: str | None
    rawSOSSendingInterval: str | None
    rawNormalScanningInterval: str | None
    rawAirplaneInterval: str | None
    rawSpeedLimit: str | None
    rawLowbatLimit: str | None
    type: str | None


@strawberry.type
class DistanceBucketType:
    hour: str | None
    dateHour: str | None
    distance: float | None
    cumulative: float | None

@strawberry.type
class AnalyticsHealthType:
    gpsScore: float
    movement: list[str]
    movementStats: list[str]
    temperatureHealthIndex: float
    temperatureStatus: str

@strawberry.type
class UptimeAnalyticsType:
    score: float
    expectedPackets: int
    receivedPackets: int
    largestGapSec: float
    dropouts: int

def safe_float(x):
    try:
        return float(str(x).replace("c", "").replace("C", "").strip())
    except:
        return None


def compute_gps_score(packets):
    # use ONLY last 10 Normal packets
    normals = [p for p in packets if p.get("packet") == "N"]
    normals = normals[:10]

    if len(normals) < 3:
        return 0.0  # not enough data

    lats = [safe_float(p.get("latitude")) for p in normals if safe_float(p.get("latitude"))]
    lons = [safe_float(p.get("longitude")) for p in normals if safe_float(p.get("longitude"))]
    signals = [safe_float(p.get("signal")) for p in normals if safe_float(p.get("signal"))]

    if len(lats) < 3 or len(lons) < 3:
        return 0.0

    lat_jitter = stdev(lats)
    lon_jitter = stdev(lons)
    avg_signal = mean(signals) if signals else 0

    # Scoring rule
    score = 100
    score -= lat_jitter * 5
    score -= lon_jitter * 5
    score -= max(0, 100 - avg_signal)

    return max(0, min(100, round(score, 2)))


def classify_movement(speed):
    if speed is None:
        return "unknown"

    s = float(speed)

    if s <= 1:
        return "stationary"
    if s <= 5:
        return "crawling"
    if s <= 45:
        return "cruising"
    if s <= 70:
        return "highway"
    return "overspeed"


def compute_temperature_health(packets):
    temps = [safe_float(p.get("rawTemperature")) for p in packets if safe_float(p.get("rawTemperature"))]
    if not temps:
        return (100, "normal")

    latest = temps[0]
    thi = 100

    # High temperature penalty
    if latest > 60:
        thi -= 50
    elif latest > 50:
        thi -= 30
    elif latest > 45:
        thi -= 15

    # Temperature rising quickly?
    if len(temps) >= 3 and (temps[0] - temps[2] > 5):
        thi -= 20

    thi = max(0, min(100, thi))

    status = (
        "critical" if thi < 40 else
        "warning" if thi < 60 else
        "warm" if thi < 80 else
        "normal"
    )

    return (thi, status)

@strawberry.type
class Query:

    @strawberry.field
    async def analyticsData(self) -> list[AnalyticsDataType]:
        recs = await get_db().find(AnalyticsData)
        return [AnalyticsDataType(**serialize(r)) for r in recs]

    @strawberry.field
    async def analyticsDataById(self, id: str) -> AnalyticsDataType | None:
        try:
            rec = await get_db().find_one(AnalyticsData, {"_id": ObjectId(id)})
        except:
            return None
        return AnalyticsDataType(**serialize(rec)) if rec else None

    @strawberry.field
    async def analyticsDataByTopic(self, topic: str) -> list[AnalyticsDataType]:
        recs = await get_db().find(AnalyticsData, {"topic": topic})
        return [AnalyticsDataType(**serialize(r)) for r in recs]
    
    @strawberry.field
    async def latestAnalyticsData(self, imei: str) -> AnalyticsDataType | None:
        db = get_db()
    
        recs = await db.find(
            AnalyticsData,
            {"imei": imei},
            sort=AnalyticsData.device_timestamp.desc(),
            limit=1
        )
    
        if not recs:
            return None
    
        return AnalyticsDataType(**serialize(recs[0]))
    
    @strawberry.field
    async def analyticsDataByFilter(self, imei: str | None = None, type: str | None = None) -> list[AnalyticsDataType]:

        db = get_db()
        query = {}

        if imei:
            query["imei"] = imei

        if type:
            query["type"] = type

        query["raw_phonenum1"] = {"$nin": [None, ""]}
        query["raw_phonenum2"] = {"$nin": [None, ""]}
        query["raw_controlroomnum"] = {"$nin": [None, ""]}

        recs = await db.find(AnalyticsData, query, sort=AnalyticsData.device_timestamp.desc())

        return [AnalyticsDataType(**serialize(r)) for r in recs]

    @strawberry.field
    async def analyticsDataByImei(self, imei: str) -> list[AnalyticsDataType]:
        recs = await get_db().find(AnalyticsData, {"imei": imei})
        return [AnalyticsDataType(**serialize(r)) for r in recs]

    @strawberry.field
    async def analyticsDataPaginated(self, skip: int, limit: int) -> list[AnalyticsDataType]:
        recs = await get_db().find(AnalyticsData)
        sliced = recs[skip:skip + limit]
        return [AnalyticsDataType(**serialize(r)) for r in sliced]

    @strawberry.field
    async def analyticsDataCount(self) -> int:
        return await get_db().count(AnalyticsData)

    @strawberry.field
    async def analyticsDistance24(self, imei: str) -> list[DistanceBucketType]:
        db = get_db()
        buckets = await compute_distance_last_24_hours(db, imei)
        return [DistanceBucketType(hour=b["hour"], dateHour=b["dateHour"], distance=b["distance"], cumulative=b["cumulative"]) for b in buckets]

    @strawberry.field
    async def analyticsHealth(self, imei: str) -> AnalyticsHealthType:
        # Fetch model objects
        recs = await get_db().find(AnalyticsData, {"imei": imei})

        if not recs:
            return AnalyticsHealthType(
                gpsScore=0,
                movement=[],
                movementStats=[],
                temperatureHealthIndex=100,
                temperatureStatus="normal",
            )

        # Convert to dict form (serialize)
        recs = [serialize(r) for r in recs]

        # Sort newest → oldest
        recs.sort(
            key=lambda r: (
                    r.get("device_timestamp")
                    or r.get("deviceTimestamp")
                    or r.get("timestamp")
                    or ""
            ),
            reverse=True,
        )

        # Compute components
        gps_score = compute_gps_score(recs)

        movement_list = [
            classify_movement(r.get("speed"))
            for r in recs[:50]
        ]

        stats = []
        for m in ["stationary", "crawling", "cruising", "highway", "overspeed"]:
            stats.append(f"{m}:{movement_list.count(m)}")

        thi, temp_status = compute_temperature_health(recs)

        return AnalyticsHealthType(
            gpsScore=gps_score,
            movement=movement_list,
            movementStats=stats,
            temperatureHealthIndex=thi,
            temperatureStatus=temp_status,
        )

    @strawberry.field
    async def analyticsUptime(self, imei: str) -> UptimeAnalyticsType:
        recs = await get_db().find(AnalyticsData, {"imei": imei})

        # Sort newest → oldest by device_timestamp or raw timestamp
        def extract_ts(obj):
            raw = (
                    getattr(obj, "device_timestamp", None)
                    or getattr(obj, "deviceRawTimestamp", None)
                    or getattr(obj, "timestamp", None)
                    or None
            )

            dt = parse_iso_to_ist(raw)

            # fallback: ensure sort() never receives a string
            return dt or datetime.min.replace(tzinfo=IST)

        recs.sort(key=lambda r: extract_ts(r), reverse=True)

        now = datetime.now(timezone.utc).astimezone(IST)
        cutoff = now - timedelta(hours=24)

        # -----------------------------
        # Collect timestamps (last 24 hours)
        # -----------------------------
        packets = []
        for r in recs:
            raw = extract_ts(r)
            dt = parse_iso_to_ist(raw)
            if dt and dt >= cutoff:
                packets.append(dt)

        # Expected packets based on 150 sec interval
        expected = int(86400 / 150)  # 576
        received = len(packets)

        # -----------------------------
        # Largest gap & dropout count
        # -----------------------------
        if not packets:
            return UptimeAnalyticsType(
                score=0,
                expectedPackets=expected,
                receivedPackets=0,
                largestGapSec=0,
                dropouts=0
            )

        packets_sorted = sorted(packets)

        largest_gap = 0
        dropouts = 0

        for i in range(1, len(packets_sorted)):
            diff = (packets_sorted[i] - packets_sorted[i - 1]).total_seconds()

            if diff > largest_gap:
                largest_gap = diff

            if diff > 600:  # >10 min
                dropouts += 1

        # -----------------------------
        # Scoring System
        # -----------------------------
        consistencyScore = (received / expected) * 100 if expected else 0
        consistencyScore = min(100, max(0, consistencyScore))

        # Gap score
        if largest_gap <= 180:
            gapScore = 100
        elif largest_gap <= 600:
            gapScore = 80
        elif largest_gap <= 1800:
            gapScore = 50
        elif largest_gap <= 3600:
            gapScore = 20
        else:
            gapScore = 0

        # Dropout score
        dropoutScore = max(0, 100 - (dropouts * 15))

        # Final weighted score
        score = (
                consistencyScore * 0.5 +
                gapScore * 0.3 +
                dropoutScore * 0.2
        )
        score = round(max(0, min(100, score)), 1)

        return UptimeAnalyticsType(
            score=score,
            expectedPackets=expected,
            receivedPackets=received,
            largestGapSec=largest_gap,
            dropouts=dropouts
        )


schema = strawberry.Schema(query=Query)
