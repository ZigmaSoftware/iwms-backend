from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import math
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

VAMOSYS_ENDPOINT = "https://api.vamosys.com/getVehicleHistory"
VAMOSYS_USER_ID = "BLUEPLANET"
VAMOSYS_GROUP_NAME = "BLUEPLANET:VAM"

CLIENT_INPUT_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S")
VAMOSYS_DATETIME_FORMATS = (
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
)

STATUS_LABELS = {
    "running": "Running",
    "idle": "Idle",
    "stopped": "Stopped",
    "no_data": "No Data",
}


class VehicleHistoryError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _ensure_vehicle_id(value: Optional[str]) -> str:
    if not value or not str(value).strip():
        raise VehicleHistoryError("vehicle_id is required", status_code=400)
    return str(value).strip()


def _parse_client_datetime(label: str, value: Optional[str]) -> datetime:
    if not value:
        raise VehicleHistoryError(f"{label} is required", status_code=400)

    raw = value.strip()

    for fmt in CLIENT_INPUT_FORMATS:
        try:
            naive = datetime.strptime(raw, fmt)
            return naive.replace(tzinfo=IST)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=IST)
        return parsed.astimezone(IST)
    except ValueError as exc:  # pragma: no cover - defensive
        raise VehicleHistoryError(f"Invalid datetime for {label}", status_code=400) from exc


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (ValueError, TypeError):
        return None


def _pick_first_str(source: Optional[Dict[str, Any]], keys: Sequence[str]) -> Optional[str]:
    if not source:
        return None
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_vamosys_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 1e12:
            seconds = seconds / 1000.0
        return datetime.fromtimestamp(seconds, tz=UTC)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=IST)
            return parsed.astimezone(IST)
        except ValueError:
            pass

        for fmt in VAMOSYS_DATETIME_FORMATS:
            try:
                naive = datetime.strptime(text, fmt)
                return naive.replace(tzinfo=IST)
            except ValueError:
                continue

    return None


def _normalize_ignition(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    text = str(value).strip().upper()
    if text in {"ON", "1", "TRUE", "YES"}:
        return "ON"
    if text in {"OFF", "0", "FALSE", "NO"}:
        return "OFF"
    return "UNKNOWN"


def _derive_status(speed: Optional[float], ignition: str, raw_status: Optional[str]) -> str:
    normalized = (raw_status or "").lower()

    if "no data" in normalized or "nodata" in normalized:
        return "no_data"

    if speed is not None and speed > 2:
        return "running"

    if ignition == "ON":
        return "idle"

    if ignition == "OFF":
        return "stopped"

    return "no_data"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return radius_km * c


def _normalize_track(locations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    track: List[Dict[str, Any]] = []

    for entry in locations:
        lat = _to_float(entry.get("latitude") or entry.get("lat") or entry.get("Latitude"))
        lng = _to_float(entry.get("longitude") or entry.get("lng") or entry.get("Longitude"))
        if lat is None or lng is None:
            continue

        timestamp = _parse_vamosys_timestamp(
            entry.get("lastSeen")
            or entry.get("gpsDatetime")
            or entry.get("gpsDateTime")
            or entry.get("gpsTime")
            or entry.get("timestamp")
            or entry.get("dateTime")
        )
        if timestamp is None:
            continue

        speed = _to_float(entry.get("speed") or entry.get("speedKmph") or entry.get("speedKMH"))
        ignition = _normalize_ignition(
            entry.get("ignitionStatus") or entry.get("ignition") or entry.get("engineStatus") or entry.get("ign")
        )
        raw_status = _pick_first_str(entry, ("vehicleStatus", "status", "vehicleMode", "mode", "vehicleState"))
        status_code = _derive_status(speed, ignition, raw_status)
        address = _pick_first_str(entry, ("address", "location", "nearestLandmark", "locationName", "place")) or "-"
        odometer = _to_float(entry.get("odoDistance") or entry.get("odometer") or entry.get("distance"))

        track.append(
            {
                "lat": lat,
                "lng": lng,
                "speedKmph": round(speed or 0.0, 2),
                "ignition": ignition,
                "status": STATUS_LABELS[status_code],
                "statusCode": status_code,
                "address": address,
                "timestamp": timestamp.astimezone(IST).isoformat(),
                "odometerKm": odometer,
                "_ts": timestamp.astimezone(UTC),
            }
        )

    track.sort(key=lambda item: item["_ts"])
    return track


def _compute_metrics(track: List[Dict[str, Any]]) -> Tuple[float, float, float, Dict[str, int]]:
    durations = {key: 0 for key in STATUS_LABELS.keys()}
    total_distance = 0.0
    top_speed = 0.0
    speed_sum = 0.0
    speed_count = 0

    for idx, point in enumerate(track):
        speed = point.get("speedKmph") or 0.0
        top_speed = max(top_speed, speed)
        if speed > 0:
            speed_sum += speed
            speed_count += 1

        if idx < len(track) - 1:
            nxt = track[idx + 1]
            dist = _haversine_km(point["lat"], point["lng"], nxt["lat"], nxt["lng"])
            point["segmentDistanceKm"] = round(dist, 3)
            total_distance += dist

            current_ts = point["_ts"]
            next_ts = nxt["_ts"]
            delta_seconds = 0
            if current_ts and next_ts:
                delta_seconds = max(0, int((next_ts - current_ts).total_seconds()))
            durations[point["statusCode"]] += delta_seconds
        else:
            point["segmentDistanceKm"] = 0.0

    average_speed = speed_sum / speed_count if speed_count else 0.0
    return total_distance, top_speed, average_speed, durations


def _compute_today_distance(track: List[Dict[str, Any]], target_date: datetime) -> float:
    if not track:
        return 0.0
    total = 0.0
    target = target_date.astimezone(IST).date()
    for point in track:
        ts = point.get("_ts")
        if ts and ts.astimezone(IST).date() == target:
            total += point.get("segmentDistanceKm", 0.0)
    return total


def _build_vehicle_info(vehicle_id: str, source: Optional[Dict[str, Any]], track: List[Dict[str, Any]]) -> Dict[str, Any]:
    last_point = track[-1] if track else None
    driver = _pick_first_str(source, ("driverName", "driver", "driver_name"))
    make = _pick_first_str(source, ("vehicleType", "vehicleModel", "vehicleMake"))
    engine_mode = "Ignition" if last_point and last_point["ignition"] == "ON" else "Engine Off"
    status = STATUS_LABELS.get(last_point["statusCode"], "No Data") if last_point else "No Data"

    return {
        "vehicleId": vehicle_id,
        "registration": _pick_first_str(
            source, ("vehicleNo", "vehicle_number", "vehicleId", "vehicle", "regNo")
        )
        or vehicle_id,
        "variant": make or "Moving Vehicle",
        "driver": driver or "NA",
        "engineMode": engine_mode,
        "status": status,
    }


def fetch_vehicle_history(payload: Dict[str, Any]) -> Dict[str, Any]:
    vehicle_id = _ensure_vehicle_id(payload.get("vehicle_id"))
    from_dt = _parse_client_datetime("from_date", payload.get("from_date"))
    to_dt = _parse_client_datetime("to_date", payload.get("to_date"))

    if from_dt >= to_dt:
        raise VehicleHistoryError("from_date must be older than to_date", status_code=400)

    params = {
        "userId": VAMOSYS_USER_ID,
        "groupName": VAMOSYS_GROUP_NAME,
        "vehicleId": vehicle_id,
        "fromDateUTC": int(from_dt.astimezone(UTC).timestamp() * 1000),
        "toDateUTC": int(to_dt.astimezone(UTC).timestamp() * 1000),
        "interval": -1,
    }

    try:
        resp = requests.get(VAMOSYS_ENDPOINT, params=params, timeout=40)
        resp.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network guard
        raise VehicleHistoryError(f"Vamosys API error: {exc}", status_code=502) from exc

    raw_json: Dict[str, Any] = resp.json() or {}
    locations = raw_json.get("vehicleLocations") or []
    track = _normalize_track(locations)

    total_distance, top_speed, avg_speed, durations = _compute_metrics(track)
    today_distance = _compute_today_distance(track, to_dt)

    meta_source = locations[0] if locations else raw_json
    vehicle_info = _build_vehicle_info(vehicle_id, meta_source, track)

    first_ts = track[0]["_ts"].astimezone(IST).isoformat() if track else None
    last_ts = track[-1]["_ts"].astimezone(IST).isoformat() if track else None

    for point in track:
        point.pop("_ts", None)

    meta = {
        "vehicleId": vehicle_id,
        "displayName": vehicle_info["registration"],
        "groupName": params["groupName"],
        "requestedFrom": from_dt.isoformat(),
        "requestedTo": to_dt.isoformat(),
        "dataFrom": first_ts,
        "dataTo": last_ts,
        "records": len(track),
    }

    stats = {
        "distanceKm": round(total_distance, 2),
        "avgSpeedKmph": round(avg_speed, 2),
        "topSpeedKmph": round(top_speed, 2),
        "todayDistanceKm": round(today_distance, 2),
        "durations": durations,
    }

    message = "success" if track else "No records found"

    return {
        "msg": message,
        "meta": meta,
        "stats": stats,
        "vehicleInfo": vehicle_info,
        "track": track,
    }
