import json
from collections import Counter

import networkx as nx
import numpy as np

from api_client import KAKAO_JS_API_KEY
from pathfinding import astar_path


def display_routes(G, routes, schedule, frequencies, roads_data, kakao_api_key=None):
    """노선과 정류장을 Kakao Map에 시각화하여 HTML 파일로 저장"""
    pos = nx.get_node_attributes(G, "pos")
    lats = [G.nodes[node]["pos"][1] for node in G.nodes() if "stop" in node]
    lons = [G.nodes[node]["pos"][0] for node in G.nodes() if "stop" in node]
    center_lat = sum(lats) / len(lats) if lats else 37.43
    center_lon = sum(lons) / len(lons) if lons else 126.99

    route_colors = ['#FF0000', '#0000FF', '#008000', '#800080', '#FFA500', '#8B0000', '#00008B', '#006400', '#5F9EA0', '#9932CC']
    map_data = {
        "center": {"lat": center_lat, "lng": center_lon},
        "zoom": 14,
        "stops": [],
        "routes": []
    }

    # 정류장 데이터 추가
    for node in G.nodes():
        if "stop" not in node:
            continue
        lon, lat = pos[node]
        name = G.nodes[node].get("name", node)
        label = G.nodes[node].get("label", "기타")
        passengers = G.nodes[node].get("passengers", 0)
        color_map = {
            "상업지구": "red",
            "주거지역": "blue",
            "교육지구": "green",
            "업무지구": "purple",
            "여가지구": "orange",
            "교통중심지": "black",
            "기타": "gray"
        }
        icon_color = color_map.get(label, "gray")
        map_data["stops"].append({
            "id": node,
            "name": name,
            "lat": lat,
            "lng": lon,
            "label": label,
            "passengers": passengers,
            "color": icon_color
        })

    # 노선 데이터 추가
    for i, route in enumerate(routes):
        route_id = i
        route_color = route_colors[i % len(route_colors)]
        frequency = frequencies.get(route_id, 0)
        route_coords = []
        for j in range(len(route) - 1):
            start = route[j]
            end = route[j + 1]
            road = next((r for r in roads_data if r["id"] == f"road_{start}_{end}"), None)
            if road and road.get("path_coords"):
                route_coords.extend(road["path_coords"])
        map_data["routes"].append({
            "route_id": route_id + 1,
            "coordinates": route_coords,
            "color": route_color,
            "frequency": frequency
        })

    # HTML 템플릿
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Bus Routes Map</title>
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_API_KEY}"></script>
        <style>
            #map {{ width: 100%; height: 800px; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var mapContainer = document.getElementById('map');
            var mapOption = {{
                center: new kakao.maps.LatLng({center_lat}, {center_lng}),
                level: {zoom}
            }};
            var map = new kakao.maps.Map(mapContainer, mapOption);

            var stops = {stops_json};
            stops.forEach(function(stop) {{
                var markerPosition = new kakao.maps.LatLng(stop.lat, stop.lng);
                var marker = new kakao.maps.Marker({{
                    position: markerPosition,
                    title: stop.name + ' (' + stop.label + ')\\n승객: ' + stop.passengers + '/일'
                }});
                marker.setMap(map);
            }});

            var routes = {routes_json};
            routes.forEach(function(route) {{
                var path = route.coordinates.map(function(coord) {{
                    return new kakao.maps.LatLng(coord[0], coord[1]);
                }});
                var polyline = new kakao.maps.Polyline({{
                    path: path,
                    strokeWeight: 4,
                    strokeColor: route.color,
                    strokeOpacity: 0.8,
                    strokeStyle: 'solid'
                }});
                polyline.setMap(map);

                var infowindow = new kakao.maps.InfoWindow({{
                    content: '노선 ' + route.route_id + ' (배차간격: ' + route.frequency + '분)'
                }});
                kakao.maps.event.addListener(polyline, 'mouseover', function() {{
                    infowindow.open(map, polyline);
                }});
                kakao.maps.event.addListener(polyline, 'mouseout', function() {{
                    infowindow.close();
                }});
            }});
        </script>
    </body>
    </html>
    """

    # HTML 파일 생성
    html_content = html_content.format(
        KAKAO_API_KEY=kakao_api_key or KAKAO_JS_API_KEY,
        center_lat=center_lat,
        center_lng=center_lon,
        zoom=map_data["zoom"],
        stops_json=json.dumps(map_data["stops"]),
        routes_json=json.dumps(map_data["routes"])
    )

    output_file = f"bus_routes.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"지도는 '{output_file}' 파일로 저장되었습니다.")
    return html_content


def calculate_route_characteristics(routes, G):
    """노선의 주요 특성(길이, 정류장 수, 지역 유형 등) 계산"""
    characteristics = []
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
        stop_count = len(route)
        area_types = Counter([G.nodes[stop]["label"] for stop in route])
        passengers = sum(G.nodes[stop]["passengers"] for stop in route)
        avg_passengers = passengers / stop_count if stop_count > 0 else 0
        avg_distance = length / (stop_count - 1) if stop_count > 1 else 0
        characteristics.append({
            "route_id": i,
            "stops": [G.nodes[stop].get("name", stop) for stop in route],
            "length": length,
            "stop_count": stop_count,
            "area_types": dict(area_types),
            "total_passengers": passengers,
            "avg_passengers": avg_passengers,
            "avg_distance": avg_distance
        })
    return characteristics


def print_route_summary(routes, G, schedule, frequencies, reference_weights=None):
    """생성된 노선과 배차 계획 요약 출력"""
    print("\n=== 버스 노선 요약 ===")
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
        stops = [G.nodes[stop].get("name", stop) for stop in route]
        print(f"\n노선 {i+1}:")
        print(f"  - 정류장 ({len(route)}개): {' -> '.join(stops)}")
        print(f"  - 총 길이: {length:.2f} km")
        print(f"  - 예상 이용객: {passengers}/일")
        print(f"  - 배차 간격: {frequencies.get(i, 0)}분")

    print("\n=== 버스 배차 요약 ===")
    for bus, routes_info in schedule.items():
        if not routes_info:
            continue
        print(f"\n{bus}:")
        for route_info in routes_info:
            route_id = route_info["route_id"]
            print(f"  - 노선 {route_id+1} (배차간격: {frequencies.get(route_id, 0)}분)")

    if reference_weights:
        print("\n=== 참조 가중치와 생성된 노선 비교 ===")
        generated_lengths = []
        generated_stop_counts = []
        generated_avg_distance = []
        generated_passengers = []
        area_type_counts = Counter()
        for route in routes:
            if len(route) < 2:
                continue
            length = 0
            for j in range(len(route) - 1):
                path = astar_path(G, route[j], route[j + 1])
                if path and len(path) > 1:
                    path_length = sum(G[path[k]][path[k + 1]]["weight"] for k in range(len(path) - 1))
                    length += path_length
            if length == 0:
                continue
            generated_lengths.append(length)
            generated_stop_counts.append(len(route))
            avg_distance = length / (len(route) - 1) if len(route) > 1 else 0
            generated_avg_distance.append(avg_distance)
            route_passengers = sum(G.nodes[stop]["passengers"] for stop in route) / len(route)
            generated_passengers.append(route_passengers)
            for stop in route:
                area_type_counts[G.nodes[stop]["label"]] += 1

        if generated_lengths:
            print(f"노선 평균 길이: {np.mean(generated_lengths):.2f} km (참조: {reference_weights.get('avg_length', 5.0):.2f} km)")
            print(f"노선 평균 정류장 수: {np.mean(generated_stop_counts):.2f} (참조: {reference_weights.get('avg_stop_count', 12.0):.2f})")
            print(f"정류장 간 평균 거리: {np.mean(generated_avg_distance):.2f} km (참조: {reference_weights.get('avg_distance', 0.7):.2f} km)")
            print(f"정류장 평균 이용객 수: {np.mean(generated_passengers):.2f}/일 (참조: {reference_weights.get('avg_passengers', 200.0):.2f}/일)")
            print("\n지역 유형 분포:")
            total_stops = sum(area_type_counts.values())
            for area_type, count in area_type_counts.most_common():
                generated_ratio = count / total_stops
                reference_ratio = reference_weights.get("area_type_distribution", {}).get(area_type, 0)
                print(f"  - {area_type}: {generated_ratio:.2%} (참조: {reference_ratio:.2%})")
