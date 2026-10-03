# 온실연구실 · 온실 재배 구획 배치 계산기

FastAPI 실습 과제. `greenhouse.py` 하나에 계산, HTML/CSS/JavaScript, SVG 배치도, 발표용 보고서를 포함합니다. 실행 시 외부 이미지·폰트·API를 요청하지 않습니다.

## 실행

Python 3.10 이상에서 이 폴더를 열고 실행합니다.

```powershell
python -m pip install -r requirements.txt
python greenhouse.py
```

접속: <http://127.0.0.1:8000/>. 서버를 직접 실행한 터미널에서는 `Ctrl+C`로 종료합니다.

## 새 기능

- 중앙 통로, 네 면의 외곽 여유 공간, 출입구 앞 작업 공간을 먼저 예약합니다.
- 입력 방향과 구획을 90도 회전한 방향을 같은 조건으로 계산해 나란히 비교합니다.
- 작물 보기 / 설계도 보기 전환. 잎채소·딸기·토마토 표현을 선택할 수 있습니다.
- 기본 격자·작은 온실·긴 온실·중앙 통로형 예제를 제공합니다.
- 구획 선택, 키보드 선택, 100–400% 확대, 확대 후 드래그 이동, 화면 맞춤을 지원합니다.
- 입력 패널 접기, 배치도 전체 화면을 지원합니다. 전체 화면 미지원 브라우저는 패널을 접어 표시합니다.
- 제목, 입력 조건, 선택한 배치도, 방향 비교, 면적 구성, 범례를 SVG / PNG / 인쇄용 보고서로 내보냅니다.
- PNG는 2400 × 2040으로 저장됩니다. `인쇄 / PDF` 화면에서 버튼을 누르고 인쇄 대상에 PDF 저장을 선택하세요.

## 주소창으로 실행하기

새 기본 예제 — 입력 방향 24개·96㎡·33.3%:

```text
http://127.0.0.1:8000/layout?width=12&length=24&bed_width=1&bed_length=4&path=0.5&margin=0.5&main_path=1.2&entry=1.5
```

동일 조건에서 90도 회전 — 28개·112㎡·38.9%:

```text
http://127.0.0.1:8000/layout?width=12&length=24&bed_width=1&bed_length=4&path=0.5&margin=0.5&main_path=1.2&entry=1.5&orientation=rotated&mode=blueprint
```

기존 과제 예제도 유지됩니다. 새로운 공간 매개변수를 생략하면 모두 0으로 계산합니다.

```text
http://127.0.0.1:8000/layout?width=10&length=20&bed_width=1&bed_length=4&path=0.5
```

결과: 28개·112㎡·56%. 이 예제의 `path=1` 결과는 20개·80㎡·40%입니다.

## 매개변수

| 이름 | 의미 | 범위 / 값 |
|---|---|---|
| width / length | 온실 가로 / 세로 | 0.01–1,000 m |
| bed_width / bed_length | 회전하기 전 구획 가로 / 세로 | 0.01–1,000 m |
| path | 구획 사이 통로 | 0–1,000 m |
| margin | 네 면의 외곽 여유 폭 | 0–1,000 m |
| main_path | 세로 방향 중앙 통로 폭 | 0–1,000 m |
| entry | 출입구 앞 작업 공간 깊이 | 0–1,000 m |
| orientation | 선택한 배치 방향 | original / rotated |
| mode | 보기 모드 | crop / blueprint |
| crop | 작물 장식 | leaf / strawberry / tomato |

길이는 소수점 넷째 자리까지 입력할 수 있고 각 배치안은 최대 2,500개 구획으로 제한됩니다. 외곽·중앙 통로·작업 공간을 빼고 남는 재배 영역의 폭과 깊이가 양수여야 합니다. 구획이 들어가지 않으면 해당 방향은 0개로 표시합니다.

## 계산 기준

1. 온실의 네 면에서 `margin`을 뺍니다. 내부 가로 = `width - 2 × margin`, 내부 세로 = `length - 2 × margin`.
2. 내부의 아래쪽 전체 폭에서 `entry`만큼 출입 작업 공간을 예약합니다.
3. `main_path > 0`이면 세로 방향의 중앙 통로를 예약하고 재배 영역을 좌우 같은 폭으로 나눕니다. 중앙 통로는 작업 공간과 연결됩니다.
4. 각 영역에서 가로 개수 = `(영역 폭 + path) // (구획 가로 + path)`, 세로 개수 = `(영역 깊이 + path) // (구획 세로 + path)`로 계산합니다.
5. 중앙 통로가 있으면 구획은 통로 쪽에 정렬합니다. 작업 공간이 있으면 구획을 아래쪽에 정렬해 작업 공간에 인접시킵니다. 나머지 폭은 바깥쪽, 나머지 깊이는 위쪽에 남습니다.
6. 중앙 통로와 작업 공간이 모두 0이면 기존처럼 좌측 상단에 배치합니다.
7. 같은 입력에서 구획의 가로·세로만 교환한 배치를 다시 계산합니다. 중앙 통로·외곽·작업 공간은 회전시키지 않습니다.

`Decimal`로 계산해 0.3 ÷ 0.1 같은 소수 경계에서 생기는 개수 오류를 피합니다.

### 면적 구분

다섯 항목은 중복 없이 온실 전체 면적과 일치합니다.

- 재배: 실제 구획 면적의 합
- 통로: 중앙 통로 + 배치된 구획 사이의 통로
- 출입 작업: 내부 가로 × 작업 공간 깊이
- 외곽 여유: 전체 면적 − 내부 가로 × 내부 세로
- 남는 공간: 위 네 항목을 제외한 미배치 면적

같은 색이나 장식이 있더라도 실제 치수 비율은 유지합니다. 구획이 많거나 작으면 번호·작물 그림을 줄이고, 좁아서 글자가 겹칠 수 있는 치수는 도면 아래 정보란에서 확인할 수 있습니다.

## 해석 범위

- 결과는 **두 방향의 균일 격자 비교**이며, 모든 배치 방식 중 최적해를 의미하지 않습니다.
- 중앙 통로가 있으면 양쪽을 같은 폭으로 나눕니다. 비대칭 배치·혼합 방향·이동식 벤치는 계산하지 않습니다.
- 출입구 표시는 아래쪽 중앙입니다. 중앙 통로가 있으면 그 폭에 맞추고, 없으면 최대 1.2m의 기호로 표시합니다. 별도의 문 폭 입력이나 문 회전 반경은 계산하지 않습니다.
- 외곽 여유 공간은 별도 예약 면적으로 분류합니다. 통로 안전 기준을 자동 판정하지 않습니다.
- 작물 선택은 그림만 바꿉니다. 실제 식재 수·권장 재식 간격·재배 적합성을 뜻하지 않습니다.
- 기둥, 설비, 구조, 배수, 환기, 실제 작업 동선 검증은 포함하지 않습니다.

## 제출 영상 예시 (약 2분)

1. `python greenhouse.py` 실행과 주소창의 URL을 보여줍니다.
2. 중앙 통로형 예제에서 온실·구획·통로·여유 공간의 입력값을 설명합니다.
3. 입력 방향 24개와 회전 방향 28개를 비교하고 회전 방향 카드를 선택합니다.
4. “통로 조건은 같고 구획을 돌리면 4개, 재배 면적 16㎡가 늘어납니다”라고 설명합니다.
5. 설계도 보기로 바꿔 치수·출입구·작업 공간을 보여줍니다.
6. 구획 선택, 확대, 전체 화면을 시연합니다.
7. PNG 저장 또는 인쇄 / PDF 보고서를 보여줍니다.
8. FastAPI가 주소창의 GET 매개변수를 받아 계산하고 HTML/SVG로 반환한다고 설명합니다.

**제출 코드:** `greenhouse.py`. 실행 영상은 위 순서로 녹화해 함께 제출하세요.

## 검증

계산·응답 검사:

```powershell
python -m pip install httpx
python -m unittest test_greenhouse -v
```

선택적인 실제 브라우저 검사 (Windows의 기본 설치 위치에 Chrome이 있고 서버가 실행 중이어야 함):

```powershell
python -m pip install playwright pypdf
python verify_browser.py
```

`artifacts`에는 화면 캡처와 실제로 내보낸 SVG/PNG/PDF 검증 샘플이 있습니다.

## 코드 구조

- `calculate_layout`: 공간 예약과 구획 배치
- `plan_pair`: 같은 조건의 두 방향 계산
- `make_svg`: 실제 좌표로 도면 생성
- `render_page`: 입력 패널, 비교 카드, 결과 화면
- `make_report`: 발표용 SVG 보고서
- `layout`: `/layout`, `/export.svg`, `/report` GET 요청 처리

## 참고 자료

- [Floorplanner 2D 도면 예시](https://floorplanner.com/2d-floorplan-examples): 도면 표현과 보기 모드
- [GrowVeg Garden Planner](https://www.growveg.com/introductory/garden-planner-quick-start.aspx): 작물과 구획을 표현하는 방식
- [GARDENA 예제 정원](https://www.gardena.com/int/c/discover/mygarden-planning-tools/garden-planner/example-gardens): 예제 선택 흐름
- [오클라호마주립대 온실 벤치 배치 자료](https://extension.okstate.edu/fact-sheets/print-publications/hla/greenhouse-floors-and-benches-hla-6703.pdf): 중앙 통로·예약 공간과 배치 비교 개념
- [FastAPI HTMLResponse](https://fastapi.tiangolo.com/advanced/custom-response/): HTML 응답 방식

기본값은 과제 시연용 예시이며, 위 자료의 권장 치수나 시공 기준을 그대로 적용한 값이 아닙니다.
