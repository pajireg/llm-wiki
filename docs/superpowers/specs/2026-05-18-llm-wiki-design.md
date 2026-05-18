# llm-wiki: LLM이 유지하는 개인 위키 시스템 — 설계

- 작성일: 2026-05-18
- 영감: [Karpathy — LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- 상태: 설계 확정 (구현 계획 미작성)

## 1. 목적과 비범위

### 목적

Karpathy의 "LLM이 유지하는 위키" 패턴을 사용자의 통합 지식 시스템으로 구체화. 인간은 소스 큐레이션·질문·방향만 담당하고, LLM이 페이지 생성·교차참조·일관성 유지를 맡는다.

도메인은 통합형: 개인 지식, 개발 활동, 회사 프로젝트, 기술 학습, 인물·도구 등. 도메인 간 격리는 namespace로.

### 산출물

이 시스템은 **두 개의 git 레포**로 분리되어 산출된다:

| 레포 | 가시성 | 내용 |
|---|---|---|
| **`llm-wiki`** | public | Claude Code 플러그인: 명령, 스킬, 훅, schema 템플릿 |
| **사용자 vault** (이름·git화는 사용자 자유) | private 권장 | 사용자 콘텐츠: `sources/`, `wiki/`, `lint-reports/`, 소유한 `schema/` |

> 플러그인은 vault 디렉터리 이름·위치와 무관하게 동작한다. `/wiki-init`은 *현재 작업 디렉터리*를 vault로 부트스트랩한다. 이 사용자의 경우 `~/Vaults/wiki/`로 정했고, 본 문서에서는 그 가정 하에 경로를 표기한다.

### 비범위 (이번 스펙에 포함되지 않음)

- SQLite 인덱스, 그래프 DB, 임베딩 검색 — *나중에 마크다운 위에 얹는 파생물* (§7 진화 경로).
- 이벤트 소싱 — git 히스토리가 그 역할.
- 다국어 i18n — 영문 README + 한글 본문 혼용 허용. 본격 i18n 분리는 나중.
- Obsidian 플러그인(TypeScript) 형태 — 본질이 Claude Code 명령이라 불일치.
- 위키 자체의 웹 UI — Obsidian이 UI.

## 2. 핵심 원칙 (Day-1 엄격 적용)

이 원칙들은 처음부터 어기지 않는다. 각각 어겼을 때 나중에 복구 비용이 크다.

1. **3계층 분리**: Sources (불변) / Wiki (LLM 합성) / Schema (LLM 규칙). 셋의 책임이 섞이면 안 된다.
2. **Sources는 절대 수정하지 않는다**. 잘못된 원본은 새 source로 정정(`supersedes`)하지, 기존 것을 고치지 않는다.
3. **모든 wiki 페이지는 `sources:` 참조를 가진다**. 출처 잃은 정보는 무가치. frontmatter에서 강제.
4. **frontmatter가 권위적 진실**. 모든 인덱스·뷰·린팅은 frontmatter 기반. day-1 스키마는 마이그레이션 비용이 크므로 신중히 박는다.
5. **Schema는 LLM이 매번 컨텍스트에 로드**. 규칙이 글로 박혀 있어야 LLM이 일관됨.
6. **두 레포 분리는 day-1부터**. 플러그인 레포에서 명령·스킬·훅·schema 템플릿. vault 레포에서 콘텐츠. 섞이면 분리 비용 큼.
7. **린팅은 처음부터**. 빚이 쌓이기 전에 시작.

## 3. 아키텍처

### 3계층 매핑

| 계층 | 역할 | 위치 |
|---|---|---|
| Sources | 불변 원본 — 진실의 출처 | vault `sources/` |
| Wiki | LLM이 쓰고 유지하는 합성 페이지 | vault `wiki/<namespace>/` |
| Schema | LLM의 작동 규칙 | vault `schema/` (`llm-wiki/templates/schema/`에서 복사됨) |

### 플러그인 레포 (`llm-wiki`) 구조

```
llm-wiki/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── wiki-init.md
│   ├── wiki-ingest.md
│   ├── wiki-ask.md
│   ├── wiki-lint.md
│   └── wiki-upgrade-schema.md
├── skills/
│   └── llm-wiki/
│       └── SKILL.md           # 위키 운영 원칙·체크리스트
├── hooks/
│   └── session-end-capture.sh # SessionEnd 훅 스크립트
├── templates/
│   ├── schema/                # 초기 schema 6개 파일 (vault로 복사됨)
│   │   ├── README.md
│   │   ├── page-types.md
│   │   ├── relations.md
│   │   ├── namespaces.md
│   │   ├── ingest-rules.md
│   │   └── lint-rules.md
│   ├── gitignore.template
│   └── README.template.md
├── scripts/
│   └── install.sh             # 글로벌 훅 등록 도우미
├── README.md                  # "Memex realized with LLMs."
└── LICENSE
```

### Vault 구조 (이 사용자: `~/Vaults/wiki/`)

```
wiki/
├── .obsidian/                  # Obsidian 설정 + Bases 뷰
├── .claude/                    # vault 로컬 명령·설정 (선택)
│
├── schema/                     # 계층 3: 사용자 소유, 자유 수정
│   ├── README.md
│   ├── page-types.md
│   ├── relations.md
│   ├── namespaces.md           # cwd→namespace 매핑 (사용자 환경별)
│   ├── ingest-rules.md
│   └── lint-rules.md
│
├── sources/                    # 계층 1: 불변
│   ├── claude-sessions/        # SessionEnd 훅이 자동 저장
│   ├── manual/                 # 사용자가 직접 떨어뜨림
│   └── conversations/          # 외부 채팅 import (선택)
│
├── wiki/                       # 계층 2: LLM 합성
│   ├── personal/
│   ├── work/
│   ├── tech/
│   ├── projects/
│   └── people/                 # cross-cutting
│
├── lint-reports/               # YYYY-MM-DD-lint.md
└── README.md
```

## 4. 데이터 모델

### 4.1 페이지 타입 (5종)

| 타입 | 역할 | 파일명 패턴 |
|---|---|---|
| `topic` | 진화하는 개념·주제. 위키의 *주력*. | `<slug>.md` (한글 slug 허용) |
| `entity` | 인물·도구·회사·프로젝트. 안정. | `<이름-slug>.md` |
| `note` | 날것의 관찰·통찰. 미합성 상태. | `<YYYY-MM-DD>-<slug>.md` |
| `source` | 원본 메타 (sources/ 안). | `<YYYY-MM-DD>-<slug>.md` |
| `question` | 미해결, 후속 탐구거리. | `q-<slug>.md` |

ingest 시 LLM은 *반드시* 이 5종 중 하나로 분류. 모호하면 가장 가까운 것 + `confidence: low` 표시.

### 4.2 공통 Frontmatter (모든 페이지 필수)

```yaml
---
type: topic | entity | note | source | question
namespace: personal | work | tech | projects | people
created: 2026-05-18
updated: 2026-05-18
sources:
  - "[[2026-05-18-claude-session-debugging]]"   # wiki 페이지는 1개 이상 필수
tags: [optional]
---
```

> `sources:`가 비어있는 wiki 페이지는 린팅이 적발 — 출처 불명은 무가치.

### 4.3 타입별 추가 Frontmatter

**topic**
```yaml
aliases: ["다른 이름1", "다른 이름2"]
related:     ["[[other-topic]]"]
contradicts: ["[[other-topic]]"]
part_of:     ["[[parent-topic]]"]
supersedes:  ["[[old-topic]]"]
```

**entity**
```yaml
kind: person | tool | company | project | other
aliases: [...]
related: [...]
```

**note**
```yaml
topics: ["[[topic-this-belongs-to]]"]
related: [...]
confidence: high | medium | low
```

**source** (sources/ 폴더 내)
```yaml
source_type: claude_session | article | book | conversation | other
ingested_at: 2026-05-18T14:32:00
url: "https://..."          # 있으면
processed: false            # /wiki-ingest 후 true
session_id: <uuid>          # claude_session인 경우
cwd: /path                  # claude_session인 경우
```

**question**
```yaml
topics: ["[[related-topic]]"]
status: open | investigating | answered | abandoned
answered_by: ["[[topic-or-note]]"]   # status=answered일 때
```

### 4.4 관계 타입 (5종)

| 관계 | 의미 | 방향 |
|---|---|---|
| `related` | 약한 연관 | 양방향 권장 |
| `part_of` | 위계, A가 B에 포함 | 단방향 (A → B) |
| `contradicts` | 모순. 린팅이 강조 | 양방향 |
| `supersedes` | A가 B를 대체. B는 보존 후 표시 | 단방향 (A → B) |
| `derived_from` | wiki 페이지 → source (`sources:`로 대체 가능) | 단방향 |

LLM은 본문 wikilink(`[[X]]`) 외에 *의미 있는* 관계는 반드시 frontmatter 필드에 명시. 본문 wikilink = "언급", frontmatter = "의미 관계".

### 4.5 Namespace 규칙

```yaml
# schema/namespaces.md 핵심

namespaces:
  personal: { allow_links_to: [all] }
  work:     { allow_links_to: [all] }     # 회사 정책 제약 없음 — 일반 namespace로
  tech:     { allow_links_to: [all] }
  projects: { allow_links_to: [all] }
  people:   { allow_links_to: [all] }     # cross-cutting

# source의 namespace와 그것이 합성된 wiki 페이지의 namespace는 일관 유지
# 예외: people/ 페이지는 어느 namespace source든 참조 가능
```

**Source → namespace 자동 추정** (자동 캡처용 cwd 매핑):

```yaml
# 실제 매핑은 사용자 환경에 맞게 /wiki-init 후 사용자가 채움
# 템플릿은 빈 표 + 주석 예시만 제공
cwd_to_namespace:
  # "/Users/<you>/Vaults/wiki/**": personal
  # "/Users/<you>/projects/**":     tech
  # "/Users/<you>/work/**":         work
  default: personal
```

## 5. 워크플로우

### 5.1 `/wiki-init` — vault 부트스트랩

호출: 빈 디렉터리에서 1회.

동작:
1. 디렉터리 구조 생성 (`schema/`, `sources/<3>`, `wiki/<5 namespaces>`, `lint-reports/`)
2. 플러그인 `templates/schema/` → vault `schema/` 복사
3. `templates/README.template.md` → vault `README.md`
4. `templates/gitignore.template` → vault `.gitignore`
5. 안내 출력: "git으로 관리하려면 `git init && git remote add ...` 실행하세요" (강제 X)
6. 사용자에게 `schema/namespaces.md`의 cwd 매핑 작성 안내

### 5.2 자동 캡처 (passive) — SessionEnd 훅

설정: `~/.claude/settings.json` (글로벌)의 SessionEnd hook으로 `llm-wiki/hooks/session-end-capture.sh` 등록. 모든 Claude Code 세션을 캡처하는 것이 의도이므로 vault-local 설정이 아니라 global 등록.

동작 (LLM 호출 0):
1. 세션 transcript 추출
2. cwd 검사 → `schema/namespaces.md`의 매핑으로 namespace 추정
3. `<vault>/sources/claude-sessions/<YYYY-MM-DD>-<slug>.md`로 저장
4. frontmatter: `type: source`, `source_type: claude_session`, `processed: false`, `cwd`, `session_id`

대상: **모든 Claude Code 세션** (옵션 B 확정). 매핑이 없으면 `personal`로 폴백.

> 훅 스크립트는 셸 스크립트로 단순. LLM 호출 없으므로 토큰 비용 0. 노이즈는 ingest 단계 또는 사용자가 source 삭제로 필터링.

### 5.3 `/wiki-ingest` — 합성 (active)

호출:
- 명시: `/wiki-ingest <source-path>` 또는 `/wiki-ingest --recent <duration>`
- 자연어: "어제 작업한 거 위키에 정리해줘"

LLM 동작 (순서):
1. `schema/*` 전체 로드
2. 대상 source 읽기 → namespace 확인
3. 관련 페이지 식별 (검색: Obsidian search + grep + frontmatter 매칭)
4. 합성 결정 — 기존 topic/entity 갱신 vs 새 topic 생성 vs note 임시 저장
5. 새 question 떠올랐으면 별도 생성
6. 변경 적용. 모든 갱신 페이지에 `sources: [[<this-source>]]` 추가
7. source 마킹: `processed: true`, `updated:` 갱신
8. (git 저장소면) commit (의미 있는 메시지)
9. 요약 출력: touch한 페이지 N개

### 5.4 `/wiki-ask` — 쿼리

호출: `/wiki-ask <질문>` 또는 자연어.

LLM 동작:
1. 위키 내 검색 → 관련 페이지 컨텍스트 로드 (topic 우선)
2. 답변 생성 — 각 주장에 page wikilink 인용
3. 답변이 새로운 통찰이면 사용자에게 "이걸 note로 저장할까요?" 제안 (자동 저장 X, 사용자 승인 후)

### 5.5 `/wiki-lint` — 점검

호출: 수동 (`/wiki-lint`) 또는 자연어. 자동 cron 없음.

점검 8가지:
1. 미처리 source 백로그 (`processed: false`)
2. 중복 후보 (제목·aliases·유사도)
3. 고아 페이지 (참조 0)
4. 깨진 wikilink
5. 모순 마커 (`contradicts:` 설정된 페이지)
6. 방치된 question (`status: open`, N일 이상)
7. frontmatter 위반 (필수 필드 누락, type 미정의 값)
8. `sources:` 누락된 wiki 페이지

출력: `lint-reports/<YYYY-MM-DD>-lint.md`. **자동 수정 X**. 단순 정정은 사용자가 "고쳐줘" 후속 호출.

### 5.6 `/wiki-upgrade-schema` — 스키마 진화

호출: 플러그인 업그레이드 후 사용자가 명시 호출 시.

LLM 동작:
1. 플러그인의 `templates/schema/`와 vault `schema/` 비교
2. diff를 보여주고 사용자에게 선택적 머지 권한
3. **vault의 schema는 사용자가 소유** — 자동 덮어쓰기 절대 X

## 6. 설치·운영

### 6.1 설치 흐름 (사용자 관점)

```bash
# 1회: 플러그인 설치
/plugin install <github-url-of-llm-wiki>

# 1회: vault 초기화 (이름·위치는 사용자 자유)
mkdir ~/Vaults/wiki && cd ~/Vaults/wiki   # 이 사용자의 선택
claude
> /wiki-init                              # 현재 디렉터리를 vault로 부트스트랩

# 1회: (선택) git 관리 시작
git init
git remote add origin <your-private-repo>
git add . && git commit -m "init"
git push -u origin main

# 1회: SessionEnd 훅 활성화 (사용자 승인 후 scripts/install.sh가 안내)

# 상시 사용
> /wiki-ingest <source>
> /wiki-ask <question>
> /wiki-lint
```

### 6.2 Git 정책

| 항목 | 동작 |
|---|---|
| `git init` 여부 | 사용자 선택. `/wiki-init`은 안내만 |
| 자동 commit | git 저장소면 ingest/lint 후 LLM이 commit. 아니면 skip |
| remote push | 사용자 책임. 플러그인 관여 X |
| 백업 | git remote에 push하면 자연 백업 |

### 6.3 분리 원칙

| 항목 | 위치 |
|---|---|
| 코드 (명령·스킬·훅) | 플러그인 레포 |
| schema 템플릿 원본 | 플러그인 `templates/schema/` |
| 사용자가 실제 쓰는 schema | vault `schema/` |
| 콘텐츠 (sources/wiki/lint-reports) | vault 레포 |

플러그인 업그레이드는 vault를 절대 건드리지 않는다.

## 7. 진화 경로

```
[Phase 1: day-1 ~ 페이지 ~500]
  마크다운 + frontmatter + grep + Obsidian 검색

[Phase 2: 페이지 500~2000]
  Obsidian Bases 뷰 본격 활용 (type·namespace·미답 question·미처리 source 등)
  frontmatter 인덱스가 이미 차 있으므로 추가 비용 0

[Phase 3: 페이지 2000+]
  SQLite 인덱스 빌더 추가 — frontmatter를 표 형태로 쿼리
  마크다운이 여전히 진실의 원천, SQLite는 파생물

[Phase 4: 그래프 분석 필요]
  Neo4j 또는 임베딩 벡터 DB. frontmatter relations 덕에 마이그레이션 수월
```

마크다운 + frontmatter가 권위적 진실. 위에 얹는 모든 인덱스는 *파생물* — 데이터 손실 없이 phase 전환 가능.

## 8. 미해결·후속

- **세션 노이즈 필터링**: 사소한 세션도 모두 캡처됨. 6개월 정도 운용 후 패턴 보고 훅에 필터 추가 검토.
- **공개 README 다국어**: 영문 우선. 한글 README는 후속.
- **다른 사용자 vault**: 이번 스펙은 사용자 본인의 vault에 집중. 다른 사람이 `/plugin install` 후 잘 동작하는지 검증은 별도 단계.
- **사용자 환경 cwd 매핑**: `/wiki-init` 후 사용자가 실제 디렉터리 구조에 맞게 `schema/namespaces.md` 채워야 함. 첫 사용 마찰 포인트.

## 9. 다음 단계

이 스펙 사용자 검토 → `writing-plans` 스킬로 구현 계획 작성.

구현 순서 예상:
1. 플러그인 레포 (`llm-wiki`) 초기 골격
2. `wiki-init` 명령 + schema 템플릿 6개
3. SessionEnd 훅
4. `wiki-ingest`
5. `wiki-ask`
6. `wiki-lint`
7. `wiki-upgrade-schema`
8. README + LICENSE
