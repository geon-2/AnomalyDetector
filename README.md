# 로그 이상 탐지 시스템 (Log Anomaly Detection System)

마이크로서비스 아키텍처 기반의 실시간 로그 이상 탐지 및 분석 시스템입니다.

HDFS, Hadoop, OpenStack 등 다양한 분산 시스템 환경에서 발생하는 로그를 수집하고, 딥러닝 모델을 통해 이상 패턴을 자동으로 감지합니다.

## 프로젝트 구조

```
AnomalyDetector/
├── services/
│   ├── log-collector/      # 로그 수집 및 파싱
│   ├── normalizer/          # 로그 정규화 및 벡터화
│   ├── detector/            # 이상 탐지 (GRU AutoEncoder)
│   ├── visualizer/          # 결과 시각화 API
│   └── llm-service/         # 이상 로그 설명 생성
├── k8s/                     # Kubernetes 배포 설정
├── training/                # 모델 학습 노트북
├── models/                  # 학습된 모델 파일
├── data/                    # 학습 및 테스트 데이터
└── Makefile                 # 빌드/배포 자동화
```

## 아키텍처 설계

### 1. 마이크로서비스 구조

이 프로젝트는 5개의 독립적인 서비스로 구성되어 있습니다. 각 서비스를 분리한 이유는 다음과 같습니다:

**Log Collector**
- 역할: 로그 파일을 읽고 Drain3 알고리즘으로 템플릿 추출
- 설계 근거: 로그 파싱은 CPU 집약적 작업이므로 독립적으로 스케일 가능하도록 분리

**Normalizer**
- 역할: 추출된 템플릿을 이벤트 시퀀스로 변환하고 벡터화
- 설계 근거: 도메인별 전처리 로직이 다를 수 있어 독립 서비스로 구현

**Detector**
- 역할: GRU AutoEncoder 모델로 시퀀스 이상 탐지
- 설계 근거: GPU 리소스가 필요한 추론 작업을 별도 Pod으로 관리

**Visualizer**
- 역할: 탐지 결과를 집계하고 REST API로 제공
- 설계 근거: 프론트엔드와 백엔드 로직 분리, 추후 UI 확장 용이

**LLM Service**
- 역할: 이상 로그에 대한 설명과 대응 방안 생성
- 설계 근거: 실시간 설명 생성을 위해 경량 룰 기반 시스템으로 구현 (LLM 모델 로딩 오버헤드 제거)

### 2. 통신 방식

Kafka를 사용하지 않고 HTTP REST API로 통신하는 이유:
- 학습 목적의 프로젝트로 인프라 복잡도 최소화
- 각 서비스 간 처리 속도가 충분히 빨라 비동기 큐 불필요
- Kubernetes 서비스 디스커버리만으로 충분한 안정성 확보

## 핵심 구현 내용

### 1. Multi-Domain 학습 전략

초기에는 HDFS 데이터만 사용했으나, 다음 문제가 발생했습니다:
- 정상 로그 33개 vs 이상 로그 1개 (심각한 클래스 불균형)
- 모델이 모든 로그를 이상으로 판단 (Accuracy 49.95%, Recall 100%)

**해결 방법:**
1. **도메인 확장**: HDFS, Hadoop, OpenStack 데이터 통합 학습
2. **데이터 증강**: 5가지 기법 적용
   - Noise Injection (10% 확률로 랜덤 이벤트 삽입)
   - Permutation (일부 순서 변경)
   - Truncation (시퀀스 길이 축소)
   - Duplication (이벤트 중복)
   - Substitution (동일 도메인 내 이벤트 교체)
3. **도메인 인식 Vocabulary**: `HDFS_E1`, `Hadoop_E2` 형태로 충돌 방지

결과: 클래스 비율 11:1로 개선, Accuracy 93.41%, Precision 92.95%

### 2. GRU AutoEncoder 모델

RNN 기반 AutoEncoder를 선택한 이유:
- 로그는 시간 순서가 중요한 **시퀀스 데이터**
- LSTM보다 GRU가 학습 속도가 빠르고 파라미터가 적음
- AutoEncoder는 정상 패턴을 학습하여 **비정상 패턴을 높은 재구성 오차로 감지**

```
Input Sequence → GRU Encoder → Latent Vector → GRU Decoder → Reconstructed Sequence
                                                    ↓
                                            Reconstruction Loss
                                                    ↓
                                        Threshold 기반 이상 판단
```

### 3. 임계값(Threshold) 조정

초기 모델의 threshold 0.000221은 너무 낮아서 모든 정상 로그를 이상으로 판단했습니다.

**조정 과정:**
1. Validation set에서 정상/이상 로그의 loss 분포 분석
2. Threshold를 0.003000으로 13.5배 상향 조정
3. 결과: 정상 로그 정확도 대폭 개선

**교훈**: Validation set을 반드시 확인하고 실제 분포에 맞게 threshold 설정 필요

### 4. LLM Service 재설계

초기에는 Meta-Llama-3 모델을 로딩하여 스키마 생성 후 LLM 추론을 수행했으나:
- 모델 로딩에 16GB+ 메모리 필요
- 초기 로딩 시간 5분 이상 소요
- 실시간 설명 생성 불가능 (추론 시간 10초+)

**개선 방안:**
- 룰 기반 패턴 매칭 시스템으로 전환
- 로그 메시지에서 키워드 감지 (block, connection, disk, mapreduce 등)
- 패턴별 사전 정의된 설명과 대응 방안 제공
- 응답 시간 1ms 미만, 메모리 사용량 50MB 이하

실무에서는 LLM이 유용하지만, 프로토타입 단계에서는 경량 솔루션이 더 적합하다고 판단했습니다.

## 실행 가이드

### 사전 준비

1. **Minikube 설치 및 시작**
   ```bash
   minikube start --memory=4096 --cpus=4
   eval $(minikube docker-env)
   ```

2. **저장소 클론**
   ```bash
   git clone <repository-url>
   cd AnomalyDetector
   ```

### 빌드 및 배포

Makefile을 통해 모든 작업을 자동화했습니다:

```bash
# 1. 모든 Docker 이미지 빌드
make build

# 2. Kubernetes에 배포
make deploy

# 3. Pod 상태 확인
make status
```

### 테스트 실행

```bash
# 1. 모든 서비스 로그 확인
make logs-all

# 2. Detector 로그 실시간 확인
make logs

# 3. 시스템 상태 테스트
make test
```

### 예상 결과

정상적으로 실행되면 다음과 같은 출력을 볼 수 있습니다:

**Log Collector:**
```
[log-collector] Loaded HDFS log: 2033 lines
[log-collector] Parsed 11 unique templates
[log-collector] Sent to normalizer: 11 templates
```

**Normalizer:**
```
[normalizer] Received 11 events
[normalizer] Converted to sequences: max_len=50
[normalizer] Sent to detector: 11 sequences
```

**Detector:**
```
[detector] Loaded multi-domain model (767 events)
[detector] Model threshold: 0.003000
[detector] Batch inference: 11 sequences
[detector] Detected 1 anomaly, 10 normal
```

**Visualizer API:**
```bash
curl http://localhost:8502/statistics
{
  "total_logs": 2033,
  "anomalies": 165,
  "normal": 1868,
  "anomaly_rate": "8.12%"
}
```

### 문제 해결

**Pod이 ImagePullBackOff 상태일 때:**
```bash
eval $(minikube docker-env)
make build
kubectl delete pods --all
make deploy
```

**Threshold 변경이 적용 안 될 때:**
```bash
# Pod 재시작이 아닌 삭제 후 재생성 필요
kubectl delete pod -l app=detector
kubectl get pods -w
```

## 데모 시나리오 (영상 촬영용)

### 1단계: 시스템 구동 (1분)

```bash
# 터미널 화면 녹화 시작
make status                    # 현재 상태 확인
make build                     # 빌드 과정 보여주기 (30초)
make deploy                    # 배포 과정 보여주기 (20초)
kubectl get pods               # 모든 Pod Running 확인
```

**설명 포인트:**
- "5개의 마이크로서비스가 Kubernetes 환경에서 동작합니다"
- "각 서비스는 독립적으로 스케일 가능하도록 설계했습니다"

### 2단계: 로그 처리 흐름 (2분)

```bash
# 각 서비스 로그를 순서대로 확인
kubectl logs deployment/log-collector --tail=10
```

**설명 포인트:**
- "Log Collector가 HDFS 로그 2033줄을 읽고 Drain3로 11개의 템플릿 추출"

```bash
kubectl logs deployment/normalizer --tail=10
```

**설명 포인트:**
- "Normalizer가 템플릿을 이벤트 ID로 변환하고 시퀀스 생성"

```bash
kubectl logs deployment/detector --tail=15
```

**설명 포인트:**
- "Multi-domain GRU AutoEncoder 모델이 767개의 이벤트 vocabulary 사용"
- "Threshold 0.003을 기준으로 이상 탐지 수행"
- "11개 시퀀스 중 1개 이상, 10개 정상으로 판단"

### 3단계: 결과 확인 (1분)

```bash
# Visualizer API 포트 포워딩
kubectl port-forward svc/visualizer-service 8502:8502 &
sleep 3

# 통계 조회
curl -s http://localhost:8502/statistics | python3 -m json.tool
```

**설명 포인트:**
- "전체 2033개 로그 중 165개(8.12%)가 이상으로 탐지됨"

```bash
# 최근 이상 로그 조회
curl -s "http://localhost:8502/anomalies?limit=3" | python3 -m json.tool
```

**설명 포인트:**
- "각 이상 로그의 재구성 오차(loss)가 threshold를 초과"

### 4단계: LLM 설명 생성 (1분)

```bash
# LLM Service 포트 포워딩
kubectl port-forward svc/llm-service 8000:8000 &
sleep 2

# 이상 로그 설명 요청
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{
    "log": {
      "message": "BLOCK* NameSystem.addStoredBlock: blockMap updated",
      "loss": 0.008234,
      "threshold": 0.003000
    },
    "status": "anomaly"
  }' | python3 -m json.tool --ensure-ascii=false
```

**예상 출력:**
```json
{
  "summary": "HDFS 블록 전송 또는 복제 과정에서 이상이 감지되었습니다.",
  "severity": "MEDIUM",
  "pattern": "block",
  "details": {
    "loss_score": "0.008234",
    "threshold": "0.003000",
    "deviation": "174.5%"
  },
  "recommendations": [
    "⚡ 주의: 빠른 대응이 권장됩니다.",
    "DataNode의 상태를 확인하세요 (hdfs dfsadmin -report)",
    "네트워크 연결 상태를 점검하세요"
  ]
}
```

**설명 포인트:**
- "룰 기반 시스템으로 실시간 설명 생성 (1ms 미만)"
- "패턴별 대응 방안을 자동으로 제안"

### 5단계: 멀티 도메인 학습 설명 (1분)

```bash
# 모델 메타데이터 확인
python3 << 'EOF'
import pickle
with open('./models/multi_domain_model_meta.pkl', 'rb') as f:
    meta = pickle.load(f)
    print(f"Domains: {meta['domains']}")
    print(f"Total Events: {meta['num_events']}")
    print(f"Test Accuracy: {meta['test_accuracy']:.2%}")
    print(f"Test Precision: {meta['test_precision']:.2%}")
    print(f"Test Recall: {meta['test_recall']:.2%}")
EOF
```

**설명 포인트:**
- "HDFS, Hadoop, OpenStack 3개 도메인 통합 학습"
- "데이터 증강으로 클래스 불균형 문제 해결"
- "최종 정확도 93.41%, 정밀도 92.95% 달성"

### 6단계: 정리 (30초)

```bash
make clean                     # 모든 리소스 삭제
kubectl get pods               # 정리 확인
```

## 주요 변경 사항 (Git Commit용)

### 새로 추가된 파일
- `Makefile` - 빌드/배포 자동화
- `README.md` - 프로젝트 문서 (본 파일)
- `services/llm-service/` - 이상 로그 설명 생성 서비스
- `training/train_multi_domain_augmented.ipynb` - Multi-domain 학습 노트북
- `models/multi_domain_*` - 학습된 모델 파일 (4개)
- `k8s/` - Kubernetes 배포 설정

### 수정된 파일
- `services/detector/main.py` - Multi-domain 모델 지원 추가
- `services/log-collector/Dockerfile` - 불필요한 데이터 복사 제거
- `services/normalizer/main.py` - Multi-domain vocabulary 지원
- `services/visualizer/main.py` - 통계 API 개선
- `.gitignore` - 대용량 데이터 파일 제외

### 삭제된 파일
- 모든 .sh 스크립트 (Makefile로 대체)
- loghub 데이터셋 (~8GB)
- 사용하지 않는 학습 스크립트들 (train_all.py, train_unified.py 등)
- AI 생성 문서들 (docs/, 각종 README)
- LLM 모델 파일들 (16GB+)

## 기술 스택

- **모델**: PyTorch, GRU AutoEncoder
- **전처리**: Drain3 (로그 파싱)
- **백엔드**: Flask (Python 3.9)
- **오케스트레이션**: Kubernetes + Minikube
- **컨테이너**: Docker
- **학습 환경**: Google Colab (T4 GPU)

## 학습 내용 및 개선점

### 잘한 점
1. 마이크로서비스 아키텍처로 각 컴포넌트 독립 관리
2. Multi-domain 학습으로 범용성 확보
3. 데이터 증강으로 클래스 불균형 해결
4. Makefile로 복잡한 배포 과정 단순화

### 아쉬운 점
1. Kafka 등 메시지 큐 미사용 (실시간성 제한)
2. 프론트엔드 UI 부재 (REST API만 제공)
3. 모델 재학습 파이프라인 자동화 부족
4. 프로덕션 레벨 로깅/모니터링 미구현

### 추후 개선 방향
- Prometheus + Grafana로 메트릭 시각화
- MLflow로 모델 버전 관리
- Horizontal Pod Autoscaler 적용
- React 기반 대시보드 구현

---

**개발 기간**: 2025.11.28
**목적**: MSA 기반 이상 탐지 시스템 학습 및 구현
