# 버스 노선 최적화 — 과천시

이 repository는 과천시 버스 노선 최적화 시스템의 **알고리즘 핵심 부분**을 담고 있습니다.

---

## 프로젝트 개요

버스 정류장 목록과 도시 데이터를 입력받아 다음 기법을 조합하여 최적 버스 노선을 생성합니다:

- **A\*** — 도로 network 기반 최단 경로 탐색
- **유전 알고리즘** — 다목적 노선 최적화
- **K-means clustering** — 정류장 지역 유형 레이블링
- **LLM 기반 weight 조정** — LLM prompt로 도출한 fitness function weight
- **Kakao Map API** — 도로 network 데이터 수집 및 interactive map 출력

9개의 적합도 함수 (F1–F4, F6–F10)가 각 후보 노선을 노선 길이, 정류장 간격, POI 커버리지, 지하철 근접성, 정류장 수, 도로 정렬, 환승 연결성 등의 기준으로 평가합니다. F5 (유동인구)는 데이터 미확보로 제외되었습니다. 세대별 평가 후 정류장 중복 페널티가 노선 집합 전체에 추가로 적용됩니다.

---

## Repository 구조

```
bus_route_algorithm/
├── main.py                 # 전체 pipeline 실행
├── algorithm.py            # Genetic algorithm 및 세대별 중복 페널티 적용
├── fitness.py              # 점수 계산 함수 F1–F4, F6–F10
├── pathfinding.py          # A* 최단 경로 탐색
├── graph.py                # 정류장 레이블링 (K-means), graph 구성
├── scheduling.py           # 버스 배차 및 배차 간격 계산
├── visualization.py        # Kakao Map HTML 생성 및 노선 요약 출력
├── api_client.py           # Kakao API 호출 및 path cache 관리
├── data_loader.py          # 데이터 로딩 함수 모음 (JSON, CSV, weight)
├── POI.py                  # Kakao API를 통한 POI 데이터 수집 스크립트 
├── bus_stop.csv            # 정류장별 POI 수집 결과 
├── llm_response_example.txt # LLM weight 파일 예시 — llm_response.txt로 복사하여 사용
├── .env.example            # API key template — .env로 복사하여 사용
├── requirements.txt
└── data/
    └── README.md
```

---

## 설치 및 설정

### 1. Clone 및 패키지 설치

```bash
git clone <repo-url>
cd bus_route_algorithm
pip install -r requirements.txt
```

### 2. API key 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 Kakao API key를 입력합니다:

```
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here
KAKAO_JS_API_KEY=your_kakao_javascript_api_key_here
```

key는 [developers.kakao.com](https://developers.kakao.com)에서 발급받습니다. 필요한 key:
- **REST API key** — Directions API 및 Local Search API 호출용
- **JavaScript API key** — HTML output의 map rendering용

### 3. 도시 데이터 준비

각 필요 파일의 출처 및 형식은 [`data/README.md`](data/README.md)를 참고하세요.

### 4. LLM weight 설정

```bash
cp llm_response_example.txt llm_response.txt
```

`llm_response.txt`를 편집하여 fitness weight를 조정하거나, 노선 우선순위를 설명하는 LLM prompt로 생성할 수 있습니다. 형식은 예시 파일을 참고하세요.

---

## 실행

```bash
python main.py
```

실행 시 다음을 입력합니다:
- 생성할 노선 수
- 운행 가능한 버스 대수

출력: `bus_routes.html` — 생성된 노선과 정류장 marker를 표시하는 interactive Kakao Map

### POI 데이터 재수집

`bus_stop.csv`는 이미 포함되어 있습니다. 다른 도시에 적용하는 등 재수집이 필요한 경우:

```bash
python POI.py
```

`정류장위치/과천시_버스_정류장_위치.json`과 유효한 REST API key가 필요합니다.

---

