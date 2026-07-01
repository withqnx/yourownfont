# 배포 가이드

## ✅ 현재 권장: Render 무료 플랜 (과금 없음)

코드는 이미 GitHub에 올라가 있습니다 → **https://github.com/withqnx/yourownfont** (private)
`render.yaml` 블루프린트도 포함돼 있어, Render가 서버에서 `Dockerfile`을 빌드합니다 (로컬 Docker 불필요).

저장소가 **public**이라 GitHub 로그인/연동 없이 URL만으로 배포합니다.

**남은 단계 (회원님이 Render 대시보드에서 진행 — 약 2분 + 첫 빌드 5~10분):**

1. https://render.com → **Get Started** → **Google 또는 이메일로 가입** (GitHub 로그인 사용 금지)
2. 대시보드 → **New +** → **Web Service**
3. **"Public Git Repository"** 칸에 URL 붙여넣기: `https://github.com/withqnx/yourownfont`
4. Render가 `Dockerfile` 자동 인식 → **Instance Type: Free** → **Create Web Service**
5. 첫 빌드 완료 후 `https://yourownfont.onrender.com` 형태 URL 발급

**무료 플랜 특성:** 15분간 요청이 없으면 잠들고, 다음 접속 시 콜드스타트 ~1분. 이후엔 정상 속도.

---

## 대안: Cloudflare Containers (유료 — $5/월)

> ⚠️ Cloudflare Containers는 **무료 티어가 없습니다**(Workers Paid $5/월 필수).
> 무료를 원하면 위 Render를 사용하세요. 아래는 유료 플랜을 쓸 경우의 절차입니다.

이 앱은 OpenCV 등 네이티브 라이브러리를 쓰는 Python 앱이라 **Cloudflare Workers(서버리스)에는 못 올라가고**, **Cloudflare Containers**로 배포합니다. 우리 `Dockerfile`을 그대로 컨테이너로 빌드해 올리고, 그 앞단의 작은 Worker(`src/index.ts`)가 모든 요청을 컨테이너로 전달합니다.

## 구성 파일 (이미 준비됨)

| 파일 | 역할 |
|------|------|
| `Dockerfile`        | FastAPI 앱 컨테이너 이미지 (uvicorn, 포트 8080) |
| `src/index.ts`      | 요청을 단일 컨테이너 인스턴스로 라우팅하는 Worker |
| `wrangler.jsonc`    | 컨테이너 + Durable Object 바인딩 + 마이그레이션 |
| `package.json`      | wrangler, @cloudflare/containers |

> ⚠️ 현재 폰트는 컨테이너 **메모리**에 보관됩니다(`POST /api/build` → `GET /api/font/{id}`).
> 그래서 모든 요청을 같은 인스턴스(`getByName("main")`)로 보냅니다. 컨테이너가
> 잠들면(20분 유휴) 저장분이 사라지므로, 영구 보관이 필요하면 R2/DO 저장소로 교체하세요.

## 전제조건

1. **Cloudflare Workers Paid 플랜 ($5/월)** — Containers는 유료 플랜에서만 동작 (베타).
2. **Docker Desktop 설치 + 실행** — wrangler가 이미지를 로컬에서 빌드해 푸시합니다.
   - 설치: https://docs.docker.com/get-started/get-docker/
   - 설치 후 실행: `open -a Docker`
3. Node.js (설치됨), 이 저장소.

## 배포 명령

```bash
cd "/Volumes/Mall(new)/DATA/YOUROWNFONT"

# 1) 의존성 (이미 설치돼 있으면 생략)
npm install

# 2) Cloudflare 로그인 (브라우저로 본인 계정 인증)
npx wrangler login

# 3) Docker Desktop 실행 확인 후 배포
open -a Docker            # 데몬이 떠 있어야 함
npm run deploy            # = wrangler deploy
```

배포가 끝나면 `https://yourownfont.<your-subdomain>.workers.dev` 형태의 URL이 출력됩니다.

### Docker 없이 검증만 하고 싶을 때

```bash
npx wrangler deploy --dry-run --outdir=dist   # Worker 번들/설정 검증 (이미지 빌드는 Docker 필요)
```

## 더 쉬운 대안 — Render (Docker 로컬 불필요)

Cloudflare 유료 플랜이나 Docker 설치가 부담되면, GitHub에 올린 뒤 Render가
서버에서 `Dockerfile`을 빌드하게 할 수 있습니다:

1. 코드를 GitHub 저장소에 푸시
2. Render → New → Web Service → 저장소 연결 → Runtime: **Docker** 자동 인식
3. 무료 플랜 선택 → Create. (로컬 Docker 불필요, Render가 빌드)

## 배포 후 확인

- `/` 접속 → 업로드 UI
- `/api/template` → 템플릿 PDF 다운로드
- 합성 테스트와 동일한 플로우로 업로드 → 폰트 생성/다운로드 확인
