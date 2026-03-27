from heapq import heappush, heappop

from geopy.distance import geodesic

from graph import MIN_ROAD_WIDTH


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
