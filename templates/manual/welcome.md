---
type: source
source_type: manual
namespace: personal
processed: false
---

# llm-wiki 시작하기

이 노트는 vault 부트스트랩 시 자동으로 포함된 첫 source입니다. 이걸 ingest해서 첫 합성을 체험해보세요:

```
/llm-wiki:ingest sources/manual/welcome.md
```

ingest가 끝나면 `wiki/personal/`에 이 문서로부터 합성된 페이지들이 생성됩니다. 그 다음 `/llm-wiki:ask "큐레이션 루프가 뭐야"` 같은 질의를 던지면 자신의 위키에서 답이 돌아오는 흐름을 직접 확인할 수 있습니다.

## 큐레이션 루프

llm-wiki는 세 단계로 돕니다:

1. **자동 수집** — Claude Code 세션이 끝날 때마다 transcript가 `sources/claude-sessions/`에 markdown으로 저장됩니다. 설정 없이 동작.
2. **수동 합성** — 모인 source를 `/llm-wiki:ingest`로 위키 페이지(`wiki/<namespace>/`)에 합성합니다. LLM이 기존 페이지를 갱신하거나 새로 만들고, 관계와 인용을 자동으로 관리합니다.
3. **질의 / 점검** — `/llm-wiki:ask`로 위키 기반 답변을 받고, 주기적으로 `/llm-wiki:lint`로 깨진 링크·고립 페이지·중복·미처리 source를 점검합니다.

## 5가지 페이지 타입

- **topic** — 진화하는 개념이나 주제 (예: "retrieval-augmented generation", "결정 일지 작성법")
- **entity** — 사람·도구·회사 (예: "Claude Code", "anthropic")
- **note** — 미가공 관찰이나 요약. topic이 되기 전 단계
- **source** — 원본. immutable. 이 파일이 source입니다
- **question** — 미해결 질문. 답이 누적되면 추후 topic으로 승격

## 5가지 관계

frontmatter에 wikilink 배열로 저장합니다:

- `related` — 느슨한 연관
- `part_of` — 포함 관계 (자식 → 부모)
- `contradicts` — 충돌하는 주장
- `supersedes` — 오래된 페이지를 대체
- `derived_from` — 다른 페이지에서 도출됨

## 5가지 네임스페이스

`wiki/<namespace>/`로 분리됩니다:

- `personal` — 개인 노트
- `work` — 업무 맥락
- `tech` — 기술 일반
- `projects` — 특정 프로젝트
- `people` — 사람 페이지

자동 분류 규칙은 `schema/namespaces.md`의 `git_owner_to_namespace`와 `cwd_to_namespace`에서 정의합니다. 비어있는 상태로 시작해도 동작하며, 사용하면서 채워나가면 됩니다.

## 핵심 불변식

1. `sources/`는 immutable — `processed:`와 `updated:` flag 외엔 손대지 않습니다
2. 모든 위키 페이지는 비어있지 않은 `sources:` frontmatter를 가집니다 (출처 없는 정보 없음)
3. frontmatter가 진실의 출처입니다
4. `schema/`는 사용자 소유 — 플러그인이 자동 덮어쓰지 않습니다
5. git 자동 커밋은 vault가 git repo일 때만

## 다음에 할 일

- `schema/namespaces.md`를 열어 자신의 git owner → namespace 매핑을 추가하세요
- 자주 쓰는 메모를 `sources/manual/`에 markdown 파일로 떨어뜨려두면, 다음 ingest에서 흡수됩니다
- 30개쯤 페이지가 쌓이면 vault 디렉터리를 Obsidian으로 열어보세요 — 그래프 뷰가 위키 구조를 시각화합니다

Karpathy의 LLM wiki 패턴에서 영감을 받았습니다: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
