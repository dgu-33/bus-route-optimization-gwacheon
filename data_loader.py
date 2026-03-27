import json
import pandas as pd


def load_reference_weights(filepath="llm_response.txt"):
    weights = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                key, val = line.strip().split(":")
                try:
                    weights[key.strip()] = float(val.strip())
                except ValueError:
                    pass
    # F5(w5)는 실질적으로 사용하지 않을 경우 자동 제거
    weights.pop("w5", None)
    return weights


def integrate_stop_poi(bus_stop_json, poi_data):
    """정류장 데이터에 poi_counts 병합"""
    for stop in bus_stop_json:
        stop_id = str(stop.get("정류소id", stop.get("정류소ID", "")))
        matching_poi = next((p for p in poi_data if p["id"] == stop_id), None)
        if matching_poi:
            stop["poi_counts"] = matching_poi["poi_counts"]
        else:
            stop["poi_counts"] = {}
    return bus_stop_json


def load_json_data(filename, encoding="utf-8"):
    """JSON 파일을 로드하고 에러 처리"""
    try:
        with open(filename, "r", encoding=encoding) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"에러: {filename} 파일을 찾을 수 없습니다.")
        return None
    except json.JSONDecodeError as e:
        print(f"에러: {filename} 파일의 JSON 형식이 잘못되었습니다. ({e})")
        return None


def load_bus_stops(json_data):
    """
    JSON 형식의 정류장 데이터 로드 및 '같은 좌표' 중복 제거
    """
    stops = []
    seen_coords = set()

    for i, row in enumerate(json_data):
        try:
            lat = float(row["WGS84위도"])
            lon = float(row["WGS84경도"])
        except (KeyError, ValueError):
            print(f"경고: 정류장 {i}의 위도/경도 변환 실패 → 스킵")
            continue

        coord = (round(lat, 7), round(lon, 7))
        if coord in seen_coords:
            continue
        seen_coords.add(coord)

        name = row.get("정류소명", "").strip()
        if not name:
            print(f"경고: 정류장 {i} - 이름 없음 → 스킵")
            continue

        stop_id = "stop_" + str(row.get("정류소id", f"{name}_{i}"))
        passengers = float(row.get("passengers", 100)) if row.get("passengers") else 100
        population = float(row.get("population", 500)) if row.get("population") else 500

        stops.append({
            "id": stop_id,
            "name": name,
            "lat": lat,
            "lon": lon,
            "passengers": passengers,
            "population": population
        })

    print(f"로드된 정류장 수 (중복 좌표 제거 후): {len(stops)}")
    return stops


def load_poi_data(filename="bus_stop.csv"):
    """POI 정보가 포함된 CSV 파일을 로드"""
    try:
        poi_df = pd.read_csv(filename, encoding='utf-8-sig')
        poi_data = []
        for _, row in poi_df.iterrows():
            poi_info = {
                "id": str(row["정류소ID"]),
                "name": row["정류소명"],
                "lat": row["위도"],
                "lon": row["경도"],
                "poi_counts": {
                    "대형마트": row["POI_대형마트"],
                    "편의점": row["POI_편의점"],
                    "어린이집": row["POI_어린이집"],
                    "학교": row["POI_학교"],
                    "학원": row["POI_학원"],
                    "주차장": row["POI_주차장"],
                    "주유소": row["POI_주유소"],
                    "지하철역": row["POI_지하철역"],
                    "은행": row["POI_은행"],
                    "문화시설": row["POI_문화시설"],
                    "중개업소": row["POI_중개업소"],
                    "공공기관": row["POI_공공기관"],
                    "관광명소": row["POI_관광명소"],
                    "숙박": row["POI_숙박"],
                    "음식점": row["POI_음식점"],
                    "카페": row["POI_카페"],
                    "병원": row["POI_병원"],
                    "약국": row["POI_약국"]
                }
            }
            poi_data.append(poi_info)
        return poi_data
    except Exception as e:
        print(f"POI 데이터 로드 중 오류 발생: {e}")
        return []
