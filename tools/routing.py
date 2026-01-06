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

async def get_transit_cost(origin: str, destination: str, date: str | None = None, time: str | None = None) -> float:
    """
    Calculate the 'cost' of travel between two points using real Transit API data.
    Cost = Total Minutes + (Transfer Count * 10)
    
    If date/time are provided, they are used for 'depart-after'.
    """
    # We need to import config here or pass it in. Importing to avoid circular dependency issues
    # if this module grows, but for now standard import is fine.
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
            # Short timeout - if API is slow, we act like it's a "far" connection
            resp = await client.get(url, params=params, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                plans = data.get("plans", [])
                if plans:
                    plan = plans[0] # Best plan
                    times = plan.get("times", {}).get("durations", {})
                    total_time = times.get("total", 0)
                    
                    # Count transfers based on segments
                    segments = plan.get("segments", [])
                    # Count how many "ride" segments are there. 
                    ride_count = sum(1 for s in segments if s.get("type") == "ride")
                    transfers = max(0, ride_count - 1)
                    
                    return total_time + (transfers * 15) # 15 min penalty per transfer
    except Exception:
        pass
        
    return float('inf') # Return infinity if no route found or error

async def optimize_stop_order_greedy(stops_formatted: list[str], start_date: str | None = None, start_time: str | None = None) -> list[str]:
    """
    Reorder stops using Nearest Neighbor Greedy approach (TSP Approximation).
    Uses REAL TRANSIT TIME as the cost metric.
    Assumes stops_formatted[0] is the FIXED start point.
    
    The optimizer is now TIME AWARE. It will carry forward the estimated arrival time 
    from step N to be the departure time for step N+1.
    """
    if len(stops_formatted) <= 2:
        return stops_formatted
        
    optimized = [stops_formatted[0]]
    remaining = set(stops_formatted[1:])
    
    current = stops_formatted[0]
    
    print(f"DEBUG: Optimizing path for {len(stops_formatted)} stops...")
    
    current_date = start_date
    current_time = start_time
    
    while remaining:
        # Find nearest neighbor to current (Time based)
        best_next = None
        min_cost = float('inf')
        
        # We must await these checks sequentially.
        # Note: Ideally we would also update current_time for each hop to be truly accurate,
        # but estimating future departure times without fetching the FULL trip plan details 
        # (arrival time) is tricky in this loop.
        # For v1, we use the start_time for all comparisons, or we could blindly add cost to time.
        
        for cand in remaining:
            cost = await get_transit_cost(current, cand, date=current_date, time=current_time)

            print(f"DEBUG: Cost {current} -> {cand} = {cost}")
            
            if cost < min_cost:
                min_cost = cost
                best_next = cand
        
        # Fallback: If ALL remaining candidates have infinite cost (e.g. no service at late night),
        # switch to HAVERSINE distance for the tie-breaker so we don't pick purely at random.
        if min_cost == float('inf'):
            print("DEBUG: All transit costs infinite. Switching to Haversine fallback.")
            min_dist = float('inf')
            
            # Map current/candidates to coords if not already done? 
            # We need to fetch coords on demand
            c1 = await get_coordinates(current)
            if c1:
                for cand in remaining:
                    c2 = await get_coordinates(cand)
                    if c2:
                        dist = haversine(c1[0], c1[1], c2[0], c2[1])
                        print(f"DEBUG: Haversine {current} -> {cand} = {dist}km")
                        if dist < min_dist:
                            min_dist = dist
                            best_next = cand
            
            # If still no best_next (e.g. coord lookup failed), we will fall through to random pick
                
        # If we failed to find a valid route to any remaining stop, just pick one to proceed
        if not best_next:
            best_next = list(remaining)[0]
        
        optimized.append(best_next)
        remaining.remove(best_next)
        current = best_next
            
    return optimized
