#!/usr/bin/env bash
#
# Codex 로 로컬 리뷰를 돌린다. ChatGPT 개인 구독을 쓰므로 API 키가 필요 없다.
#
# codex-action(GitHub Actions 용)은 openai-api-key 만 지원해서 구독으로 못 쓴다.
# 그래서 CI 대신 로컬 CLI 를 쓰고, 결과를 PR 에 올리는 것은 gh 로 따로 한다.
#
# 사용법
#   scripts/codex-review.sh                  현재 브랜치를 main 과 비교해 리뷰
#   scripts/codex-review.sh --uncommitted    커밋 전 작업 트리를 리뷰
#   scripts/codex-review.sh --post 28        리뷰 후 PR #28 에 코멘트로 게시
#
# Codex 는 저장소의 AGENTS.md 를 자동으로 읽는다. 수정안 금지 규칙은
# AGENTS.md 의 "## Code Review Rules" 절에 있으므로 여기서 다시 적지 않는다.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

MODE=(--base main)
POST_PR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --uncommitted) MODE=(--uncommitted); shift ;;
    --base) MODE=(--base "$2"); shift 2 ;;
    --commit) MODE=(--commit "$2"); shift 2 ;;
    --post) POST_PR="$2"; shift 2 ;;
    *) echo "알 수 없는 인자: $1" >&2; exit 2 ;;
  esac
done

command -v codex >/dev/null || { echo "codex CLI 가 없습니다. npm i -g @openai/codex" >&2; exit 1; }

OUT_DIR="${TMPDIR:-/tmp}/kfs-codex-review"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/$(date +%Y%m%d-%H%M%S).md"

PROMPT=$(cat <<'EOF'
저장소의 AGENTS.md 의 "## Code Review Rules" 절을 먼저 읽고 그 규칙을 그대로 따르세요.

이번 리뷰의 초점은 불변식 공격입니다. 다음 순서로 보세요.

1. 이 변경이 주장하는 보장을 먼저 명시적으로 적으세요. 코드와 커밋 메시지에서 추출합니다
2. 각 보장에 대해 그것이 깨지는 구체적인 이벤트 순서를 구성하세요
3. 추측으로 쓰지 말고, 코드의 어느 줄이 그 순서를 허용하는지 가리키세요

공격 축은 크래시 타이밍, 부분 실패, 재시작 후 복구, 동시성, 경계값, 네트워크 재정렬,
리더 교체입니다. 지켜야 할 핵심 불변식은 하나입니다.
커밋된(High Watermark 이하) 메시지는 어떤 리더 교체 후에도 사라지지 않는다.

수정안을 쓰지 마세요. 반례와 질문만 가져오세요.
반례를 못 찾았으면 못 찾았다고 쓰고 무엇을 시도했는지 나열하세요.
"확실히 깨진다" 와 "깨질 것 같은데 확인이 필요하다" 를 구분해서 쓰세요.
EOF
)

echo "Codex 리뷰 실행: ${MODE[*]}"
printf '%s' "$PROMPT" | codex review "${MODE[@]}" - | tee "$OUT"

echo
echo "저장 위치: $OUT"

if [ -n "$POST_PR" ]; then
  command -v gh >/dev/null || { echo "gh 가 없어 게시를 건너뜁니다." >&2; exit 0; }
  {
    echo "## Codex 적대적 검증 (로컬 CLI, ChatGPT 구독)"
    echo
    cat "$OUT"
  } | gh pr comment "$POST_PR" --body-file -
  echo "PR #$POST_PR 에 게시했습니다."
fi
