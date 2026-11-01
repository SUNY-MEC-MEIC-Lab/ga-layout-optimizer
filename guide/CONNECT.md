# 설치 · 연결 — Claude Code · Claude Desktop · Codex · ChatGPT · 브라우저

[← README](../README.md) · [구조](ARCHITECTURE.md) · [결과 상세](RESULTS.md) · [벤치마크](BENCHMARKS.md) · [한계](LIMITATIONS.md)

## 공통 — 요구사항

- **Python 3.8+ 만.** 엔진·파서·MCP 서버 모두 표준 라이브러리만 쓴다. `pip install` 할 것이 없다.

  ```bash
  conda create -y -n ga-layout python=3.11     # 서드파티 0개인 상태가 정상이다
  conda activate ga-layout
  python tests/run_all.py
  ```

  엔진에 서드파티 의존성을 추가하는 변경은 아래 폐쇄망 조항을 먼저 개정한 뒤에만 한다.
- **엔진은 외부 네트워크 불필요.** 폐쇄망에서 `git clone` 만으로 설치된다.
  단, **로컬인 것은 엔진뿐이다** — 어떤 LLM 클라이언트(Claude·ChatGPT)를 쓰든 도구 응답(기기 이름·치수·결과)은
  그 LLM 서비스로 전송된다. 실제 설계값을 넣지 말 것 ([한계](LIMITATIONS.md) 18항).

## Claude Code — 플러그인 (MCP 서버 자동 등록)

```bash
git clone https://github.com/hajun011103/ga-layout-optimizer.git smr-ga-plugin
# Claude Code 안에서
/plugin marketplace add ./smr-ga-plugin
/plugin install smr-ga@smr-ga-marketplace
```

플러그인·MCP 서버 식별자(`smr-ga`)는 초기 이름 그대로다 — 바꾸면 설치된 환경의 도구 이름이 깨진다.

| 명령 | 단계 |
|---|---|
| `/smr-ga:ga-layout` | 스킬 — 전체 진행 (도면 경로 / 자연어 경로) |
| `/smr-ga:ga-import` | 도면 → 현황 배치 → 프로젝트 |
| `/smr-ga:ga-spec` | 자연어 → IR 초안 |
| `/smr-ga:ga-check` | Gate 1 검증 + 동결 |
| `/smr-ga:ga-run` | 최적화 + 도면 |
| `/smr-ga:ga-explain` | 해설 (읽기 전용) |
| `/smr-ga:ga-studio` | 브라우저 스튜디오 + 원격 MCP 엔드포인트 |

플러그인의 [`.mcp.json`](../.mcp.json) 이 MCP 서버 `smr-ga` 를 등록한다 (도구 18개, `ga_*` —
목록은 [구조](ARCHITECTURE.md) 3절).

## Claude Desktop

`claude_desktop_config.json`:

```json
{ "mcpServers": { "smr-ga": { "command": "python3",
    "args": ["/절대경로/smr-ga-plugin/server/mcp_server.py"] } } }
```

## Codex CLI (OpenAI)

`~/.codex/config.toml`:

```toml
[mcp_servers.smr-ga]
command = "python3"
args = ["/절대경로/smr-ga-plugin/server/mcp_server.py"]
```

규약은 [`AGENTS.md`](../AGENTS.md) 에 있다. Codex 는 이 파일만 읽으면 Claude 와 같은 워크플로가 동작한다.

## ChatGPT 웹 · Claude.ai 웹 (원격 MCP 커넥터)

웹 서비스는 **공개 HTTPS 주소의 MCP 서버**만 붙는다. 이 컴퓨터에서 서버를 띄우고 터널로 연다.

```bash
TOKEN=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
cloudflared tunnel --url http://127.0.0.1:8765          # → https://<무작위>.trycloudflare.com
python3 server/mcp_server.py --http --port 8765 --token "$TOKEN" \
        --public-url https://<무작위>.trycloudflare.com
```

| 서비스 | 등록 위치 | 입력할 URL |
|---|---|---|
| ChatGPT (개발자 모드) | 설정 → 앱·커넥터 → 고급 → 개발자 모드 켜기 → 커넥터 만들기 · 인증 "없음" | `https://<무작위>.trycloudflare.com/t/<TOKEN>/mcp` |
| Claude.ai | 설정 → 커넥터 → 사용자 지정 커넥터 추가 | 같은 URL |

- 토큰은 URL 경로(`/t/<TOKEN>/…`) 또는 `Authorization: Bearer` 로 검사한다. **URL 을 아는 사람은 누구나 쓸 수 있으니** 쓰고 나면 서버와 터널을 끈다.
- 웹 LLM 은 사용자 컴퓨터 파일을 서버에 직접 넘기지 못한다 → `ga_upload_link` 가 주는 **스튜디오 업로드 페이지**에서 올리고, 나온 `file_id` 를 대화에 붙여 넣는다. 다운로드 URL 이 있는 파일은 `url` 인자로 바로 넘길 수 있다.
- 원격 모드에서는 서버 로컬 경로 읽기가 기본으로 막혀 있다 (`--allow-local-paths` 로만 허용).
- **원격 연결 = 도면과 결과가 OpenAI/Anthropic 서비스로 전달된다.** 폐쇄망·실제 설계값에는 쓰지 말 것.
  각 서비스의 메뉴 이름과 요금제별 제공 여부는 바뀔 수 있다 — 연결이 안 되면 해당 서비스 도움말의 "MCP 커넥터" 항목을 확인할 것.

## 브라우저 스튜디오 (LLM 없이)

```bash
python3 server/mcp_server.py --http      # → http://127.0.0.1:8765/studio
```

스튜디오는 LLM 클라이언트와 **같은 MCP 도구**를 호출한다. 오른쪽 패널에 호출 기록이 남는다.

## CLI 만으로 (IR 경로)

```bash
# 1) 검증 (Gate 1)
python3 engine/validate_spec.py examples/spec_smr_aux.json

# 2) 동결
python3 engine/validate_spec.py examples/spec_smr_aux.json --freeze

# 3) 최적화 + 도면
python3 engine/run.py examples/spec_smr_aux.json --iters 60000 --restarts 6

# 층수 민감도 스윕
python3 engine/run.py examples/spec_smr_aux.json --sweep-floors 1-6

# 다목적 Pareto — 가중치를 미리 정하지 않는다
python3 engine/run.py examples/spec_smr_aux.json --mode nsga --pop 80 --gens 80

# 음성 대조군 — 이 명령은 반드시 거부되어야 한다 (종료코드 1)
python3 engine/run.py examples/spec_infeasible.json

# 도면 → 현황 배치 (MCP 없이)
python3 engine/takeoff.py <도면…> --units mm --out work/
```

종료코드: `0` 정상 · `1` Gate 1 불통과(실행 안 함) · `2` hard 제약 위반 잔존.

## 3D 비교 페이지 다시 만들기

```bash
python3 tools/make_viewer_data.py     # docs/data.js
python3 tools/make_bench_data.py      # docs/bench.js
```

실제 도면 2건(클리닉·연구소 IFC)은 저장소에 넣지 않았다. `bench/real/public/` 아래에 받아 두면 포함된다
([결과 상세](RESULTS.md) 3절).
