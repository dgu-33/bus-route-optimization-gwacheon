import json
import time

import networkx as nx
from geopy.distance import geodesic

import api_client
from api_client import get_kakao_path, CACHE_FILE
from data_loader import (
    load_reference_weights, integrate_stop_poi,
    load_json_data, load_bus_stops, load_poi_data
)
from graph import create_city_graph, MIN_ROAD_WIDTH
from algorithm import genetic_algorithm
from scheduling import schedule_buses, calculate_frequencies
from visualization import display_routes, print_route_summary

TARGET_CITY = "Gwacheon"  # 대상 도시: 과천시


def generate_bus_routes(reference_weights, target_city, num_routes, num_buses,
                        bus_stop_json, nodes, link_geo, transfer_stop_ids):
    """버스 노선 생성 및 시각화 메인 함수"""
    print(f"\n1. {target_city}의 교통 네트워크 구축 중...")
    stops = load_bus_stops(bus_stop_json)

    G_road = nx.Graph()
    roads = []

    for i, start_stop in enumerate(stops):
        start_id = str(start_stop["id"])
        G_road.add_node(start_id,
                        pos=(start_stop["lon"], start_stop["lat"]),
                        name=start_stop["name"])

        for j, end_stop in enumerate(stops[i+1:], start=i+1):
            end_id = str(end_stop["id"])

            if not all(isinstance(coord, (int, float)) for coord in [end_stop["lon"], end_stop["lat"]]):
                print(f"경고: 정류장 {end_id}의 좌표가 유효하지 않습니다.")
                continue

            raw_dist_km = geodesic(
                (start_stop["lat"], start_stop["lon"]),
                (end_stop["lat"], end_stop["lon"])
            ).km
            print(f"[{i},{j}]    ▶ 직선 거리 = {raw_dist_km:.3f}km  |  "
                  f"{start_stop['name']} → {end_stop['name']}")

            if raw_dist_km > 1.0:
                continue

            cache_key = f"{start_id}_{end_id}"
            if cache_key in api_client.path_cache:
                cached = api_client.path_cache[cache_key]
                path_coords = cached.get("path_coords")
                distance = cached.get("distance")
            else:
                time.sleep(0.2)
                path_coords, distance = get_kakao_path(
                    start_stop["lon"], start_stop["lat"],
                    end_stop["lon"], end_stop["lat"]
                )
                if path_coords is not None and distance is not None:
                    api_client.path_cache[cache_key] = {
                        "path_coords": path_coords,
                        "distance": distance
                    }
                    with open(CACHE_FILE, "w", encoding="utf-8") as _cf:
                        json.dump(api_client.path_cache, _cf, ensure_ascii=False, indent=2)

            if path_coords and distance > 0:
                G_road.add_edge(start_id, end_id,
                                weight=distance,
                                width=MIN_ROAD_WIDTH)
                roads.append({
                    "id":          f"road_{start_id}_{end_id}",
                    "start":       {"lat": start_stop["lat"], "lon": start_stop["lon"]},
                    "end":         {"lat": end_stop["lat"],   "lon": end_stop["lon"]},
                    "length":      distance,
                    "width":       MIN_ROAD_WIDTH,
                    "path_coords": path_coords
                })

    pois = load_poi_data()
    target_graph = create_city_graph(stops, pois, roads, G_road)

    print(f"\n2. {target_city}에 최적 버스 노선 생성 중...")
    routes = genetic_algorithm(target_graph, reference_weights,
                               num_routes, stops, pois, nodes, link_geo, transfer_stop_ids)

    print(f"\n3. 버스 배차 계획 수립 중...")
    schedule = schedule_buses(routes, target_graph, num_buses)
    frequencies = calculate_frequencies(schedule)

    print_route_summary(routes, target_graph, schedule, frequencies, reference_weights)
    print(f"\n4. 노선도 생성 중...")
    map_html = display_routes(target_graph, routes, schedule, frequencies, roads)

    return routes, schedule, frequencies, map_html


def main():
    print("===== 버스 노선 생성 시스템 =====")
    print(f"대상 도시: {TARGET_CITY}")

    # 1. LLM 가중치 로드
    reference_weights = load_reference_weights("llm_response.txt")

    # 2. 입력 데이터 로드
    bus_stop_json = load_json_data("정류장위치/과천시_버스_정류장_위치.json")
    if not bus_stop_json:
        print("에러: 정류장 위치 파일을 로드하지 못했습니다.")
        return

    poi_data = load_poi_data("bus_stop.csv")
    if not poi_data:
        print("경고: POI 데이터를 로드하지 못했습니다. POI 미반영으로 진행.")

    bus_stop_json = integrate_stop_poi(bus_stop_json, poi_data)

    # 3. 교통 노드/링크/통과노선 데이터 로드
    transfer_data = load_json_data(r"통과노선/정류장별_통과노선.json")
    transfer_stop_ids = []
    if transfer_data:
        transfer_stop_ids = [
            str(item["정류소ID"]) for item in transfer_data
            if item.get("통과노선수", 0) >= 2
        ]

    node_geo = load_json_data(r"교통노드/과천시_교통노드.json")
    nodes = []
    if node_geo:
        nodes = [
            {
                "latitude":  item["geometry"]["coordinates"][1],
                "longitude": item["geometry"]["coordinates"][0],
                "node_type": item["properties"].get("nd_type_h")
            }
            for item in node_geo["response"]["result"]["featureCollection"]["features"]
        ]

    link_geo = load_json_data(r"교통링크/과천시_교통링크.json") or {
        "response": {"result": {"featureCollection": {"features": []}}}
    }

    # 4. 사용자 입력
    num_routes = int(input("생성할 노선 개수를 입력하세요: "))
    num_buses = int(input("운행 가능한 버스 대수를 입력하세요: "))

    # 5. 버스 노선 생성
    routes, schedule, frequencies, map_html = generate_bus_routes(
        reference_weights, TARGET_CITY, num_routes, num_buses,
        bus_stop_json, nodes, link_geo, transfer_stop_ids
    )
    print("\n노선 생성이 완료되었습니다!")
    print(f"지도는 'bus_routes.html' 파일로 저장되었습니다.")


if __name__ == "__main__":
    main()
