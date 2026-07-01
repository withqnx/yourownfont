# YourOwnFont ✍️ 한글 손글씨 폰트

손글씨를 나만의 **한글 폰트(TTF/OTF)** 로 만들어주는 웹 앱.
자모 조각과 숫자·기호만 손으로 쓰면, **11,172자 전부를 자동 조합**합니다.

## 핵심 아이디어 — 자모 조합 (11,172자를 다 쓰지 않는다)

한글은 초성(19)·중성(21)·종성(27) 자모의 조합입니다. 그래서 **자모 약 67개 + 숫자·기호**
(총 ~110칸)만 손으로 쓰면, 소프트웨어가 각 자모를 음절마다 알맞은 위치·크기로 배치해
모든 글자를 만들어냅니다. AI·GPU가 필요 없어 **무료 호스팅에서 동작**합니다.

같은 ㄱ이라도 모음 방향(가 vs 고)·받침 유무(가 vs 각)에 따라 자동으로 크기·위치가
바뀝니다(1벌 + 지능형 배치). 더 자연스럽게 하려면 벌수를 늘리는 것이 향후 개선점.

## 동작 방식

```
템플릿 PDF 인쇄  →  자모·숫자·기호 손글씨  →  스캔/촬영  →  업로드
        │
        ▼
[정렬]   네 모서리 마커 검출 → 원근 보정 (OpenCV)
[추출]   이진화 → 격자 셀 분할 → 각 조각 크롭/정규화
[벡터화] 조각 윤곽선 추출 → 폰트 좌표(em)
[조합]   초·중·종성을 음절 영역에 배치·병합 → 11,172자 생성 (hangul.py)
[조립]   유니코드 매핑 → TTF/OTF 생성 (fontTools)
        │
        ▼
  브라우저 미리보기 + 폰트 다운로드
```

## 실행 (로컬)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --reload --port 8077
# http://127.0.0.1:8077
```

## 테스트

실제 스캔 없이 합성 페이지(마커 + 한글 시스템 폰트로 그린 자모)로 전체 파이프라인을 검증:

```bash
.venv/bin/python tests/test_korean_e2e.py
# → cells 109/109, syllables 11172, 샘플 렌더 build/korean_sample.png
```

## 구조

| 파일 | 역할 |
|------|------|
| `backend/app/charset.py`   | 자모(초·중·종성) + 숫자·기호를 Cell로 정의 |
| `backend/app/template.py`  | 인쇄용 PDF 템플릿 (격자 + 마커 + 한글 안내) |
| `backend/app/scan.py`      | 스캔 정렬·이진화·셀 분할·정규화 (OpenCV) |
| `backend/app/vectorize.py` | 비트맵 → 폰트 좌표 윤곽선 |
| `backend/app/hangul.py`    | 음절 분해 + 자모 배치·조합 엔진 |
| `backend/app/fontbuild.py` | fontTools로 TTF/OTF 조립 |
| `backend/app/pipeline.py`  | 스캔 → 자모 벡터화 → 음절 조합 → 폰트 |
| `backend/app/main.py`      | FastAPI: 템플릿/빌드/미리보기/다운로드 |
| `frontend/index.html`      | 단일 페이지 UI |

## 배포

무료(과금 없음)로는 **Render 무료 플랜**을 사용합니다 — 자세한 절차는 [DEPLOY.md](DEPLOY.md).
(Cloudflare Containers는 무료 티어가 없어 제외.)

## 알려진 한계 / 개선 여지

- **자모 배치가 휴리스틱**이라 일부 글자에서 자모가 늘어나거나 위치가 어색할 수 있음
  → 벌수 확대(초성 세로/가로용 등) + 영역 미세조정으로 개선 가능.
- 윤곽선이 폴리곤이라 가장자리가 약간 각짐 → potrace 곡선화가 향후 개선점.
- 휴대폰 촬영 시 그림자/심한 왜곡은 정렬 실패 가능 → 평판 스캔 권장.
- 폰트는 메모리 보관(단일 프로세스). 영구 저장은 R2/DO 등으로 확장 필요.
- TTF/OTF 모두 지원(웹 UI에서 선택).
