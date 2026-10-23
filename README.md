# 제출OK (JeChulOK)

무료 파일 제출 준비 도구: https://jechulok.vercel.app/

## Agent Skill + local MCP v1.0.0 — AI가 로컬에서 제출 파일을 준비하도록

**[JeChulOK Submission Skill](.agents/skills/jechulok-submission/SKILL.md)**을 제공해요. Python 기반의 독립형 로컬 CLI로 JPG 사진 규격 검사·변환과 PDF 페이지 추출을 수행하고, 출력 파일의 실제 형식·용량·픽셀·페이지 수를 다시 확인합니다. 사용자 파일을 서버로 업로드하지 않으며, 기존 파일을 덮어쓰지 않습니다.

### v1.0 정식 안정화 릴리스

v0.9의 **14개 MCP 도구와 기존 CLI 사용법을 유지**하면서,
실제 로컬 MCP stdio 사용 흐름을 합성 이미지·PDF로 끝까지 검증했습니다.
파일 경로의 중간 심볼릭 링크·\`..\` 별칭을 차단하고,
읽기 오류 또는 알 수 없는 확장자를 기술 검증 \`pass\`로 처리하지 않습니다.
다중 파일 실행 중에도 각 입력·출력 경로를 다시 확인하며,
실패 시 생성된 결과를 정리합니다.

GitHub Actions는 Python 3.11·3.13에서 **의존성 검사 → 컴파일 →
전체 테스트 → 설치 환경 진단**을 실행합니다. 이 자동 검증은
실제 기관 접수나 외부 보안 감사가 아니며, 내용·서명·사진 구성은
직접 확인해야 합니다. 자세한 운영 범위는 [SECURITY.md](SECURITY.md)에
정리했습니다.

### 처음 사용한다면: 설치부터 Codex 연결까지

**[빠른 시작 가이드](.agents/skills/jechulok-submission/QUICKSTART.md)**에서
macOS·Windows 설치, Codex·Cursor·Claude Desktop 연결, 실제 테스트 방법을
정리했습니다. 별도의 가상환경을 사용해 시스템 Python을 변경하지 않습니다.

```bash
cd .agents/skills/jechulok-submission
python3 scripts/setup_mcp.py install --allowed-dir "/absolute/path/to/documents"
python3 scripts/setup_mcp.py doctor --allowed-dir "/absolute/path/to/documents"
python3 scripts/setup_mcp.py config --client codex --allowed-dir "/absolute/path/to/documents"
```

마지막 명령은 안전한 설정 **복사용 텍스트**만 출력합니다. 사용자 승인 없이
Codex 설정을 변경하지 않고, 설치 후에도 별도 MCP 연결 과정이 필요합니다.

### CLI 단독 설치(대체 방법)

MCP까지 사용할 경우에는 위의 v0.9 가상환경 설치를 권장합니다. 다음은 CLI만 사용할 때의 수동 설치 방법입니다. Python 3.11 이상이 필요합니다.

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


## MCP v1.0 — AI가 직접 호출하는 로컬 도구

기존 CLI 외에 **표준 MCP(stdio) 서버**를 지원합니다. AI가 `check_file`,
`prepare_image`, `extract_pdf_pages`, `verify_submission` 등의 14개 도구를
호출할 수 있습니다. Python 3.11+와 MCP Python SDK v2가 필요합니다.

```bash
cd .agents/skills/jechulok-submission
python -m pip install -r requirements-mcp.txt
```

Codex 연결 방법, 허용 폴더 설정(`JECHULOK_ALLOWED_DIRS`), 테스트와 제한 사항은
**[MCP v1.0 설명서](.agents/skills/jechulok-submission/MCP.md)**를 참고하세요.

서버는 로컬 stdio로만 통신하며 네트워크 API를 열지 않습니다.
**GitHub 저장소를 복제했다고 AI에 자동 설치되는 것은 아닙니다.** 사용자의
AI 클라이언트에서 MCP 서버를 연결해야 합니다. JPG 생성 후에는 기술적 규격을
다시 검사하며, 사진을 자르는 작업은 별도로 승인받도록 설계했습니다.


### v0.3 한국어 제출 조건 해석

새 MCP 도구 `parse_submission_rules`는 ‘JPG 300×400px 500KB 이하’ 같은 문장을 기술 조건으로 분리하고 모호한 요구를 `needs_review`로 표시합니다. `prepare_from_requirements`는 명확한 JPG 조건이나 사용자가 페이지 범위를 지정한 PDF에 대해서만 새 파일을 만들고 결과를 다시 읽어 검사합니다. 기존 네 도구도 그대로 유지됩니다.

CLI도 같은 파서를 사용합니다: `python scripts/jechulok.py parse-rules --text 'JPG 300×400px 500KB 이하'`

JPG 또는 PNG 같은 선택형 조건, cm/mm, 픽셀 단위가 없는 숫자, `500KB 미만`, 흰색 배경, 얼굴 비율, 전자서명 등은 자동 제출 적합성으로 판단하지 않습니다. PDF는 사용자에게 어떤 페이지를 보존할지 별도로 확인합니다. 단위는 기존 CLI와 동일한 1024기준 KiB/MiB입니다. 상세 내용은 MCP.md를 참고하세요.

### v0.4: 긴 공고 · 다중 파일 제출 준비

- `analyze_submission_notice`: 명시적으로 이름이 붙은 사진·이력서·증명서 조건을 공고에서 항목별로 분리하고 근거 줄을 함께 반환합니다.
- `prepare_submission_batch`: 항목 ID와 실제 파일 경로를 **수동으로 매칭**한 뒤 전체 계획을 우선 미리보기로 보여줍니다.
- **실행 전 이중 승인**: `execute=true`, `confirm_execution=true`를 모두 지정해야 실제 결과 파일을 만듭니다.
- 모호한 규격이나 공통 미배정 조건이 있으면 실행하지 않습니다. PDF 페이지 삭제·추출 범위는 사용자가 직접 지정해야 합니다.
- 전체 사전 검사, 기존 파일 덮어쓰기 방지, 기술 조건 재검증, 중간 실패 시 생성 결과 되돌리기를 제공합니다.

```bash
python scripts/jechulok.py parse-notice --text $'- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지'
```

v0.4 당시 MCP는 **8개 도구**였습니다. 기존 `main` 웹서비스 배포에는 영향을 주지 않으며, 별도 로컬 CLI/MCP 서버입니다.


### v0.5: 로컬 파일 후보 추천 (읽기 전용)

새 MCP 도구 `suggest_submission_files(notice_text, directory_path)`는 사용자가
지정한 폴더의 파일명과 확장자만 읽고, 공고의 각 제출 항목에 대해 후보를
최대 5개씩 보여줍니다.

- **자동 매칭·자동 수정·자동 제출 없음**: 모든 후보는 사용자가 직접 확인한 후
  `prepare_submission_batch`에 명시적으로 입력해야 합니다.
- **비재귀 탐색**: 최대 250개 폴더 항목만 확인하며, 이 범위를 넘기면
  `truncated=true`를 반환합니다.
- **개인정보 보호**: 문서 본문을 열지 않고, 외부 서버에 전송하지 않습니다.
  심볼릭 링크 및 허용 폴더 바깥 경로를 제한합니다.
- **실행 승인 유지**: 미리보기 → 사용자가 파일·페이지 확인 →
  `execute=true`와 `confirm_execution=true` 승인 순서를 지킵니다.
- 이름만 비슷한 파일은 실제 올바른 서류라고 판정하지 않습니다.

공고 내용이 모호하면 이전과 같이 `needs_review`가 반환되어 일괄
실행하지 않습니다.


### v0.6: 제출용 파일명 추천 · 항목별 검증 현황

10번째 로컬 MCP 도구 `suggest_submission_output_paths`를 추가했습니다.
확인된 파일 매칭과 출력 폴더를 전달하면 `제출용_증명사진.jpg`처럼
읽기 전용으로 파일 이름을 제안합니다. 같은 이름이 있으면 번호를
붙이며 **파일은 생성하지도 예약하지도 않습니다.**

- 조건을 이미 만족하는 PDF는 새로운 복사본을 만들지 않도록 제안
- PDF가 조건을 벗어나면 페이지 삭제를 추측하지 않고 수동 선택 요청
- 실제 실행 전에는 기존 `prepare_submission_batch` 미리보기와 이중 승인 필요
- 작업 결과에는 `summary` 추가: 항목별 `technical_status`,
  기술 검증 수, 생성 파일 수, 미검증 수 및 검토가 필요한 항목
- `technically_verified`는 파일의 기계적 제약 검사만 통과했다는 뜻입니다.
  기관에 접수되었거나 서류 내용이 적합하다는 의미가 아닙니다.

기존 웹사이트는 변경하지 않았습니다.


### v0.7: 승인 검토 · 실패 수정 가이드 · 최종 제출 체크리스트

새 MCP 도구 `review_submission_plan`은 실제 파일을 만들지 않고
항목별 경로와 PDF 선택 페이지를 사전 검사합니다. 모호하거나 잘못된
매칭에 대해서는 원인별 수정 안내를 보여줍니다.
`awaiting_human_approval`은 **승인이 완료되었다는 뜻이 아닙니다.**
정확한 작업 계획을 사용자에게 보여준 뒤 별도로 실행 승인을 받아야 합니다.

새 MCP 도구 `verify_submission_package`는 최종 파일을 **다시 열어**
규격을 검사합니다. 사진 크기나 PDF 용량처럼 기계가 확인할 수 있는
조건만 검증하며 파일이 중간에 바뀌면 새로운 검사 결과를 반영합니다.

- 준비 전: 공고 원문, 입력·출력 경로, PDF 페이지, 사진 자르기 승인 점검
- 준비 후: 기술 검증 결과, 항목별 실패 원인과 수정 가이드 제공
- 접수 전: 사진 내용·PDF 서명·본문·접수 사이트의 완료 여부를 사용자가 확인
- `technical_pass`는 규격 검사 결과일 뿐 **실제 접수 완료가 아닙니다**
- 로컬 파일만 처리하며 자동 업로드·신청서 자동 제출은 지원하지 않습니다

기존 웹서비스는 그대로 유지됩니다.


### v0.8: AI의 다음 질문 안내 + 로컬 HTML 검증 보고서

- `guide_submission_workflow`는 공고의 모호한 규칙, 누락된 원본,
  실행 전 승인, 최종 확인 중 **다음에 필요한 질문 하나**를 안내합니다.
  실제 파일 처리·페이지 선택·승인·업로드를 수행하지 않습니다.
- `create_submission_html_report`는 최종 파일을 현재 시점에 다시 검사하고
  브라우저에서 열 수 있는 로컬 HTML 결과 보고서를 생성할 수 있습니다.
  기본 호출은 **미리보기만** 하며 보고서를 만들지 않습니다.
- 보고서 저장은 `execute=true`와 `confirm_execution=true` 그리고
  사용자의 실제 승인 모두가 필요합니다. 기존 파일 덮어쓰기 금지.
- 보고서는 오프라인 정적 HTML이며 경로 전체·문서 내용·이미지·PDF 본문을
  포함하지 않지만, 최종 **파일명은 표시**합니다. 개인정보가 포함된
  파일명은 보고서 공유 전 확인하세요.
- 기술 규격 검사 완료를 **기관의 제출 완료**라고 표기하지 않습니다.

이번 변경은 로컬 Agent Skill/MCP에 한정되며 기존 웹사이트 배포는
변경하지 않았습니다.


### v0.9: 독립형 가상환경 설치 · MCP 연결 가이드 · 오류 진단

- Python 3.11+ **표준 라이브러리만** 사용하는 `setup_mcp.py` 도우미 추가
- `install`: 스킬 내부 `.venv`를 만들고 필수 MCP 의존성 설치
- `doctor`: Python·MCP 모듈·허용 폴더 접근·실행 경로 등을 읽기 전용 검사
- `config`: Codex용 TOML, Cursor·Claude Desktop용 JSON 연결 설정 출력
- Windows 경로의 역슬래시·따옴표를 안전하게 이스케이프하고,
  macOS·Linux 가상환경 Python 심볼릭 링크의 실행 경로를 유지
- 연결 실패 원인별 해결 방법과 실제 대화 예제를 `QUICKSTART.md`에 추가

기존 **MCP 도구 14개**는 유지합니다. 클라이언트 설정을 자동으로 수정하거나,
사용자 동의 없이 파일을 변환하거나 업로드하지 않습니다. 기존 웹사이트는 변경하지 않았습니다.
