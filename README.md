# 제출OK · JechulOK

브라우저에서 이미지·PDF 파일을 변환하고 제출 규격을 확인하는 서비스입니다.

**공식 사이트:** https://jechulok.vercel.app

## v4.0 테스트 게이트

- `public/`: 운영 v3.9에서 가져온 정적 소스 스냅샷. 빌드 결과에만 v4.0을 표시하며 원본 파일 내용은 유지합니다.
- `build.mjs` / `vendor-lock.json`: PDF.js·pdf-lib·heic2any의 고정 버전을 해시 검증 후 `dist/`에 포함합니다.
- `scripts/verify-dist.mjs`: 사이트 경로·라이브러리 SHA-256 검사.
- `regression.mjs`: Playwright로 JPG, 2장 ZIP, 사진→PDF, PDF 5페이지 병합·2페이지 추출, 썸네일 렌더링을 검사합니다.
- `.github/workflows/ci-release.yml`: PR에서는 테스트만 하고, `main`에 변경이 들어오면 승인 후 빌드·스테이징·재검증·프로모션을 합니다.

## 수동 테스트

Node.js 22 이상, Python 3와 Chromium 실행이 가능한 환경에서:

```bash
npm ci
npx playwright install --with-deps chromium
npm run build
npm run verify
python3 -m http.server 4173 --directory dist --bind 127.0.0.1
```

다른 터미널에서:

```bash
BASE_URL=http://127.0.0.1:4173 npm test
```

기기별 HEIC·AVIF 샘플이 있으면 `HEIC_FIXTURE`, `AVIF_FIXTURE` 환경 변수에 **로컬 파일 경로**를 지정하여 선택 검사를 실행할 수 있습니다.

## Vercel 자동 배포 활성화 — 필수 사용자 설정

현재 Vercel 프로젝트 `jechulok`은 GitHub에 자동 연동되어 있지 않습니다. 따라서 GitHub Actions의 승인형 CLI 배포를 사용합니다. **Vercel Git 연동을 추가로 켜면 테스트 전에 자동 배포될 수 있으니 켜지 마세요.**

1. GitHub 저장소 → **Settings → Environments**에서 `production` 생성.
2. 공개 저장소이므로 가급적 **Required reviewers**를 지정하고, Deployment branches는 `main`으로 제한. 1인 저장소에서 자가 승인이 필요하면 GitHub 정책을 확인하세요.
3. 해당 Environment의 **Secrets**에 `VERCEL_TOKEN` 추가. Vercel에서 최소 권한 토큰을 직접 발급해 GitHub UI에 입력하고, 채팅이나 Git 코드에는 붙여넣지 마세요.
4. 해당 Environment의 **Variables**에 `VERCEL_ORG_ID` = `team_3zhjGeWXbOhhW3lWvodLGsAF`, `VERCEL_PROJECT_ID` = `prj_mAm5d2L05J7hHlgGj6EPbHg7rnEW` 설정.
5. PR의 `Build + real browser regression` 검사 통과 확인 → PR을 `main`에 병합 → GitHub Actions의 프로덕션 Job 승인. 실행 순서: build→test→stage production without domain→stage test→promote.
6. **Vercel 운영 사이트는 프로모션 이전까지 그대로 유지됩니다.** 토큰 누락이나 검증 실패 시 배포 작업이 중단됩니다.

현재 토큰과 Environment 설정은 이 저장소의 코드로 확인하거나 생성할 수 없기 때문에 사용자 측 설정 전에는 자동 프로덕션 배포가 활성화되지 않습니다.

## 보안 주의

- PR 빌드에는 운영 인증정보를 넣지 않습니다. 외부 사용자가 낸 PR에서는 절대 운영 배포를 실행하지 않습니다.
- `VERCEL_TOKEN`은 `production` Job에서만 사용됩니다.
- 파일 변환은 브라우저에서 동작하도록 유지합니다. PDF·HEIC의 자체 호스팅 라이브러리가 실패할 때에는 외부 CDN으로 fallback될 수 있습니다.
- GitHub 보호 규칙을 설정하면 PR 리뷰·검증을 필수화할 수 있습니다.
- 이 워크플로는 **GitHub Actions를 통한 배포만 통제**하며, 별도 Vercel 대시보드/API 권한 사용까지 차단하지는 않습니다.

