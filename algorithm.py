import random

import numpy as np
from geopy.distance import geodesic

from function_1_to_5 import route_length, stop_distance, poi_score, subway_distance
from function_6_to_10 import (
    normalize_stop_count, node_alignment_scores,
    balanced_length_score, duplication_penalty_score, compute_transfer_score
)
from graph import astar_path


def fitness(route, G, reference_weights, stops_data, pois_data, nodes_data, link_data, transfer_ids):
    """노선의 적합도를 F1~F10의 가중 합으로 계산"""
    if len(route) < 2:
        return 0

    # (1) F1 ~ F2: 경로 길이, 정류장 간 거리 계산
    length = 0
    paths = []
    for i in range(len(route) - 1):
        path = astar_path(G, route[i], route[i + 1])
        if path and len(path) > 1:
            path_length = sum(G[path[j]][path[j + 1]]["weight"] for j in range(len(path) - 1))
            length += path_length
            paths.append(path)
        else:
            return 0  # 유효한 경로가 아니면 적합도 0

    # F1: route_length
    L_i = reference_weights.get("avg_length", 5.0)
    L_max = reference_weights.get("max_length", 7.5)
    f1 = route_length(length, L_i, L_max)

    # F2: stop_distance (직선 거리 기준)
    stop_coords = [(G.nodes[stop]["pos"][1], G.nodes[stop]["pos"][0]) for stop in route]
    distances = [
        geodesic((stop_coords[i][0], stop_coords[i][1]), (stop_coords[i+1][0], stop_coords[i+1][1])).km
        for i in range(len(stop_coords) - 1)
    ]
    D_ideal = reference_weights.get("avg_distance", 0.7)
    sigma = reference_weights.get("sigma", 0.2)
    f2 = stop_distance(distances, D_ideal, sigma)

    # F3: poi_score (정류장별 poi_counts 사용)
    poi_list = []
    weight_dict = reference_weights.get("poi_weights", {
        "학교": 0.3, "병원": 0.3, "음식점": 0.2, "카페": 0.2,
        "편의점": 0.15, "공공기관": 0.25, "지하철역": 0.4, "문화시설": 0.1
    })

    for stop in route:
        counts = G.nodes[stop].get("poi_counts", {})
        for poi_type, cnt in counts.items():
            if cnt and cnt > 0:
                poi_list.append({"type": poi_type, "count": cnt})

    f3 = poi_score(poi_list, weight_dict) if poi_list else 0

    # F4: subway_distance
    subway_nodes = [n for n in nodes_data if n.get("node_type") == "subway"]
    subway_dists = []
    for stop in route:
        lat, lon = G.nodes[stop]["pos"][1], G.nodes[stop]["pos"][0]
        dists = [geodesic((lat, lon), (n["latitude"], n["longitude"])).meters for n in subway_nodes]
        if dists:
            subway_dists.append(min(dists))
    D_scale = reference_weights.get("D_scale", 1000)
    f4 = subway_distance(subway_dists, D_scale) if subway_dists else 0

    # F5: 유동인구 (데이터 없음 → 0)
    f5 = 0

    # F6: normalize_stop_count
    N_ideal = reference_weights.get("avg_stop_count", 12)
    N_max = reference_weights.get("max_stop_deviation", 5)
    f6 = normalize_stop_count(len(route), N_ideal, N_max)

    # F7, F8: node_alignment_scores
    stops_coords = [(G.nodes[stop]["pos"][1], G.nodes[stop]["pos"][0]) for stop in route]
    f7, f8 = node_alignment_scores(stops_coords, nodes_data, node_type="subway", radius=50, scale=100)

    # F9: balanced_length_score (도로 링크 정보 활용)
    link_lengths = []
    if isinstance(link_data, list):
        features = link_data
    else:
        features = link_data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])

    for feat in features:
        if "geometry" not in feat or "coordinates" not in feat["geometry"]:
            continue
        coords = feat["geometry"]["coordinates"]
        if len(coords) >= 2:
            length_m = sum(geodesic(coords[i], coords[i + 1]).meters for i in range(len(coords) - 1))
            link_lengths.append(length_m)

    L_ideal = reference_weights.get("L_ideal", 200)
    L_max = reference_weights.get("L_max", 300)
    f9 = np.mean([balanced_length_score(l, L_ideal, L_max) for l in link_lengths]) if link_lengths else 0

    # F10: compute_transfer_score
    route_stop_ids = [stop for stop in route if "stop" in stop]
    f10 = compute_transfer_score(route_stop_ids, transfer_ids)

    # 가중 합
    weights = reference_weights.get("fitness_weights", {
        "w1": 0.100, "w2": 0.100, "w3": 0.150, "w4": 0.100, "w5": 0.050,
        "w6": 0.100, "w7": 0.050, "w8": 0.150, "w9": 0.100, "w10": 0.100
    })
    fitness_score = (
        weights["w1"] * f1 +
        weights["w2"] * f2 +
        weights["w3"] * f3 +
        weights["w4"] * f4 +
        weights["w5"] * f5 +
        weights["w6"] * f6 +
        weights["w7"] * f7 +
        weights["w8"] * f8 +
        weights["w9"] * f9 +
        weights["w10"] * f10
    )

    return max(0, fitness_score)


def genetic_algorithm(G, reference_weights, num_routes, stops_data, pois_data, nodes_data, link_data, transfer_ids, population_size=50, generations=100):
    """유전 알고리즘으로 최적 버스 노선 생성"""
    all_stops = [n for n in G.nodes() if isinstance(n, str) and "stop" in n]
    if len(all_stops) < 3:
        print("에러: 그래프에 정류장이 충분하지 않습니다.")
        return []

    # 승객 수가 가장 많은 정류장을 허브로 선택
    hub = max(all_stops, key=lambda x: G.nodes[x]["passengers"])
    target_stop_count = int(reference_weights.get("avg_stop_count", 12))

    # 초기 노선 집합 생성
    population = []
    for _ in range(population_size):
        route = [hub]
        remaining = set(all_stops) - {hub}
        attempts = 0
        max_attempts = len(all_stops) * 3
        while len(route) < target_stop_count and remaining and attempts < max_attempts:
            candidates = list(remaining)
            random.shuffle(candidates)
            for next_stop in candidates:
                path = astar_path(G, route[-1], next_stop)
                if path and len(path) > 1:
                    for stop in path[1:]:
                        if stop not in route and "stop" in stop:
                            route.append(stop)
                            if stop in remaining:
                                remaining.remove(stop)
                    break
            else:
                if candidates:
                    remaining.remove(candidates[0])
            attempts += 1
        if len(route) >= 3:
            population.append(list(dict.fromkeys(route)))

    if not population:
        print("에러: 유효한 초기 노선을 생성하지 못했습니다.")
        return []

    # 유전 알고리즘 반복
    for gen in range(generations):
        scored_population = [(route, fitness(route, G, reference_weights, stops_data, pois_data, nodes_data, link_data, transfer_ids)) for route in population]
        scored_population.sort(key=lambda x: x[1], reverse=True)
        selection_size = population_size // 2
        fitness_values = [max(0, score) for _, score in scored_population]
        if sum(fitness_values) == 0:
            selected = random.choices([route for route, _ in scored_population], k=selection_size)
        else:
            selected = random.choices(
                [route for route, _ in scored_population],
                weights=fitness_values,
                k=selection_size
            )
        new_population = list(selected)

        # 교차 및 돌연변이
        while len(new_population) < population_size:
            parent1, parent2 = random.sample(selected, 2)
            child = parent1.copy()
            if len(parent1) > 2 and len(parent2) > 2:
                crossover_point = random.randint(1, min(len(parent1), len(parent2))-1)
                child = parent1[:crossover_point]
                child.extend([s for s in parent2 if s not in child])

            if random.random() < 0.1 and len(child) > 0 and len(all_stops) > len(child):
                mutation_idx = random.randint(0, len(child)-1)
                new_stop = random.choice(list(set(all_stops) - set(child)))
                if mutation_idx > 0 and mutation_idx < len(child) - 1:
                    prev_stop = child[mutation_idx - 1]
                    next_stop = child[mutation_idx + 1]
                    path1 = astar_path(G, prev_stop, new_stop)
                    path2 = astar_path(G, new_stop, next_stop)
                    if path1 and path2:
                        child[mutation_idx] = new_stop
                elif mutation_idx == 0:
                    next_stop = child[mutation_idx + 1]
                    if astar_path(G, new_stop, next_stop):
                        child[mutation_idx] = new_stop
                elif mutation_idx == len(child) - 1:
                    prev_stop = child[mutation_idx - 1]
                    if astar_path(G, prev_stop, new_stop):
                        child[mutation_idx] = new_stop

            # 유효한 경로 검증
            valid_route = [child[0]]
            for i in range(1, len(child)):
                path = astar_path(G, valid_route[-1], child[i])
                if path:
                    for stop in path[1:]:
                        if stop not in valid_route and "stop" in stop:
                            valid_route.append(stop)
            if len(valid_route) >= 3:
                if len(valid_route) > target_stop_count:
                    valid_route = valid_route[:target_stop_count]
                new_population.append(valid_route)

        population = new_population
        if (gen + 1) % 10 == 0:
            best_score = scored_population[0][1]
            avg_score = np.mean([score for _, score in scored_population])
            print(f"세대 {gen+1}/{generations}: 최고 점수 = {best_score:.2f}, 평균 점수 = {avg_score:.2f}")

    # 최종 노선 선택
    final_scored_population = [(route, fitness(route, G, reference_weights, stops_data, pois_data, nodes_data, link_data, transfer_ids)) for route in population]
    final_scored_population.sort(key=lambda x: x[1], reverse=True)
    return [route for route, _ in final_scored_population[:num_routes]]
