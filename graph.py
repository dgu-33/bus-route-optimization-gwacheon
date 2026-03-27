from collections import Counter

import networkx as nx
import numpy as np
from geopy.distance import geodesic
from sklearn.cluster import KMeans

MIN_ROAD_WIDTH = 6  # 최소 도로 폭 (미터)


def label_nodes(pois, stops, k=3):
    """POI와 정류장 데이터를 사용해 정류장에 지역 유형 레이블 부여"""
    if not pois or len(pois) < k:
        k = max(2, len(pois)) if pois else 2

    poi_coords = np.array([[poi["lat"], poi["lon"]] for poi in pois]) if pois else np.array([[stop["lat"], stop["lon"]] for stop in stops])
    poi_types = [poi["type"] for poi in pois] if pois else ["unknown"] * len(stops)

    kmeans = KMeans(n_clusters=k, random_state=0).fit(poi_coords)

    cluster_types = {}
    for i in range(k):
        cluster_pois = [poi_types[j] for j in range(len(poi_types)) if kmeans.labels_[j] == i]
        most_common = Counter(cluster_pois).most_common(1)
        cluster_types[i] = most_common[0][0] if most_common else "기타"

    label_mapping = {
        "학교": "교육지구",
        "어린이집": "교육지구",
        "학원": "교육지구",
        "병원": "의료지구",
        "약국": "의료지구",
        "음식점": "상업지구",
        "카페": "상업지구",
        "대형마트": "상업지구",
        "편의점": "상업지구",
        "문화시설": "여가지구",
        "관광명소": "여가지구",
        "공공기관": "업무지구",
        "은행": "업무지구",
        "지하철역": "교통중심지",
    }

    for i in cluster_types:
        if cluster_types[i] in label_mapping:
            cluster_types[i] = label_mapping[cluster_types[i]]

    stop_labels = {}
    for stop in stops:
        nearby_pois = [i for i, poi in enumerate(pois)
                       if geodesic((stop["lat"], stop["lon"]), (poi["lat"], poi["lon"])).km <= 0.3] if pois else []
        if nearby_pois:
            cluster = Counter(kmeans.labels_[nearby_pois]).most_common(1)[0][0]
            stop_labels[stop["id"]] = cluster_types[cluster]
        else:
            stop_labels[stop["id"]] = "기타"

    return stop_labels


def create_city_graph(stops, pois, roads, road_graph):
    """정류장, POI, 도로 데이터를 사용해 도시 그래프 생성"""
    G = nx.Graph()
    # Expand per-stop poi_counts into individual typed POI records for clustering
    poi_records = [
        {"lat": p["lat"], "lon": p["lon"], "type": poi_type}
        for p in pois
        for poi_type, count in p.get("poi_counts", {}).items()
        if count and count > 0
    ]
    stop_labels = label_nodes(poi_records, stops)

    for stop in stops:
        if not all(isinstance(coord, (int, float)) for coord in [stop["lon"], stop["lat"]]):
            print(f"경고: 정류장 {stop['id']}의 좌표가 유효하지 않습니다: ({stop['lon']}, {stop['lat']})")
            continue

        G.add_node(stop["id"],
                   pos=(stop["lon"], stop["lat"]),
                   name=stop["name"],
                   label=stop_labels[stop["id"]],
                   passengers=stop.get("passengers", 0),
                   population=stop.get("population", 0),
                   poi_counts=stop.get("poi_counts", {}))

    for u, v, data in road_graph.edges(data=True):
        if u not in G.nodes or v not in G.nodes:
            print(f"경고: 엣지 ({u}, {v})가 존재하지 않는 노드를 참조합니다.")
            continue
        G.add_edge(u, v, weight=data["weight"], width=data.get("width", MIN_ROAD_WIDTH))

    print(f"그래프 노드 수: {G.number_of_nodes()}, 엣지 수: {G.number_of_edges()}")
    isolated = list(nx.isolates(G))
    if isolated:
        print(f"연결되지 않은 노드: {isolated}")

    return G
