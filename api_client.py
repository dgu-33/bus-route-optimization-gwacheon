import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

# REST API 키 가져오기
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
if not KAKAO_REST_API_KEY:
    raise ValueError("KAKAO_REST_API_KEY 환경변수가 없습니다!")

HEADERS = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}

# JavaScript API 키 가져오기 (HTML 지도 시각화용)
KAKAO_JS_API_KEY = os.getenv("KAKAO_JS_API_KEY")
if not KAKAO_JS_API_KEY:
    raise ValueError("KAKAO_JS_API_KEY 환경변수가 없습니다!")

# 경로 캐시
CACHE_FILE = "path_cache.json"
try:
    with open(CACHE_FILE, "r", encoding="utf-8") as _f:
        path_cache = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError):
    print(f"⚠️ 캐시 파일 로드 실패({CACHE_FILE}). 새로운 캐시를 생성합니다.")
    path_cache = {}


def get_kakao_path(start_lon, start_lat, end_lon, end_lat):
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    params = {
        "origin": f"{start_lon},{start_lat}",
        "destination": f"{end_lon},{end_lat}",
        "priority": "RECOMMEND",
        "car_type": 1,
        "car_fuel": "GASOLINE"
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print("  → 요청 실패 상태 코드:", resp.status_code)
            print("  → 응답 내용:", resp.text)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("routes"):
            return None, 0
        route = data["routes"][0]
        distance = route["summary"]["distance"] / 1000  # m → km
        path_coords = []
        for section in route.get("sections", []):
            for road in section.get("roads", []):
                coords = road.get("vertexes", [])
                for i in range(0, len(coords), 2):
                    path_coords.append((coords[i+1], coords[i]))  # (lat, lon)
        return path_coords, distance
    except requests.RequestException as e:
        print(f"  → 경로 조회 오류: {e}")
        return None, 0
