# 제출OK Agent Skill + MCP v1.6 빠른 시작

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
