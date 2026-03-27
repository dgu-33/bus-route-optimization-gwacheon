from pathfinding import astar_path


def schedule_buses(routes, G, num_buses):
    """노선을 버스에 배정하여 스케줄 생성"""
    route_stats = []
    for i, route in enumerate(routes):
        if len(route) < 2:
            continue
        length = 0
        for j in range(len(route) - 1):
            path = astar_path(G, route[j], route[j + 1])
            if path and len(path) > 1:
                path_length = sum(G[path[k]][path[k + 1]]["weight"] for k in range(len(path) - 1))
                length += path_length
            else:
                continue
        passengers = sum(G.nodes[stop]["passengers"] for stop in route)
        round_trip_time = (length * 2) / 30 * 60  # 왕복 시간 (분, 평균 속도 30km/h)
        route_stats.append({
            "route_id": i,
            "route": route,
            "length": length,
            "passengers": passengers,
            "round_trip_time": round_trip_time
        })

    # 노선을 왕복 시간 기준으로 정렬
    route_stats.sort(key=lambda x: x["round_trip_time"], reverse=True)
    schedule = {f"Bus {i+1}": [] for i in range(num_buses)}
    # 노선을 버스에 균등 배정
    for route_info in route_stats:
        bus_times = {bus: sum(r["round_trip_time"] for r in schedule[bus]) for bus in schedule}
        target_bus = min(bus_times, key=bus_times.get)
        schedule[target_bus].append(route_info)
    return schedule


def calculate_frequencies(schedule):
    """각 노선의 배차 간격 계산"""
    frequencies = {}
    for bus, routes in schedule.items():
        for route_info in routes:
            route_id = route_info["route_id"]
            bus_count = sum(1 for b, rs in schedule.items() for r in rs if r["route_id"] == route_id)
            frequency = max(5, min(60, route_info["round_trip_time"] / bus_count))
            frequencies[route_id] = round(frequency)
    return frequencies
