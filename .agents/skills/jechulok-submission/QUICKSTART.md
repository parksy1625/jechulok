# 제출OK Agent Skill + MCP v0.9 빠른 시작

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
**14개 MCP 도구 목록과 합성 문장 규칙 분석 호출**을 검사할 수 있습니다.

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
