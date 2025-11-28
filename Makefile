.PHONY: build deploy clean restart logs test

# Docker 환경 설정
docker-env:
	@eval $$(minikube docker-env)

# 모든 이미지 빌드
build:
	@echo "Building Docker images..."
	@eval $$(minikube docker-env) && \
	echo "[1/4] Building log-collector..." && \
	docker build -t log-collector:latest ./services/log-collector && \
	echo "[2/4] Building normalizer..." && \
	docker build -t normalizer:latest ./services/normalizer && \
	echo "[3/4] Building detector..." && \
	mkdir -p ./services/detector/models && \
	cp ./models/*.pkl ./services/detector/models/ 2>/dev/null || true && \
	cp ./models/*.pth ./services/detector/models/ 2>/dev/null || true && \
	docker build -t detector:latest ./services/detector && \
	rm -rf ./services/detector/models && \
	echo "[4/4] Building visualizer..." && \
	docker build -t visualizer:latest ./services/visualizer && \
	echo "[5/5] Building llm-service..." && \
	docker build -t llm-service:latest ./services/llm-service && \
	echo "✅ All images built successfully!"

# Kubernetes 배포
deploy:
	@echo "Deploying to Kubernetes..."
	@kubectl apply -f k8s/configmap.yaml
	@kubectl apply -f k8s/deployments.yaml
	@kubectl apply -f k8s/services.yaml
	@echo "✅ Deployment complete!"
	@echo "\nChecking pod status..."
	@kubectl get pods

# 전체 클린업
clean:
	@echo "Cleaning up Kubernetes resources..."
	@kubectl delete -f k8s/services.yaml 2>/dev/null || true
	@kubectl delete -f k8s/deployments.yaml 2>/dev/null || true
	@kubectl delete -f k8s/configmap.yaml 2>/dev/null || true
	@echo "✅ Cleanup complete!"

# 재배포 (빌드 + 배포)
redeploy: build deploy

# Pod 재시작
restart:
	@echo "Restarting pods..."
	@kubectl rollout restart deployment/log-collector
	@kubectl rollout restart deployment/normalizer
	@kubectl rollout restart deployment/detector
	@kubectl rollout restart deployment/visualizer
	@kubectl rollout restart deployment/llm-service
	@echo "✅ Pods restarted!"

# 로그 확인
logs:
	@echo "=== Detector Logs ==="
	@kubectl logs -f deployment/detector --tail=50

logs-all:
	@echo "=== Log Collector ==="
	@kubectl logs deployment/log-collector --tail=20
	@echo "\n=== Normalizer ==="
	@kubectl logs deployment/normalizer --tail=20
	@echo "\n=== Detector ==="
	@kubectl logs deployment/detector --tail=20
	@echo "\n=== Visualizer ==="
	@kubectl logs deployment/visualizer --tail=20
	@echo "\n=== LLM Service ==="
	@kubectl logs deployment/llm-service --tail=20

# 상태 확인
status:
	@echo "=== Pods ==="
	@kubectl get pods
	@echo "\n=== Services ==="
	@kubectl get svc
	@echo "\n=== ConfigMaps ==="
	@kubectl get configmap

# 테스트
test:
	@echo "Testing system..."
	@echo "Port forwarding visualizer..."
	@kubectl port-forward svc/visualizer-service 8502:8502 &
	@sleep 3
	@echo "Fetching statistics..."
	@curl -s http://localhost:8502/statistics | python3 -m json.tool || true
	@pkill -f "port-forward"

# 도움말
help:
	@echo "AnomalyDetector Makefile Commands"
	@echo ""
	@echo "  make build        - Docker 이미지 빌드"
	@echo "  make deploy       - Kubernetes 배포"
	@echo "  make redeploy     - 재빌드 + 재배포"
	@echo "  make clean        - 모든 리소스 삭제"
	@echo "  make restart      - Pod 재시작"
	@echo "  make logs         - Detector 로그 확인"
	@echo "  make logs-all     - 모든 서비스 로그 확인"
	@echo "  make status       - 시스템 상태 확인"
	@echo "  make test         - 시스템 테스트"
