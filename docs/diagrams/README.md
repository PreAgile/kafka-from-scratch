# 다이어그램

`.excalidraw` 파일은 [excalidraw.com](https://excalidraw.com)에서 열어 편집합니다. VS Code를 쓴다면 `Excalidraw` 확장을 설치하면 에디터 안에서 바로 열립니다.

**그림을 보는 것이 목적이 아니라 백지에서 다시 그리는 것이 목적입니다.** 각 다이어그램은 설명 없이도 그 개념을 복원할 수 있을 만큼의 정보만 담고, 나머지는 문서에 둡니다.

| 파일 | 다루는 개념 | 관련 문서 |
|---|---|---|
| [01-log-segment-layout](01-log-segment-layout.excalidraw) | 세그먼트 파일 구조, 파일명이 곧 베이스 오프셋, 길이 프리픽스 레코드, 고정 크기 인덱스 엔트리 | [01-how-it-works](../00-analysis/01-how-it-works.md) |
| [02-produce-path](02-produce-path.excalidraw) | 메시지 한 건의 전체 경로, 컨트롤/데이터 플레인 분리, fire-and-forget 복제가 acks=1을 만드는 이유 | [02-missing-features A-2](../00-analysis/02-missing-features.md) |
| [03-isr-high-watermark](03-isr-high-watermark.excalidraw) | LEO와 HW의 차이, ISR 축소가 필요한 이유, acks=all + min.insync.replicas=1의 함정 | [02-missing-features A-3](../00-analysis/02-missing-features.md) |
| [04-leader-epoch-truncation](04-leader-epoch-truncation.excalidraw) | 스플릿 브레인에서 로그가 갈라지는 과정, 에포크 질의와 truncation | [02-missing-features A-4](../00-analysis/02-missing-features.md) |

## 아직 그리지 않은 것

Level이 올라가면서 추가합니다.

- 크래시 복구: 부분 쓰기 지점 탐지와 truncate
- 레코드 배치의 내부 레이아웃과 offset 델타
- 컨트롤러 선출과 ZooKeeper znode 트리
- 결정론적 시뮬레이터의 구조
