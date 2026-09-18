---
description: 방금 구현한 것을 깨뜨릴 반례를 찾는다
argument-hint: <파일 경로 또는 불변식>
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*), Bash(mvn:*)
---

대상: $ARGUMENTS (비어 있으면 `git diff` 로 최근 변경을 대상으로 삼는다)

`.github/review-prompts/adversary.md` 를 읽고 그 역할을 그대로 수행하라.

추가로, 로컬이므로 다음까지 한다.

- 반례를 찾았으면 그것을 **재현하는 테스트를 실제로 작성해서 실패하는 것을 확인**하라.
  테스트 작성은 허용된다. 프로덕션 코드 수정은 금지다.
- 실패를 확인했으면 테스트만 남기고 멈춰라. 고치는 것은 사용자 몫이다.
- 반례를 못 찾았으면 "찾지 못했습니다" 라고 쓰고, 네가 무엇을 시도했는지 나열하라.
  시도 목록이 있어야 사용자가 네가 안 본 각도를 알 수 있다.
