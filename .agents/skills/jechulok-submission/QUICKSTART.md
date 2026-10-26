# 제출OK Agent Skill + MCP v2.7 빠른 시작

제출OK는 **사용자 컴퓨터에서 실행되는 로컬 프로그램**입니다. 이 저장소를 복제하거나
이 웹페이지를 방문하는 것만으로 AI 클라이언트에 자동 연결되지는 않습니다.
Python 3.11+와 인터넷 연결(최초 패키지 설치 시)이 필요합니다.
파일 준비와 MCP 통신은 설치 후 로컬에서 작동하며 파일을 업로드하지 않습니다.

## 1. 복제하고 설치하기

저장소를 복제한 다음 **실제 서류가 있는 폴더 경로**를 명시하세요.
폴더는 설치 전에 존재해야 하며 심볼릭 링크나 `..` 별칭이 아니어야 합니다.

```bash
git clone https://github.com/parksy1625/jechulok.git
cd jechulok/.agents/skills/jechulok-submission
python3 scripts/setup_mcp.py install --allowed-dir "/absolute/path/to/your/documents"
```

Windows에서는 `python3` 대신 `py -3.11` 또는 `python`을 사용할 수 있습니다.
PowerShell에서는 Windows 절대경로를 따옴표로 감싸세요. 실습은 다른 개인정보 폴더 대신
테스트 전용 서류 폴더를 만드는 것이 좋습니다.

설치는 스킬 폴더 내부 `.venv` 가상환경에만 필요한 패키지를 설치하고,
**Codex·Cursor·Claude Desktop 설정 파일을 자동 변경하지 않습니다.**
동일 명령을 재실행하면 기존 가상환경을 재사용합니다.

## 2. 자가 진단

```bash
python3 scripts/setup_mcp.py doctor --allowed-dir "/absolute/path/to/your/documents"
```

`status: pass`면 Python 버전, 가상환경 실행 파일, 패키지 import,
서버 스크립트, 작업 폴더의 OS 수준 접근권한이 확인된 상태입니다.
`needs_setup`이면 `checks`의 `fix`를 확인하세요.
진단은 파일을 생성·삭제·변환하지 않으며 클라이언트 연결의 실제 성공까지 보증하지 않습니다.

## 2-1. MCP 실제 연결 진단 (v1.1)

기존 `doctor`는 Python 환경을 확인했지만 MCP 서버가 실제로 호출되는지는
확인하지 않았습니다. 이제 다음 명령으로 서버를 로컬에서 실행하고,
**현재 20개 MCP 도구 목록과 합성 문장 규칙 분석 호출**을 검사할 수 있습니다.

```bash
python3 scripts/setup_mcp.py probe --allowed-dir "/absolute/path/to/your/documents"
```

설치 검사부터 실제 서버 응답까지 한 번에 확인하려면:

```bash
python3 scripts/setup_mcp.py status --allowed-dir "/absolute/path/to/your/documents"
```

성공 결과는 `"status": "pass"`, 실패 시에는 `code`와 `fix`를
반환합니다. 이 명령은 실제 제출 파일을 열거나 처리하지 않습니다.
`status=pass`는 **이 컴퓨터에서 로컬 MCP 서버와 통신할 수 있다는 뜻**이며,
Codex·Cursor·Claude Desktop의 설정 적용이나 실제 서류 접수 성공을
뜻하지 않습니다. 클라이언트 자체에서도 도구 목록과 합성 텍스트
`parse_submission_rules` 호출을 확인해 주세요.

## 3. Codex에 연결

```bash
python3 scripts/setup_mcp.py config --client codex --allowed-dir "/absolute/path/to/your/documents"
```

출력되는 **TOML 코드만** 기존 `~/.codex/config.toml`에 추가하세요.
`[mcp_servers.jechulok]` 항목이 이미 있으면 중복 삽입하지 말고
기존 항목을 검토한 뒤 수정하세요. 기존 설정을 통째로 덮어쓰지 마세요.

```toml
# 아래는 개념 예시입니다. 실제 절대경로는 config 명령이 생성합니다.
[mcp_servers.jechulok]
command = "/ABSOLUTE/PATH/.venv/bin/python"
args = ["/ABSOLUTE/PATH/scripts/mcp_server.py"]
[mcp_servers.jechulok.env]
JECHULOK_ALLOWED_DIRS = "/ABSOLUTE/PATH/TO/YOUR/DOCUMENTS"
```

Codex를 다시 실행한 뒤 `codex mcp list`로 연결 목록을 확인하세요.
도구 호출까지 확인하려면 아래 예제의 규칙 분석 요청을 실행해 보세요.
Codex CLI와 IDE 확장은 연결 설정을 공유할 수 있습니다.
<https://developers.openai.com/learn/docs-mcp>

## 4. Cursor / Claude Desktop에 연결

```bash
python3 scripts/setup_mcp.py config --client cursor --allowed-dir "/absolute/path/to/your/documents"
python3 scripts/setup_mcp.py config --client claude-desktop --allowed-dir "/absolute/path/to/your/documents"
```

명령 출력은 각각 `mcpServers.jechulok` JSON 객체를 담은 **예시 설정**입니다.
Cursor의 MCP 설정(일반적으로 `~/.cursor/mcp.json`)이나
Claude Desktop의 MCP 서버 설정에 해당 서버 항목만 병합하세요.
기존 JSON을 통째로 대체하거나 중복 키를 만들지 마세요.
설정 경로와 UI는 클라이언트 버전에 따라 달라질 수 있습니다.

이 서버는 로컬 **stdio** 전용입니다. 네트워크 URL로 등록하는 서버가 아닙니다.
클라우드에서 실행되는 AI 세션은 사용자 PC의 파일에 자동 접근할 수 없습니다.

## 5. 실제 대화 예시

먼저 민감하지 않은 문구로 도구 연결을 테스트하세요.

> 제출OK의 parse_submission_rules로 "JPG 300×400px 500KB 이하"를 분석해 줘.
> **파일 변경 없이** 파싱 결과와 불확실한 조건만 설명해 줘.

공고 분석을 시작할 때:

> 다음 공고를 제출OK의 analyze_submission_notice로 분석해 줘.
> 각 항목의 조건을 정리하고 불명확한 내용은 먼저 물어봐.
> 내 파일을 자동으로 매칭하거나 생성하지는 마.

실제 파일 준비를 할 때:

> 이 사진은 300×400px JPG 500KB 이하 조건이야. 먼저 inspect/check_file로 확인하고,
> 파일이 맞지 않으면 새 파일 작업을 **미리보기**로 보여줘. 정확한 입력·출력
> 경로와 사진 자르기 여부를 확인한 뒤에만 작업해.

최종 검증을 할 때:

> 지정한 파일들을 verify_submission_package로 다시 확인해 줘.
> 기술 조건에서 통과하지 못한 항목과 사람이 직접 확인할 목록을 알려줘.
> 제출 사이트에는 업로드하지 마.

## 6. 문제 해결

| 증상 | 우선 조치 |
|---|---|
| `python` 실행 불가 | Python 3.11 이상 설치 및 실행 명령 확인 |
| `mcp` / `pypdf` / `PIL` import 오류 | 가상환경 설치 재실행 → `doctor` 결과 확인 |
| MCP 서버 실행은 되지만 도구 목록 없음 | `command`가 `.venv`의 Python인지, `args`가 올바른 `mcp_server.py` 절대경로인지 확인 |
| 허용 폴더 밖이라는 오류 | `JECHULOK_ALLOWED_DIRS`를 실제 파일 폴더로 제한해 지정했는지 확인 |
| 경로가 바뀐 후 연결 실패 | 스킬을 옮겼다면 `config` 명령을 다시 실행해 새 경로로 갱신 |
| Windows TOML 파싱 오류 | 직접 백슬래시를 쓰지 말고 `config --client codex` 출력값 복사 |
| AI가 승인 없이 작업하려 함 | 실행 중단. 작업은 기본 미리보기이며 실제 실행에는 사용자 승인과 이중 플래그 필요 |
| PDF 페이지가 자동 선택되지 않음 | 정상 동작: 사용자가 보존할 페이지를 반드시 결정 |
| 파일 검증은 통과했지만 접수가 되지 않음 | 기술 규격 통과는 문서 내용·기관 접수 완료를 보증하지 않음 |

**보안:** `JECHULOK_ALLOWED_DIRS`는 필요 최소 폴더만 지정하세요.
출력 설정에는 PC의 절대경로가 있으므로 외부에 공유하기 전에 확인하세요.
새 파일 생성은 사용자가 승인한 명시적 경로에만 수행하며 원본을 덮어쓰지 않습니다.


## 7. 서버 비정상 종료 후 파일 복구 (v1.4)

v1.4의 승인된 비동기 작업은 첫 허용 작업 폴더 안의
`.jechulok-jobs/`에 상태 기록을 저장합니다. JPG/PDF를 임시 이름으로
검증한 뒤 최종 결과를 게시하므로, 강제 종료 시 일부 임시 파일과
최종 출력 파일이 함께 남아 있을 수 있습니다.

복구 순서는 다음과 같습니다.

1. Codex 등 MCP 클라이언트에서 `list_interrupted_submission_jobs`를
   호출해 중단된 `job_id`, 임시 파일명 및 출력 파일 존재 여부를 확인합니다.
2. `resolve_interrupted_submission_job(job_id)`를 호출하면
   **미리보기**만 표시되며 어떤 파일도 삭제하지 않습니다.
3. 최종 출력 파일은 **사용자가 직접 확인하고 보관·이동 여부를 결정**합니다.
   최종 파일이 이미 존재하면 이전 출력명을 재사용하지 마세요.
4. 전용 임시 파일만 지우기로 명확하게 동의한 후
   `resolve_interrupted_submission_job`에
   `cleanup_staging=true`, `confirm_cleanup=true`,
   `checked_final_outputs=true`를 전달합니다. 기존 서버 PID가
   실행 중일 수 있거나 경로가 안전하지 않으면 정리는 거부됩니다.
5. 반환 상태가 `reviewed`인 것을 확인한 후 **새 미리보기와 새 승인**으로
   작업을 다시 시작합니다. 이전 승인이나 실행 중이던 작업은
   자동으로 복원되지 않습니다.

**중요:** 여러 파일을 한 번에 게시하는 작업은 전체 원자성을
보장하지 않습니다. 비정상 종료 후 남은 *최종 출력 파일*은 복구
도구가 삭제하지 않습니다. 임시 파일 안에도 개인정보가 있을 수
있으므로 로컬 작업 폴더를 안전하게 보호하세요. 임시 파일 제거
명령은 시스템 전체 임시 파일을 청소하는 도구가 아닙니다.


## 8. 여러 AI 클라이언트가 동시에 같은 폴더에 연결될 때 (v1.5)

Codex, Cursor, Claude Desktop 등이 같은 제출 폴더에 연결되면
**모두 동일한 `JECHULOK_ALLOWED_DIRS`의 첫 번째 폴더**를 사용하세요.
v1.5에서는 승인된 작업을 실행하는 순간 이 폴더의
`.jechulok-jobs/.writer.lock` 파일에 OS 수준 배타적 잠금을 설정합니다.
다른 MCP 프로세스가 작업 중이면 `folder_writer_active` 오류를
반환하며 작업 파일을 만들지 않습니다.

잠금 파일은 삭제하지 마세요. 실제 잠금은 프로세스가 종료되면
운영체제가 해제합니다. 서버가 비정상 종료되었다면
`list_interrupted_submission_jobs`로 `interrupted_job_count`와
각 파일 개수를 확인하고, **최종 파일부터 직접 검사**한 후
기존 v1.4의 확인 절차를 따르세요. 새 작업에는 새 승인이 필요합니다.

**제한 사항:** 이 방식은 같은 첫 번째 작업 루트를 지정한
v1.5 MCP 서버들끼리의 협력적 보호입니다. 독립된 폴더 설정이나
다른 프로그램까지 차단하는 시스템 전체 잠금은 아닙니다.


## 9. AI에게 한 번에 요청하는 대화형 안내 (v1.6)

MCP 연결 후 AI에게 다음과 같이 요청해 보세요.

> "제출OK 안내 모드로 진행해줘. 제출 공고를 읽고 나에게 필요한
> 질문을 한 번에 하나씩 해줘. 정확한 계획을 보여준 후, 내가
> 승인하기 전에는 아무 파일도 생성하지 마."

AI는 새 `assist_submission` 도구를 사용하여 5단계를 안내합니다.

1. `action="next"`: 공고의 모호한 부분 확인
2. `action="next"`와 공고 텍스트: 원본 파일 지정 질문
3. 파일 지정 목록을 함께 넘겨 정확한 변환 계획과
   `approval_fingerprint` 미리보기 제공
4. **실제 승인 후에만** `action="start"`와 실행 플래그 2개,
   미리보기에서 받은 검증값을 전달하여 작업 시작
5. `action="status"`로 완료 확인, `action="verify"`로
   최종 파일 기술 검증 및 수동 체크리스트 확인

각 질문과 계획은 로컬에서만 처리됩니다. 이 새 안내 기능은
별도 사용자 프로필이나 서버 세션을 저장하지 않습니다.
`approval_fingerprint`는 계획이 변경됐는지 확인하기 위한
값이지, 승인 증명이나 파일 원본의 해시가 아닙니다.
사용자 동의 없이 실행 플래그를 true로 설정하지 마세요.


## 10. 여러 서류를 한 번에 선택하고 오류 수정하기 (v1.7)

AI가 안내 모드에서 파일 선택을 요청할 때 다음과 같이 말할 수 있습니다.

> "이번 공고의 원본 파일 중 누락된 항목을 한 번에 정리해 줘.
> 내가 지정하는 폴더에서 파일명 후보만 보여주고, 파일은 네가
> 자동으로 선택하거나 내용 적합성을 추측하지 마."

`assist_submission(action="next", notice_text="...", source_directory="...")`
형태로 호출하면 **명시된 허용 폴더**에서만 파일명·확장자 기반
추천을 받습니다. `source_directory`를 생략하면 디렉터리 검색을
하지 않습니다. 후보는 3개씩만 노출하며 서류를 자동 배정하지 않습니다.

공고가 모호하면 `notice_explanation`에서 원문 줄번호와
필요한 확인 항목을 살펴보고 직접 판단하세요. 파일 준비 계획이
막히면 `problem_explanation`에 표시된 코드와 다음 조치를
확인한 후 다시 미리보기하세요.

파일 생성·PDF 페이지 추출·자르기 승인 절차는 v1.6과 동일합니다.
안내 개선이 사용자 승인이나 접수 완료를 대신하지 않습니다.


## 11. 안내 품질 자동 검사하기 (v1.8)

실제 개인정보를 입력하거나 파일을 업로드하지 않고 합성 공고
100건에 대한 품질·안전성 회귀 검사를 실행합니다.

```bash
cd .agents/skills/jechulok-submission
python scripts/evaluate_v18.py --check
```

출력 JSON의 evaluated_cases = 100 및 distinct_synthetic_notices = 100을
확인하세요. status = pass 이면 **해당 합성 테스트 100개**가 모두
사전 정의된 기대 결과를 만족했다는 뜻입니다. 실제 기관 공고
해석 정확도 100% 또는 지원 서류가 모두 접수된다는 뜻은 아닙니다.

GitHub Actions에서도 평가 JSON을 jechulok-eval-v18-synthetic
아티팩트로 제공합니다. 평가 방법과 해석 한계는 EVALUATION.md를
참고하세요. 원본 파일이나 개인 제출 공고는 테스트에 사용하지 않습니다.


## 12. 실제 공고 정확도를 독립 검수로 평가하기 (v1.9)

v1.9는 실사용자 자료를 **자동 수집하지 않습니다**. 사용 권한이
있고 개인정보를 수동으로 제거한 공고의 **파일 제출 기술 조건만**
별도 JSONL 파일로 수집해야 합니다. 사람 2명이 서로의 답변과
파서 출력 결과를 보지 않고, 같은 공고에 정답 라벨을 부여하세요.
의견이 다르면 제3자가 따로 판정합니다.

사람의 승인을 받은 뒤 아래처럼 로컬에서만 실행하세요.

```bash
cd .agents/skills/jechulok-submission
mkdir -p private-evaluation
# 먼저 REAL_EVALUATION.md의 스키마로 파일을 안전하게 작성하세요.
python scripts/evaluate_real_v19.py private-evaluation/notices.notice-eval-private.jsonl --strict
```

실제 파일이 없다면 GitHub에 있는
`tests/fixtures/v19_example_synthetic.jsonl` 예제로만 시험할 수
있으며 **그 결과를 실제 성능으로 표현해서는 안 됩니다.**
출력되는 집계 결과에서 조건 누락률과 잘못된 조건률, 검수자
합의율과 안전 차단률을 별도로 비교하세요.

실제 공고나 평가 자료를 GitHub 저장소·Actions·공개 이슈에
업로드하지 마세요. 사람의 비식별화 검수가 필수이며,
정규표현식 차단만으로 민감정보 누출을 완전히 방지할 수 없습니다.


## 13. v2.0 ZIP 배포 · 기존 설치 보존 업데이트

GitHub Actions 실행 결과의 `jechulok-agent-skill-v2.0.0`에서 ZIP과
SHA-256 파일을 받을 수 있습니다. (최종 태그 기반 GitHub Release가
실제로 게시된 경우에는 Releases에서도 받을 수 있습니다.)
신뢰할 수 있는 프로젝트 배포 자료인지 출처를 확인하세요.
이 체크섬은 **전자서명이 아닙니다**.

기존 로컬 스킬에서 **먼저 쓰기 없는 업데이트 미리보기**를 실행합니다.

```bash
python scripts/setup_mcp.py upgrade \
  --allowed-dir "/USER/WORK/FOLDER" \
  --archive "/DOWNLOAD/jechulok-agent-skill-v2.0.0.zip" \
  --destination "/NEW/FOLDER/jechulok-skill-v2"
```

경로를 확인한 다음 같은 명령 끝에 `--execute`를 추가하면
**존재하지 않는 새 폴더**에만 파일을 풀어 놓습니다.
기존 가상환경, MCP 클라이언트 설정, 원본 서류는 건드리지 않습니다.

새 폴더로 이동한 뒤 `setup_mcp.py install` → `doctor` →
`probe` → `config` 순서로 검사하고, 사용자 확인 후
새 클라이언트 MCP 설정만 직접 병합하세요. 잘못되면 **기존 설치
경로를 가리키던 설정으로 되돌려** 이전 버전을 유지할 수 있습니다.
자동 다운로드나 클라이언트 설정 전환을 지원하는 것으로
오해하지 마세요.

개발·릴리스 검사:
`python scripts/release_v20.py verify --archive "/DOWNLOAD/...zip"`
는 읽기 전용입니다. ZIP 생성은 개발 소스에서
`python scripts/release_v20.py build --output-dir "/EXISTING/DIR"`
로 할 수 있습니다. 기존 출력 파일은 덮어쓰지 않습니다.

정식 태그 기반 릴리스는 별도 `v2.0.0` Git 태그가 실제로
푸시된 경우에만 시작됩니다. 현재 Actions 아티팩트의 30일 보관과
태그 기반 Release 영구 배포는 서로 다릅니다.


## 14. v2.1 업데이트 확인과 베타 테스트 진단

다음 명령은 모두 로컬 폴더에 있는 파일을 처리하지 않고
상태를 점검합니다.

```bash
python scripts/setup_mcp.py doctor --allowed-dir "/USER/WORK/FOLDER"
python scripts/setup_mcp.py probe --allowed-dir "/USER/WORK/FOLDER"
python scripts/setup_mcp.py beta-check --allowed-dir "/USER/WORK/FOLDER"
python scripts/setup_mcp.py updates --allowed-dir "/USER/WORK/FOLDER"
```

기본 `updates`는 **네트워크를 사용하지 않습니다**. 사용자가
GitHub에 접속해 게시된 안정 버전을 알아보려면 다음을 **명시적으로**
실행해야 합니다.

```bash
python scripts/setup_mcp.py updates --allowed-dir "/USER/WORK/FOLDER" --online
```

이 요청은 GitHub API의 릴리스 메타데이터만 읽으며, 설치 프로그램을
내려받거나 실행하지 않습니다. 릴리스가 게시되지 않았다면
`no_published_release`를 반환할 수 있습니다.

ZIP에서 설치한 경우 `doctor`는 MANIFEST.json의 파일별 체크섬과
실제 설치 파일을 비교합니다. Git 저장소 체크아웃은 매니페스트가
없으므로 무결성 확인이 생략되었다고 출력합니다. 매니페스트도
변조될 수 있어 전자서명이나 발행자 인증 수단은 아닙니다.

외부 테스트는 개인 서류가 없는 **별도 합성 데이터 폴더**에서만
진행하고, 문제를 제보할 때 실제 파일 경로·스크린샷·원문을
업로드하지 마세요. 자세한 절차는 `BETA_GUIDE.md`를 참고하세요.


## 15. 처음 설치한 사용자를 위한 자동 안내 (v2.2)

문제가 생기면 다음 명령을 실행하세요.

```bash
python scripts/setup_mcp.py guide --allowed-dir "/WORK/FOLDER"
```

한글 일반 텍스트로 **현재 단계·검사 오류·다음 행동**을 안내합니다.
명령은 자동 실행하지 않으며 작업 파일·클라이언트 설정을
변경하지 않습니다. 색깔이 없어도 이해할 수 있도록 구성되어 있습니다.

영어가 필요하면 `--language en`, 기계 판독 결과가 필요하면
`--format json`, 특정 클라이언트 안내는 `--client cursor`처럼
지정하세요. 설치 점검만 정상이어도 AI 앱 연결이 보장되지는 않습니다.
실제 로컬 MCP 연결을 확인하려면 **별도 동의로** `--probe`를 추가하세요.

배포 파일이 훼손됐다는 경고가 나오면 **현재 설치 파일을 더
실행하지 말고**, 신뢰할 수 있는 GitHub 아티팩트에서 새 파일을
확보해 **다른 폴더에 설치**하세요. 어떤 단계도 개인 서류를
자동 처리하거나 기관에 제출하지 않습니다.


## 16. 설치가 손상됐을 때 안전하게 복구하기 (v2.3)

먼저 신뢰할 수 있는 다른 설치본의 `setup_mcp.py`에서만
**읽기 전용 복구 계획**을 확인하세요. 손상된 설치본의 코드나
설치 스크립트를 계속 실행하지 마세요.

```bash
python scripts/setup_mcp.py recovery-plan \
  --allowed-dir "/WORK/FOLDER" \
  --archive "/DOWNLOAD/jechulok-agent-skill-v2.3.0.zip" \
  --destination "/NEW/FOLDER/jechulok-v23"
```

`status=planned`면 ZIP 내부 일관성과 새 설치 위치가 확인된
것이지 **발행자 서명이나 실제 복구 완료**가 아닙니다. 이
명령은 파일을 만들지 않습니다.

신뢰할 수 있는 원본을 검증하고 사용자가 명시적으로 승인한
뒤에만 기존 `upgrade` 명령에 `--execute`를 붙여 새 폴더에
압축을 풉니다. 새 폴더에서 의존성 설치→doctor→probe→config
순서로 검사하고, 최종 MCP 클라이언트 설정은 **직접 확인 후
변경**하세요. 기존 설치와 설정을 남겨두면 수동 복귀가 가능합니다.

합성 환경에서 전체 복구 과정을 점검하려면:

`python scripts/recovery_scenarios_v23.py --check`

통제된 **14개 테스트**이지 실제 외부 사용자 조사가 아닙니다.
실제 사용자 문서를 입력하거나 기관에 접수하지 않습니다.

## 17. 첫 제출 서류 준비 안내 (v2.4)

기존 MCP 클라이언트에서 `assist_submission`에 공고의 실제
파일 규격을 입력하세요. 결과의 `experience`에서 현재
**5단계 중 단계**, `next_action`과 `next_step_help`,
`outstanding_file_choices`를 확인할 수 있습니다.

파일 후보가 여러 개라면 **한 번에 원본 파일을 직접 선택**하면 됩니다.
자동 매칭이나 승인은 하지 않습니다. `approve_exact_plan` 단계에서는
경로·PDF 페이지·자르기 옵션을 직접 확인하고, 별도의 명시적
실행 승인을 해야만 실제 파일을 생성할 수 있습니다.

최종 검증의 기술 조건 통과는 기관의 접수 완료 증명이
아닙니다. **진행 퍼센트는 단순 단계 위치**이므로 파일 작업의
실시간 완료 비율로 이해하면 안 됩니다.

개인 서류를 사용하지 않고 새 안내의 회귀 테스트를 실행하려면:

```bash
python scripts/first_run_audit_v24.py --check
```

서로 다른 합성 공고 6건의 상태 24개를 검사합니다.
보고서의 가상 질문 절감 수치는 실제 사용자 테스트가 아닙니다.


## 18. 사용 경험 피드백 남기기 (선택 사항, v2.5)

사용자가 직접 요청한 경우에만 로컬 컴퓨터에 저장합니다.
기본적으로 개인정보, 공고 원문, 사용 파일 경로,
자유로운 설명 및 접속 정보는 기록하지 않습니다.

```bash
python scripts/feedback_v25.py preview --stage files \
  --issue file_selection_confusing --impact minor
```

`preview`는 읽기 전용입니다. 아래처럼 사용자가 선택한 **기존
로컬 폴더**에만 별도 `save` 명령으로 저장할 수 있습니다.

```bash
python scripts/feedback_v25.py save --stage files \
  --issue file_selection_confusing --impact minor \
  --output-dir "/EXISTING/PRIVATE/FEEDBACK/FOLDER"
```

```bash
python scripts/feedback_v25.py summary \
  --directory "/EXISTING/PRIVATE/FEEDBACK/FOLDER"
```

5건 미만일 때는 범주별 통계를 표시하지 않고, 작은 범주가
남아 있어도 추가로 숨깁니다. 어떤 출력도 **자동으로 온라인
공유되지 않습니다.** 필요한 경우 사용자가 집계 결과만 검토하여
별도 동의를 받아 공유하세요. 기록 철회는 로컬 파일을 직접
삭제하면 됩니다.

전체 스키마·한계는 `FEEDBACK.md`를 참조하세요.
테스트는 `python scripts/feedback_audit_v25.py --check`로
실행하며, **31개 합성 조건**으로 실제 만족도를 대신할 수 없습니다.


## 19. 피드백 기반 개선 우선순위 확인 (v2.6)

실제 사용자 동의로 직접 수집한 로컬 범주형 피드백이 있을
경우에만 분석할 수 있습니다. 테스트를 위해서는 합성 데이터만
사용하세요.

```bash
python scripts/feedback_insights_v26.py prioritize \
  --directory "/LOCAL/FEEDBACK/BASELINE"
```

```bash
python scripts/feedback_insights_v26.py compare \
  --baseline-directory "/LOCAL/FEEDBACK/BASELINE" \
  --current-directory "/LOCAL/FEEDBACK/CURRENT"
```

각 폴더에는 최소 10개 응답이 필요하며, 소수 의견이 노출될
우려가 있으면 전체 해당 문제 유형 분석을 숨깁니다.
빈도별 정렬이 곧 영향도·개선 우선순위의 객관적인 정답은
아니며, 집단 비교만으로 새 버전의 효과를 증명할 수 없습니다.

테스트 명령:
`python scripts/feedback_insights_audit_v26.py --check`.
이 테스트는 합성 데이터만 생성하고 외부 전송은 하지 않습니다.
자세한 통계 해석과 개인정보 취급은 `RELEASE_NOTES_v26.md`를
참고하세요.

## 20. 강화된 피드백 분석 및 비교 동의 (v2.7 권장)

기존 v2.5 범주형 피드백을 로컬에서 읽기만 합니다.
우선순위는 전체 최소 20건, 비교는 각 폴더 최소 30건이 필요하며
어느 문제 유형에든 1~4건이 있으면 결과를 전부 숨깁니다.

```bash
python scripts/feedback_insights_v27.py prioritize \
  --directory "/EXISTING/LOCAL/FEEDBACK/FOLDER"
```

버전별 피드백 폴더를 사람이 구분해둔 경우에만 다음을 사용하세요.
질문 문구, 모집 방식과 기간 등이 비교 가능한지 먼저 검토해야 합니다.

```bash
python scripts/feedback_insights_v27.py compare \
  --baseline-directory "/EXISTING/BASELINE/FOLDER" \
  --current-directory "/EXISTING/CURRENT/FOLDER" \
  --conditions-comparable
```

마지막 옵션이 없으면 기록을 읽지 않고 비교를 보류합니다. 옵션이
있어도 조건이 실제로 동일했는지 확인하거나 인과관계를 증명하지는
못합니다. 온라인 전송·자동 저장·MCP 도구 추가는 없습니다.

합성 회귀 테스트: `python scripts/feedback_insights_audit_v27.py --check`.
