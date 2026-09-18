# Kafka from Scratch

Kafka의 로그 엔진과 복제 모델을 바닥부터 구현하면서, 분산 로그 시스템을 백지에서 설명할 수 있는 수준까지 올리는 학습 프로젝트입니다.

`reference/`에 있는 [buildthingsuseful/build-your-own-kafka](https://github.com/buildthingsuseful/build-your-own-kafka) 코드를 교재이자 비교 기준으로 삼습니다. 원본은 약 2,500줄짜리 참조 구현이고, 이 저장소의 작업은 그 코드가 **의도적으로 또는 실수로 빼먹은 것들을 하나씩 채우면서 왜 진짜 Kafka가 그렇게 생겼는지 알아내는 것**입니다.

## 왜 원본을 고치지 않고 다시 만드는가

원본을 읽어보면 단일 브로커 로그 엔진의 뼈대는 제대로 잡혀 있습니다. 세그먼트 롤링, offset 인덱스, ZooKeeper 기반 컨트롤러 선출까지 있습니다.

그런데 조금만 들여다보면 다음이 없습니다.

- 메시지 프레이밍이 없어서 요청이 TCP 경계에서 쪼개지면 깨집니다
- 복제가 fire-and-forget이라 `acks=all`에 해당하는 보장이 존재하지 않습니다
- ISR, High Watermark, 리더 에포크가 없어서 리더 교체 시 커밋된 데이터가 조용히 사라질 수 있습니다
- CRC와 크래시 복구가 없어서 쓰는 중에 죽으면 다음 기동에 깨집니다

이 목록이 곧 커리큘럼입니다. 근거와 코드 위치는 [docs/00-analysis/02-missing-features.md](docs/00-analysis/02-missing-features.md)에 정리해 두었습니다.

## 저장소 구조

```
reference/          원본 참조 구현 (읽기 전용, 수정하지 않음)
docs/
  00-analysis/      원본 동작 추적과 결함 분석
  adr/              설계 결정 기록
  notes/            주차별 학습 노트
  benchmarks/       측정 결과
  diagrams/         Excalidraw 다이어그램
log-engine/         Level 1: 단일 파티션 로그 엔진
broker/             Level 2~3: 프로토콜, 복제
simulation/         결정론적 장애 시뮬레이터
```

## 레벨과 정지선

| 레벨 | 내용 | 기간 | 상태 |
|---|---|---|---|
| 0 | 원본 정독, 동작 추적, 결함 목록화 | 3일 | 진행 중 |
| 1 | 단일 파티션 로그 엔진 재구현 (CRC, 크래시 복구, sparse index, 보존) | 2주 | 대기 |
| 2 | 레코드 배치, 프레이밍, fsync 정책, 성능 측정 | 1주 | 대기 |
| 3 | 복제, ISR, High Watermark, 리더 에포크 | 2주 | 대기 |
| 4 | 컨슈머 그룹, 트랜잭션, 합의 알고리즘 | 하지 않음 | 문서로만 |

Level 4를 구현하지 않는 이유는 [ADR 0002](docs/adr/0002-stop-at-level-3.md)에 적었습니다.

작업 단위는 [이슈](https://github.com/PreAgile/kafka-from-scratch/issues)로 쪼개 두었고, 진행 상황은 [프로젝트 보드](https://github.com/users/PreAgile/projects/4)에서 봅니다. 이슈 하나가 PR 하나에 대응합니다.

## 다이어그램

핵심 개념 네 가지는 `docs/diagrams/`에 Excalidraw로 그려 두었습니다. 보는 것이 목적이 아니라 **백지에서 다시 그리는 것**이 목적입니다.

| 다이어그램 | 다루는 개념 |
|---|---|
| [세그먼트 레이아웃](docs/diagrams/01-log-segment-layout.excalidraw) | 파일명이 곧 베이스 오프셋인 이유, 길이 프리픽스 레코드, 고정 크기 인덱스 |
| [produce 경로](docs/diagrams/02-produce-path.excalidraw) | 메시지 한 건의 전체 경로, fire-and-forget 복제가 acks=1을 만드는 이유 |
| [ISR과 High Watermark](docs/diagrams/03-isr-high-watermark.excalidraw) | LEO와 HW의 차이, acks=all + min.insync.replicas=1의 함정 |
| [리더 에포크](docs/diagrams/04-leader-epoch-truncation.excalidraw) | 스플릿 브레인에서 로그가 갈라지는 과정과 truncation |

## 진행 방식

한 사이클은 이렇게 돕니다.

1. 구현 전에 만들 것을 말로 설명해서 노트에 남깁니다. 그림 포함.
2. 에이전트에게 설계 리뷰만 받습니다. 코드는 받지 않습니다.
3. 테스트를 먼저 씁니다. 불변식을 정의하는 게 핵심입니다.
4. 구현은 직접 합니다.
5. 구현이 끝나면 에이전트에게 "이걸 깨뜨릴 입력과 순서를 찾아라"를 시킵니다.
6. 원본 Kafka 구현과 대조하고 차이를 노트에 남깁니다.

상세 규칙은 [AGENTS.md](AGENTS.md)에 있습니다.

## 리뷰 하네스

혼자 하는 프로젝트의 최대 약점은 "내가 모르는 것을 모르는 상태"입니다. 그걸 메우려고 리뷰 자동화를 붙였습니다.

다만 일반적인 리뷰 봇을 그대로 쓰면 학습이 무너집니다. 봇이 "여기 이렇게 고치세요"를 주면 붙여넣게 되고, 코드는 좋아지고 머리에는 아무것도 안 남습니다. 그래서 모든 리뷰어를 **어긋난 지점을 가리키고 질문만 하도록** 제약했습니다 ([ADR 0004](docs/adr/0004-review-harness.md)).

| 층 | 언제 | 무엇 |
|---|---|---|
| 기계 게이트 | PR마다 | 학습 절차 검사, 빌드, 짧은 시드 스윕 |
| 다관점 AI 리뷰 | PR 열 때 + 코멘트 요청 | Claude(개념 갭) + Codex(불변식 공격) + CodeRabbit(코드 품질) |
| 적대적 검증 | `/adversary` 코멘트 | 반례 사냥 |
| 로컬 커맨드 | 구현 전후 | `/design-review`, `/adversary`, `/explain-check`, `/kafka-diff`, `/second-opinion` |
| 커리큘럼 검토 | 주 1회 | 커리큘럼 자체의 빈틈을 이슈로 |
| 야간 시드 스윕 | 매일 | 2만 시드, 위반 시 이슈 자동 생성 |

리뷰의 주 입력은 diff가 아니라 PR 본문의 **백지 설명**입니다. 코드를 보지 않고 쓴 자기 설명과 실제 코드의 괴리가 곧 자각하지 못한 잘못된 모델입니다.

리뷰어 셋은 계보가 다른 모델이고, 규칙을 읽는 위치도 각각 다릅니다. Claude 는 `.github/review-prompts/`, Codex 는 `AGENTS.md`의 `## Code Review Rules`, CodeRabbit 은 `.coderabbit.yaml` 입니다. 세 곳 모두에 수정안 생성 금지를 박아 두었습니다.

설정 방법과 한계는 [docs/review-harness.md](docs/review-harness.md)에 있습니다.

## 최종 산출물

코드보다 다음 세 가지가 본체입니다.

1. ADR 묶음: 각 결정이 다음 결정을 어떻게 강제했는지의 인과 사슬
2. 불변식 위반 재현 리포트: 리더 에포크 없이 데이터가 사라지는 시드
3. "Kafka를 백지에서 설명하는 문서" 한 편

## 라이선스

`reference/` 아래는 원저작자의 MIT 라이선스를 따릅니다. 나머지는 학습용 개인 작업물입니다.
