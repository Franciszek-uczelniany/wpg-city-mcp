import httpx
import config
from tools import locations, routing
from tools.routing import add_minutes

async def fetch_trip_plan(origin: str, destination: str, mode: str = config.DEFAULT_TRANSIT_MODE, date: str | None = None, time: str | None = None) -> tuple[dict | None, str | None]:
    """
    Internal helper to fetch a trip plan without formatting.
    Returns (plan_dict, error_message).
    """
    formatted_origin = await locations.format_location(origin)
    formatted_dest = await locations.format_location(destination)
    
    if not locations.is_valid_format(formatted_origin):
        return None, f"Error: Could not find/resolve origin: '{origin}'."
    if not locations.is_valid_format(formatted_dest):
        return None, f"Error: Could not find/resolve destination: '{destination}'."

    url = config.TRANSIT_TRIP_PLANNER_URL
    params = {
        "api-key": config.TRANSIT_API_KEY,
        "origin": formatted_origin,
        "destination": formatted_dest,
        "mode": mode or config.DEFAULT_TRANSIT_MODE
    }
    
    if date: params["date"] = date
    if time: params["time"] = time
    
    try:
        headers = {"User-Agent": "WinnipegTransitMCP/1.0"}
        async with httpx.AsyncClient(headers=headers) as client:
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                return None, f"Error planning trip: {response.status_code} - {response.text}"
                
            data = response.json()
            plans = data.get("plans", [])
            if not plans:
                return None, f"No trip plans found from {origin} to {destination}."
            
            return plans[0], None
            
    except Exception as e:
        return None, f"Error planning trip: {str(e)}"

def format_plan_text(plan: dict, origin: str, destination: str) -> str:
    """Format a JSON plan object into a readable string."""
    segments = plan.get("segments", [])
    times = plan.get("times", {})
    durations = times.get("durations", {})
    
    start_time = times.get("start", "Unknown").replace("T", " ")
    
    total_min = durations.get("total", 0)
    walk_min = durations.get("walking", 0)
    wait_min = durations.get("waiting", 0)
    ride_min = durations.get("riding", 0)
    
    result = [
        f"Trip: {origin} -> {destination}",
        f"Date: {start_time}",
        f"Total Duration: {total_min} min",
        f"  - 🚶 Walking: {walk_min} min",
        f"  - ⏳ Waiting: {wait_min} min",
        f"  - 🚌 Riding: {ride_min} min",
        "------------------------------------------------"
    ]
    
    for seg in segments:
        type_ = seg.get("type", "")
        seg_times = seg.get("times", {})
        seg_durations = seg_times.get("durations", {})
        start_seg = seg_times.get("start", "").split("T")[-1][:-3]
        end_seg = seg_times.get("end", "").split("T")[-1][:-3]
        
        if type_ == "walk":
            w_time = seg_durations.get("walking", 0)
            
            # Extract destination info
            to_obj = seg.get("to", {})
            if "stop" in to_obj:
                s = to_obj["stop"]
                to_node = f"{s.get('name', 'Stop')} (#{s.get('key', '')})"
            elif "intersection" in to_obj:
                to_node = to_obj["intersection"].get("name", "Intersection")
            elif "monument" in to_obj:
                to_node = to_obj["monument"].get("name", "Landmark")
            else:
                to_node = "Destination"
                
            result.append(f"  🚶 Walk to {to_node}")
            result.append(f"     (approx {w_time} mins) • {start_seg} - {end_seg}")
            
            # Internal helper for coordinates dict extraction - reused logic
            def get_location_coords_dict(node):
                entities = []
                for key in ['stop', 'intersection', 'monument', 'point']:
                    if key in node: entities.append(node[key])
                for key in ['origin', 'destination']:
                    if key in node:
                        inner = node[key]
                        for subkey in ['point', 'stop', 'intersection', 'monument']:
                            if subkey in inner: entities.append(inner[subkey])
                for entity in entities:
                    if "centre" in entity and "geographic" in entity["centre"]:
                        return entity["centre"]["geographic"]
                return None

            from_geo = get_location_coords_dict(seg.get("from", {}))
            to_geo = get_location_coords_dict(seg.get("to", {}))

            if from_geo and to_geo:
                f_lat, f_lon = from_geo.get("latitude"), from_geo.get("longitude")
                t_lat, t_lon = to_geo.get("latitude"), to_geo.get("longitude")
                
                map_url = f"https://www.google.com/maps/dir/?api=1&origin={f_lat},{f_lon}&destination={t_lat},{t_lon}&travelmode=walking"
                result.append(f"     🗺️ Map: {map_url}")
            
        elif type_ == "ride":
            r_time = seg_durations.get("riding", 0)
            route = seg.get("route", {})
            r_name = route.get("name", "Bus")
            r_num = route.get("key", "")
            variant = seg.get("variant", {}).get("name", "")
            
            from_obj = seg.get("from", {})
            to_obj = seg.get("to", {})
            
            board_at = "Unknown Stop"
            if "stop" in from_obj:
                s = from_obj["stop"]
                board_at = f"{s.get('name')} (#{s.get('key')})"
                
            alight_at = "Unknown Stop"
            if "stop" in to_obj:
                s = to_obj["stop"]
                alight_at = f"{s.get('name')} (#{s.get('key')})"

            result.append(f"  🚌 Ride {r_num} {r_name} ({variant})")
            result.append(f"     Board at: {board_at}")
            result.append(f"     Get off at: {alight_at}")
            result.append(f"     ({r_time} mins) • {start_seg} - {end_seg}")
            
        elif type_ == "transfer":
            result.append(f"  🔄 Transfer")
            
    return "\n".join(result)

async def plan_trip(origin: str, destination: str, mode: str = config.DEFAULT_TRANSIT_MODE, date: str | None = None, time: str | None = None) -> str:
    """
    Plan a trip between two points using Winnipeg Transit.
    
    Arguments 'origin' and 'destination' can be:
    - Plain text addresses or landmarks (e.g. "The Forks", "IKEA", "123 Main St") - Resolved via OSM
    - Stop numbers (e.g. "10625", "Stop 10541")
    - Formatted keys:
        - "stops/{key}"
        - "geo/{lat},{lon}"
        - "intersection/{key}"
    """
    plan, error = await fetch_trip_plan(origin, destination, mode, date, time)
    if error:
        return error
    
    return format_plan_text(plan, origin, destination)

async def plan_journey(stops: list[str], optimize: bool = False, date: str | None = None, time: str | None = None) -> str:
    """
    Plan a multi-stop journey (A -> B -> C ...).
    
    Args:
        stops: List of locations (plain text, stop numbers, or formatted keys)
        optimize: If True, optimized the visit order (TSP) starting from the first stop.
        date: Optional start date (YYYY-MM-DD or equivalent accepted by API).
        time: Optional start time (HH:MM).
    """
    if len(stops) < 2:
        return "Error: Need at least 2 stops to plan a journey."
    
    resolved_map = {} # formatted -> original
    formatted_stops = []
    
    for s in stops:
        fmt = await locations.format_location(s)
        formatted_stops.append(fmt)
        if fmt not in resolved_map:
            resolved_map[fmt] = s
            
    if optimize:
        formatted_stops = await routing.optimize_stop_order_greedy(formatted_stops, start_date=date, start_time=time)
        
    results = []
    if optimize:
        results.append(f"ℹ️ Route Optimization Enabled. New Order: {' -> '.join([resolved_map.get(f, f) for f in formatted_stops])}\n")
    
    # Simple iteration for standard journey
    for i in range(len(formatted_stops) - 1):
        origin = formatted_stops[i]
        dest = formatted_stops[i+1]
        
        origin_label = resolved_map.get(origin, origin)
        dest_label = resolved_map.get(dest, dest)
        
        leg_result = await plan_trip(origin, dest, date=date, time=time)
        results.append(f"--- Leg {i+1}: {origin_label} to {dest_label} ---\n{leg_result}")
        
    return "\n\n".join(results)

async def plan_timed_itinerary(
    stops_config: list[dict],
    start_date: str | None = None,
    start_time: str | None = None
) -> str:
    """
    Plan an optimized itinerary with specific stay durations at each stop.

    Args:
        stops_config: List of dictionaries. The first stop is the origin.
            Each item format: {"location": "...", "min_stay": minutes, "max_stay": minutes}
            (Stay times for the LAST stop are ignored).
        start_date: YYYY-MM-DD
        start_time: HH:MM
    """
    if len(stops_config) < 2:
        return "Error: Need at least 2 stops."

    # 1. Resolve Locations
    resolved_map = {}
    formatted_list = []
    stay_times = {} # formatted -> min_stay
    
    print(f"DEBUG: Planning timed itinerary for {len(stops_config)} stops")

    for item in stops_config:
        raw_loc = item.get("location", "")
        min_stay = int(item.get("min_stay", 0))
        
        fmt = await locations.format_location(raw_loc)
        formatted_list.append(fmt)
        stay_times[fmt] = min_stay
        
        if fmt not in resolved_map:
            resolved_map[fmt] = raw_loc

    # 2. Optimize
    # This logic pushes timestamps forward based on travel + stay
    optimized_stops = await routing.optimize_stop_order_greedy(
        formatted_list, 
        start_date=start_date, 
        start_time=start_time,
        stay_times=stay_times
    )
    
    results = []
    results.append(f"ℹ️ Optimized & Timed Itinerary\n")
    results.append(f"Start Time: {start_date or ''} {start_time or ''}\n")
    
    # 3. Execution Loop with Time Tracking
    curr_date = start_date
    curr_time = start_time
    
    for i in range(len(optimized_stops) - 1):
        origin = optimized_stops[i]
        dest = optimized_stops[i+1]
        
        origin_label = resolved_map.get(origin, origin)
        dest_label = resolved_map.get(dest, dest)
        
        results.append(f"📍 Leg {i+1}: {origin_label} -> {dest_label}")
        results.append(f"   Departing around: {curr_time or 'ASAP'}")
        
        # Plan trip
        plan, err = await fetch_trip_plan(origin, dest, date=curr_date, time=curr_time)
        
        if err or not plan:
            results.append(f"   ❌ Error: {err or 'No plan found'}")
            break
            
        # Format textual output
        text = format_plan_text(plan, origin_label, dest_label)
        results.append(text)
        
        # Calculate Arrival
        times = plan.get("times", {})
        end_time_str = times.get("end", "").split("T")[-1][:-3] # HH:MM:SS -> HH:MM
        
        # We try to use the exact arrival time from the plan
        if end_time_str:
            curr_time = end_time_str 
        else:
            # Fallback
            dur_min = times.get("durations", {}).get("total", 0)
            curr_date, curr_time = add_minutes(curr_date, curr_time, dur_min)
            
        results.append(f"   🏁 Arrived at {dest_label} at {curr_time}")
        
        # Add Stay Duration
        if i < len(optimized_stops) - 1: # If not the absolute last item? 
            # optimized_stops[i+1] is 'dest'.
            # If 'dest' is NOT the last stop in the list, we stay.
            # Even if it IS the last stop, the user might want to stay there (end of trip),
            # but usually itineraries end at arrival.
            if i < len(optimized_stops) - 2:
                stay_min = stay_times.get(dest, 0)
                if stay_min > 0:
                    curr_date, leave_time = add_minutes(curr_date, curr_time, stay_min)
                    results.append(f"   ⏳ Staying for {stay_min} mins... (Departing {leave_time})")
                    curr_time = leave_time
            else:
                results.append(f"   🎉 End of Trip")
                
        results.append("")
        
    return "\n".join(results)
