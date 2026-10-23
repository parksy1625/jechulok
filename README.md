# 제출OK (JeChulOK)

무료 파일 제출 준비 도구: https://jechulok.vercel.app/

## Agent Skill v0.1.0 — AI가 로컬에서 제출 파일을 준비하도록

**[JeChulOK Submission Skill](.agents/skills/jechulok-submission/SKILL.md)**을 제공해요. Python 기반의 독립형 로컬 CLI로 JPG 사진 규격 검사·변환과 PDF 페이지 추출을 수행하고, 출력 파일의 실제 형식·용량·픽셀·페이지 수를 다시 확인합니다. 사용자 파일을 서버로 업로드하지 않으며, 기존 파일을 덮어쓰지 않습니다.

### 설치

Python 3.11 이상이 필요합니다.

```bash
cd .agents/skills/jechulok-submission
python -m pip install -r requirements.txt
python scripts/jechulok.py --help
```

Codex는 이 저장소를 작업 폴더로 열면 `.agents/skills/jechulok-submission/SKILL.md`를 프로젝트 스킬로 인식할 수 있습니다. 개인 범위에서 쓰려면 폴더를 `~/.agents/skills/jechulok-submission`에 복사하거나 Codex의 스킬 설치 기능을 이용하세요. <https://learn.chatgpt.com/docs/build-skills>

### 예시

```bash
# 조건 검사만 진행
python scripts/jechulok.py check --input ./photo.png --format jpg --width 300 --height 400 --max-kb 500

# 원본을 유지하고 제출용 JPG 생성·검증
python scripts/jechulok.py prepare-image --input ./photo.png --output ./photo-ready.jpg --width 300 --height 400 --max-kb 500 --mode contain

# PDF에서 2~4, 7페이지 추출
python scripts/jechulok.py prepare-pdf --input ./source.pdf --output ./selected.pdf --pages 2-4,7 --max-pages 4
```

`--max-kb`는 1KB = 1,024바이트로 계산합니다. 변환 후 `status: "pass"`는 **기술적으로 명시한 규격만 충족**했다는 뜻이며, 실제 접수 성공이나 사진 내용의 적합성을 보장하지 않습니다. JPG/PNG/WebP 입력을 지원하며, HEIC/AVIF 변환·OCR·PDF 완전 편집 등은 아직 지원하지 않습니다. PDF 페이지 추출 시 서명·북마크·폼이 보존되지 않을 수 있습니다.

### 테스트

```bash
python -m unittest discover -s tests -v
```

GitHub Actions가 Python 3.11·3.13 환경에서 테스트합니다. CLI 스킬 폴더는 MIT 라이선스이며, 이 라이선스가 저장소의 별도 웹서비스 소스나 다른 프로젝트에 자동으로 적용되지는 않습니다.

**기능 제안·버그:** 이 저장소의 GitHub Issues에 남겨주세요.
