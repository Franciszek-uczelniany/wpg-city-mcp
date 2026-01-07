import httpx
from math import radians, cos, sin, asin, sqrt
from tools.locations import get_coordinates

async def get_walking_directions(lat1, lon1, lat2, lon2):
    """Get walking instructions from OSRM."""
    try:
        osrm_url = f"http://router.project-osrm.org/route/v1/walking/{lon1},{lat1};{lon2},{lat2}"
        params = {"steps": "true", "overview": "false"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(osrm_url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes", [])
                if routes:
                    steps = routes[0].get("legs", [])[0].get("steps", [])
                    instructions = []
                    for step in steps:
                        maneuver = step.get("maneuver", {})
                        m_type = maneuver.get("type", "")
                        modifier = maneuver.get("modifier", "")
                        street = step.get("name", "") or "path"
                        
                        direction = f"{m_type} {modifier}".strip()
                        if m_type == "depart": direction = "Head"
                        if m_type == "arrive": direction = "Arrive"
                        
                        instr = f"{direction} on {street}" if street else direction
                        instr = instr.replace("  ", " ").strip().capitalize()
                        instructions.append(f"       ↳ {instr}")
                        
                    return instructions
    except Exception:
        pass
    return []

def haversine(lat1, lon1, lat2, lon2):
    """Calculate great circle distance in km."""
    R = 6371 # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2) * sin(dlat/2) + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) * sin(dlon/2)
    c = 2 * asin(sqrt(a))
    return R * c

from datetime import datetime, timedelta

async def get_transit_details(origin: str, destination: str, date: str | None = None, time: str | None = None) -> tuple[float, int]:
    """
    Calculate the 'cost' and 'duration' of travel between two points.
    Returns (cost, duration_minutes).
    Cost = Total Minutes + (Transfer Count * 10)
    Duration = Total Minutes
    """
    import config
    
    url = config.TRANSIT_TRIP_PLANNER_URL
    params = {
        "api-key": config.TRANSIT_API_KEY,
        "origin": origin,
        "destination": destination,
        "mode": config.DEFAULT_TRANSIT_MODE
    }
    
    if date: params["date"] = date
    if time: params["time"] = time
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                plans = data.get("plans", [])
                if plans:
                    plan = plans[0]
                    times = plan.get("times", {}).get("durations", {})
                    total_time = times.get("total", 0)
                    
                    segments = plan.get("segments", [])
                    ride_count = sum(1 for s in segments if s.get("type") == "ride")
                    transfers = max(0, ride_count - 1)
                    
                    cost = total_time + (transfers * 15)
                    return cost, total_time
    except Exception:
        pass
        
    return float('inf'), 0

def add_minutes(date_str: str | None, time_str: str | None, minutes: int) -> tuple[str | None, str | None]:
    """Add minutes to a date/time pair."""
    if not time_str:
        return date_str, time_str
        
    # Default date if missing but time is present (needed for rollover)
    dt_str = f"{date_str} {time_str}" if date_str else f"2000-01-01 {time_str}"
    fmt = "%Y-%m-%d %H:%M"
    
    try:
        dt = datetime.strptime(dt_str, fmt)
        dt += timedelta(minutes=minutes)
        
        new_date = dt.strftime("%Y-%m-%d") if date_str else None
        new_time = dt.strftime("%H:%M")
        return new_date, new_time
    except ValueError:
        return date_str, time_str

async def optimize_stop_order_greedy(
    stops_formatted: list[str], 
    start_date: str | None = None, 
    start_time: str | None = None,
    stay_times: dict[str, int] | None = None
) -> list[str]:
    """
    Reorder stops using Nearest Neighbor with Time Awareness.
    
    Args:
        stops_formatted: List of stops (0 is fixed start).
        start_date: YYYY-MM-DD
        start_time: HH:MM
        stay_times: Dict mapping stop formatted string -> minutes to stay.
    """
    if len(stops_formatted) <= 2:
        return stops_formatted
        
    optimized = [stops_formatted[0]]
    remaining = set(stops_formatted[1:])
    current = stops_formatted[0]
    
    current_date = start_date
    current_time = start_time
    
    stay_times = stay_times or {}
    
    print(f"DEBUG: Optimizing path for {len(stops_formatted)} stops...")
    
    while remaining:
        best_next = None
        min_cost = float('inf')
        best_duration = 0
        
        # Consider stay time at current stop before leaving?
        # No, stay time happens AT the stop. So we add it AFTER arriving.
        # Exception: The FIRST stop, we assume start_time IS the departure time.
        # But for subsequent stops, we arrive, stay, then depart.
        
        # In this loop: We are at 'current'. We want to go to 'cand'.
        # We assume 'current_time' is when we are ready to leave 'current'.
        
        for cand in remaining:
            cost, dur = await get_transit_details(current, cand, date=current_date, time=current_time)
            # print(f"DEBUG: Cost {current} -> {cand} = {cost} (Dur: {dur})")
            
            if cost < min_cost:
                min_cost = cost
                best_next = cand
                best_duration = dur
        
        # Fallback to Haversine if all infinite
        if min_cost == float('inf'):
            print("DEBUG: Infinite costs. Fallback to Haversine.")
            min_dist = float('inf')
            c1 = await get_coordinates(current)
            if c1:
                for cand in remaining:
                    c2 = await get_coordinates(cand)
                    if c2:
                        dist = haversine(c1[0], c1[1], c2[0], c2[1])
                        if dist < min_dist:
                            min_dist = dist
                            best_next = cand
            
            if not best_next:
                best_next = list(remaining)[0]
                
        # Update Timeline
        # 1. Add Travel Time
        current_date, current_time = add_minutes(current_date, current_time, best_duration)
        
        # 2. Add Stay Time at the NEW stop (best_next)
        # (Only if it's not the last stop? Well, we just update the clock. 
        # If we continue from there, we need to have stayed.)
        stay_minutes = stay_times.get(best_next, 0)
        current_date, current_time = add_minutes(current_date, current_time, stay_minutes)
        
        optimized.append(best_next)
        remaining.remove(best_next)
        current = best_next
            
    return optimized
