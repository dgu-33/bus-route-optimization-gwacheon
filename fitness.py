import math

import numpy as np
from geopy.distance import geodesic


# ---------------------------------------------------------------------------
# F1 – F4: Route-level scoring functions
# ---------------------------------------------------------------------------

def route_length(L, L_i, L_max):
    score = 1 - ((L - L_i) / L_max) ** 2
    return max(0, score)


def stop_distance(D_list, D_ideal, sigma):
    if len(D_list) < 2:
        return 0
    scores = [math.exp(-((d - D_ideal) ** 2) / (2 * sigma ** 2)) for d in D_list]
    return sum(scores) / len(D_list)


def poi_score(poi_list, weight_dict):
    total_weighted = 0
    total_count = 0
    for poi in poi_list:
        weight = weight_dict.get(poi['type'], 0)
        total_weighted += weight * poi['count']
        total_count += 1
    return total_weighted / total_count if total_count > 0 else 0


def subway_distance(subway_dists, D_scale):
    if not subway_dists:
        return 0
    scores = [math.exp(-d / D_scale) for d in subway_dists]
    return sum(scores) / len(subway_dists)


# ---------------------------------------------------------------------------
# F6 – F10: Network-level scoring functions
# ---------------------------------------------------------------------------

def normalize_stop_count(N_stop, N_ideal=30, N_max=15):
    """
    정류장 수 정규화 함수
    N_stop: 현재 노선의 정류장 수
    N_ideal: 이상적인 정류장 수
    N_max: 이상적 정류장 수로부터 허용 가능한 최대 편차 (±N_max)
    반환값: 0~1 범위의 정규화 점수 (1에 가까울수록 이상적)
    """
    diff = (N_stop - N_ideal) / N_max
    score = 1 - diff**2
    return max(0.0, min(1.0, score))


def node_alignment_scores(stops, nodes, node_type=None, radius=50, scale=100):
    """
    교통 노드 정규화 함수
    stops: 위도(lat)와 경도(lon) 쌍을 요소로 갖는 리스트
    nodes: 키를 포함하는 딕셔너리들의 리스트 'latitude','longitude','node_type'
    node_type: 필터할 노드 유형 (None=모든 노드)
    radius: 근접 판정 반경 (m)
    scale: 거리 점수 스케일 값 (m)
    """
    near_count = 0
    dists = []
    for lat, lon in stops:
        d2nodes = [
            geodesic((lat, lon), (n['latitude'], n['longitude'])).meters
            for n in nodes
            if node_type is None or n['node_type'] == node_type
        ]
        dmin = min(d2nodes) if d2nodes else np.inf
        dists.append(dmin)
        if dmin <= radius:
            near_count += 1
    S_node = near_count / len(stops) if stops else 0.0
    D_avg = np.mean(dists) if dists else np.inf
    S_dist = np.exp(-D_avg / scale) if D_avg != np.inf else 0.0
    return S_node, S_dist


def balanced_length_score(length_m, L_ideal=10000, L_max=15000):
    """
    교통링크 정규화 함수
    각 도로 링크의 실제 길이(length_m)가 이상적인 길이(L_ideal)에 얼마나 가까운지를
    정규화하여 0~1 사이의 점수로 반환합니다. 1에 가까울수록 이상 범위에 가까움을 의미합니다.
    """
    diff = (length_m - L_ideal) / L_max
    score = 1 - diff ** 2
    return max(0.0, min(1.0, score))


def duplication_penalty_score(weights, counts):
    """
    지역 공정성 적합도 함수
    weights: 각 요소 i에 대한 중복 가중치 w_dup_i 리스트
    counts: 각 요소 i에 대한 중복 횟수 count_i 리스트 (weights와 길이가 같아야 함)
    반환값: 0.0 ~ 1.0 사이의 점수 (중복이 없으면 1.0, 많을수록 0에 가까워짐)

    """
    if len(weights) != len(counts):
        raise ValueError("weights와 counts의 길이가 같아야 합니다.")
    N = len(weights)
    total_penalty = sum(w * c for w, c in zip(weights, counts))
    score = 1.0 - total_penalty / N
    return max(0.0, min(1.0, score))


def compute_transfer_score(route_stop_ids, transfer_stop_ids):
    """
    route_stop_ids: 후보 노선이 포함한 정류장 ID 리스트
    transfer_stop_ids: 기존 데이터 기반 환승 정류장 후보 리스트
    """
    if not route_stop_ids:
        return 0.0
    transfer_count = sum(1 for stop in route_stop_ids if stop in transfer_stop_ids)
    return transfer_count / len(route_stop_ids)
