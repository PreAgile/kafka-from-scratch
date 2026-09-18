# 원본 구현은 어떻게 동작하는가

`reference/com/simplekafka` 전체 코드를 읽고 추적한 결과입니다. 코드를 고치기 전에 "지금 무엇이 일어나는가"를 정확히 붙잡는 것이 목적입니다.

## 전체 규모

| 파일 | 줄 수 | 책임 |
|---|---|---|
| `broker/SimpleKafkaBroker.java` | 1,092 | 소켓 서버, 요청 디스패치, 컨트롤러 선출, 복제 |
| `broker/Partition.java` | 512 | 세그먼트 롤링, append, 인덱스, offset 조회 |
| `broker/Protocol.java` | 371 | 요청/응답 직렬화 |
| `broker/ZookeeperClient.java` | 244 | 브로커 등록, 메타데이터, 워치 |
| `client/SimpleKafkaClient.java` | 210 | 메타데이터 캐시, produce/fetch |
| `client/SimpleKafkaConsumer.java` | 196 | 폴링 루프 |
| `client/SimpleKafkaProducer.java` | 118 | 전송 래퍼 |
| `broker/BrokerInfo.java` | 47 | 브로커 주소 값 객체 |

## 메시지 한 건이 지나가는 경로

프로듀서가 `send("hello")`를 호출했을 때 실제로 일어나는 일입니다.

1. **클라이언트가 메타데이터를 조회한다.**
   `SimpleKafkaClient.refreshMetadata()`가 부트스트랩 브로커에 `METADATA`(0x03) 요청을 보내고, 브로커 목록과 토픽별 파티션의 리더/팔로워를 받아 메모리에 캐시합니다.

2. **클라이언트가 리더 브로커에 직접 붙는다.**
   `SimpleKafkaClient.send()`가 캐시에서 해당 파티션의 리더를 찾아 그 브로커로 TCP 연결을 엽니다. 여기서 이미 Kafka의 핵심 설계 하나가 보입니다. **메타데이터 평면과 데이터 평면이 분리되어 있고, ZooKeeper는 데이터 경로에 전혀 등장하지 않습니다.**

3. **브로커가 요청을 읽는다.**
   `SimpleKafkaBroker.handleClient()`(reference/com/simplekafka/broker/SimpleKafkaBroker.java:519)가 1KB 버퍼로 `read()`를 한 번 호출하고, 읽힌 바이트를 그대로 `processClientMessage()`에 넘깁니다. 첫 바이트가 요청 타입입니다.

4. **리더가 아니면 전달한다.**
   `handleProduceRequest()`는 `targetPartition.getLeader() != brokerId`이면 `forwardProduceToLeader()`로 리더에게 넘깁니다. 클라이언트 메타데이터 캐시가 낡았을 때를 위한 안전망입니다.

5. **로그에 append한다.**
   `Partition.append()`(reference/com/simplekafka/broker/Partition.java:176)가 활성 세그먼트 끝에 `[4바이트 길이][payload]`를 쓰고, `force()`로 디스크에 내린 뒤, 인덱스에 `(offset, position)` 16바이트를 기록하고 `nextOffset`을 1 증가시킵니다.

6. **팔로워에 복제를 던진다.**
   `replicateToFollowers()`가 팔로워마다 스레드 풀에 작업을 제출합니다. 각 작업은 새 TCP 연결을 열고 `REPLICATE`(0x21)를 보낸 뒤 1바이트 ack를 읽어 **로그만 남깁니다.**

7. **클라이언트에 응답한다.**
   6번의 결과를 기다리지 않고 offset을 담은 응답을 바로 보냅니다.

여기서 이미 중요한 사실이 하나 확정됩니다. 6번과 7번의 순서 때문에 **이 구현의 내구성 보장은 항상 `acks=1`입니다.** 팔로워 복제 성공 여부는 클라이언트 응답에 영향을 주지 않습니다.

## 로그 파일은 어떻게 생겼는가

`Partition`이 만드는 디렉터리 구조입니다.

```
{baseDir}/
  00000000000000000000.log     레코드들이 append-only로 쌓임
  00000000000000000000.index   (offset, position) 쌍
  00000000000000010240.log     세그먼트가 1MB를 넘으면 롤링
  00000000000000010240.index
```

파일명이 그 세그먼트의 **베이스 오프셋**입니다. 이 관례 덕분에 디렉터리를 스캔하는 것만으로 세그먼트 목록과 각 세그먼트가 담당하는 offset 구간을 복원할 수 있습니다. 별도의 메타데이터 파일이 필요 없습니다.

`.log` 안의 레코드는 길이 프리픽스만 있습니다.

```
[int32 길이][payload 바이트들][int32 길이][payload 바이트들]...
```

`.index`의 엔트리는 고정 16바이트입니다.

```
[int64 offset][int64 file position]
```

고정 크기라는 점이 핵심입니다. 엔트리 크기가 고정이면 "N번째 엔트리"로 바로 seek할 수 있어서, 인덱스 파일 자체를 이진 탐색할 수 있습니다.

## offset으로 메시지를 찾는 경로

`readMessages(offset, maxBytes)`가 하는 일입니다.

1. `findSegmentForOffset()`: 세그먼트 목록을 베이스 오프셋 기준 이진 탐색해서 해당 세그먼트를 찾습니다.
2. `findPositionForOffset()`: 세그먼트 내 상대 offset을 구하고, 인덱스 파일에서 `상대offset * 16` 위치로 seek해 파일 position을 읽습니다.
3. 그 position부터 길이 프리픽스를 따라가며 `maxBytes`에 닿을 때까지 레코드를 읽습니다.
4. 세그먼트 끝에 닿으면 다음 세그먼트로 넘어가 계속 읽습니다.

원본은 모든 offset에 인덱스 엔트리를 씁니다. 즉 **조밀 인덱스**입니다. 메시지 하나당 인덱스 16바이트가 붙는 셈이고, 이건 실제 Kafka의 sparse index와 다른 선택입니다. 이 차이가 왜 생겼는지는 Level 1에서 직접 측정해 볼 지점입니다.

## 클러스터는 어떻게 자기를 인식하는가

ZooKeeper의 znode 구조입니다.

```
/brokers/{id}          ephemeral. 값은 "host:port". 브로커가 죽으면 자동 소멸
/controller            ephemeral. 값은 컨트롤러 브로커 id
/topics/{name}         persistent. 값은 "파티션수;복제계수"
/topics/{name}/partitions/{id}   persistent. 값은 "리더;팔로워1,팔로워2,"
```

동작은 이렇습니다.

- 기동 시 `registerWithZookeeper()`가 `/brokers/{id}`에 ephemeral 노드를 만듭니다.
- `electController()`가 `/controller`에 ephemeral 노드 생성을 시도합니다. 성공한 하나가 컨트롤러가 됩니다. ZooKeeper의 생성 원자성을 락으로 쓰는 전형적인 패턴입니다.
- `/brokers` 자식 변경 워치가 걸려 있어서, 브로커가 죽으면 `onBrokersChanged()`가 호출되고 컨트롤러가 `rebalancePartitions()`를 돕니다.
- 컨트롤러가 죽으면 ephemeral 노드가 사라지고, 워치를 받은 나머지가 `electController()`를 다시 돕니다.

**ephemeral 노드가 세션 만료 시 자동으로 사라진다는 성질 하나로 장애 감지와 리더십 양도를 동시에 해결한다는 점**이 이 설계의 핵심입니다. 별도의 heartbeat 프로토콜을 만들지 않았습니다.

## 컨슈머는 어떻게 읽는가

`SimpleKafkaConsumer`는 생성자에서 토픽과 파티션을 고정으로 받고, `currentOffset`을 메모리에 들고 폴링합니다. `poll()`은 `fetch(topic, partition, currentOffset, maxBytes)`를 호출하고 받은 개수만큼 offset을 전진시킵니다.

컨슈머 그룹도, offset 커밋도 없습니다. 프로세스를 재시작하면 offset은 생성자에 준 값으로 돌아갑니다. 이게 왜 실제 Kafka에서 `__consumer_offsets`라는 내부 토픽으로 해결됐는지는 Level 3 이후 문서로 다룹니다.

## 읽고 나서 남는 감각

원본이 잘 보여주는 것은 세 가지입니다.

첫째, **로그가 곧 자료구조**라는 것. append-only 파일 하나에서 순서 보장, 재생 가능성, 복제의 단순함이 전부 파생됩니다. DB의 WAL, Raft 로그, 이벤트 소싱이 전부 같은 형태입니다.

둘째, **파일명이 메타데이터**라는 것. 베이스 오프셋을 파일명에 박는 관례 하나로 인덱스 복원 문제가 사라집니다.

셋째, **컨트롤 플레인과 데이터 플레인의 분리**. ZooKeeper는 "누가 리더인가"만 알고 메시지는 지나가지 않습니다. 운영에서 "ZK가 느린데 왜 프로듀서가 멀쩡한가" 또는 그 반대 상황을 진단할 때 쓰는 기준선입니다.

원본이 못 보여주는 것은 [02-missing-features.md](02-missing-features.md)에 정리했습니다.
