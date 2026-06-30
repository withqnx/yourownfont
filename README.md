# YourOwnFont ✍️

손글씨를 나만의 폰트(TTF)로 만들어주는 웹 앱.
템플릿을 인쇄해 글자를 쓰고, 스캔해서 업로드하면 폰트를 생성합니다.

> **현재 상태: v1 (MVP) — 영문·숫자·기호.**
> 한글 AI 자동 생성은 v2에서 추가 예정입니다 (아래 로드맵 참고).

## 동작 방식

```
템플릿 PDF 인쇄  →  손글씨 작성  →  스캔/촬영  →  업로드
        │
        ▼
[정렬]  네 모서리 마커 검출 → 원근 보정 (OpenCV)
[추출]  적응형 이진화 → 격자 셀 분할 → 글자 크롭/정규화
[벡터화] 윤곽선 추출 → 폰트 좌표(em)로 매핑 (베이스라인 정렬 + 자간)
[조립]  유니코드 매핑 → TTF 생성 (fontTools)
        │
        ▼
  브라우저 미리보기 + .ttf 다운로드
```

핵심 설계: 템플릿의 셀 좌표(`template.layout_cells`)와 정렬 마커(`marker_centers`)를
생성기와 스캐너가 **공유**하므로 둘이 절대 어긋나지 않습니다.

출력 형식은 **TTF / OTF** 모두 지원합니다(웹 UI에서 선택).

## 실행 (로컬)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --reload --port 8077
# http://127.0.0.1:8077 접속
```

## 배포

Cloudflare Containers(또는 Render)로 배포합니다. 자세한 절차는 [DEPLOY.md](DEPLOY.md) 참고.

## 테스트

실제 스캔 없이 합성 페이지(정렬 마커 + 시스템 폰트로 그린 글자)로 전체
파이프라인을 검증합니다:

```bash
.venv/bin/python tests/test_e2e.py
# OK: 94/94 glyphs, 95 cmap entries, font ~21KB
# build/test_output.ttf 와 미리보기 렌더가 생성됩니다
```

## 구조

| 파일 | 역할 |
|------|------|
| `backend/app/charset.py`   | 대상 글자 집합 + PostScript 글리프 이름 |
| `backend/app/template.py`  | 인쇄용 PDF 템플릿 생성 (격자 + 마커) |
| `backend/app/scan.py`      | 스캔 정렬·이진화·셀 분할·정규화 (OpenCV) |
| `backend/app/vectorize.py` | 비트맵 → 폰트 좌표 윤곽선 (베이스라인/자간) |
| `backend/app/fontbuild.py` | fontTools로 TTF 조립 |
| `backend/app/pipeline.py`  | 스캔 bytes → 폰트 bytes 오케스트레이션 |
| `backend/app/main.py`      | FastAPI: 템플릿/빌드/미리보기/다운로드 |
| `frontend/index.html`      | 단일 페이지 UI (별도 빌드 불필요) |

## 로드맵

- **v1 (완료)**: 영문·숫자·기호. 스캔 → 벡터화 → TTF. 동기 처리.
- **v1.1 (품질)**: potrace 곡선 벡터화(현재는 폴리곤), 기준선 자동 보정, 커닝.
- **v2 (한글 AI)**: 한글 시드 글자만 쓰면 few-shot 폰트 생성 모델
  (MX-Font / CKFont / FontDiffuser)로 11,172자 자동 생성.
  GPU 워커 + 비동기 작업 큐(Celery/Redis) 도입.
- **v3 (UX)**: React 프론트 전환, 진행률 표시, 폰트 편집 기능.

## 알려진 한계 (v1)

- 윤곽선이 폴리곤이라 글자 가장자리가 약간 각짐 → v1.1에서 곡선화.
- 휴대폰 촬영 시 그림자/심한 왜곡은 정렬 실패 가능 → 평판 스캔 권장.
- 폰트는 메모리에 보관(단일 프로세스). 영구 저장은 v2 작업 큐와 함께.
