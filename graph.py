from collections import Counter
from heapq import heappush, heappop

import networkx as nx
import numpy as np
from geopy.distance import geodesic
from sklearn.cluster import KMeans

MIN_ROAD_WIDTH = 6  # 최소 도로 폭 (미터)


def astar_path(G, start, goal, constraints=None):
    """A* 알고리즘으로 최단 경로 탐색"""
    if constraints is None:
        constraints = {"min_width": MIN_ROAD_WIDTH}

    def heuristic(node1, node2, G):
        """두 노드 간 직선 거리(지오데식 거리) 계산"""
        try:
            if node1 not in G.nodes or node2 not in G.nodes:
                raise ValueError(f"노드 {node1} 또는 {node2}가 그래프에 없습니다.")
            pos1 = G.nodes[node1].get("pos")
            pos2 = G.nodes[node2].get("pos")
            if pos1 is None or pos2 is None:
                raise ValueError(f"노드 {node1} 또는 {node2}에 'pos' 속성이 없습니다.")
            lon1, lat1 = pos1
            lon2, lat2 = pos2
            if not all(isinstance(coord, (int, float)) for coord in [lon1, lat1, lon2, lat2]):
                raise ValueError(f"노드 {node1} ({pos1}) 또는 {node2} ({pos2})의 좌표가 유효하지 않습니다.")
            return geodesic((lat1, lon1), (lat2, lon2)).km
        except Exception as e:
            print(f"heuristic 계산 중 에러 (노드 {node1}, {node2}): {e}")
            return float('inf')

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal, G)}

    while open_set:
        current_f, current = heappop(open_set)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]

        for neighbor in G.neighbors(current):
            edge_data = G[current][neighbor]
            if edge_data.get("width", MIN_ROAD_WIDTH) < constraints.get("min_width", 0):
                continue

            tentative_g_score = g_score[current] + edge_data["weight"]

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal, G)
                heappush(open_set, (f_score[neighbor], neighbor))

    print(f"{start}에서 {goal}로 가는 경로를 찾을 수 없습니다.")
    return None


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
        "school": "교육지구",
        "hospital": "의료지구",
        "restaurant": "상업지구",
        "cafe": "상업지구",
        "shop": "상업지구",
        "park": "여가지구",
        "residential": "주거지역",
        "office": "업무지구"
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
    stop_labels = label_nodes([], stops)

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
