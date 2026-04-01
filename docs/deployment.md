# Deployment Guide: Prompt Management Service

This guide covers deploying the Prompt Management Service to production.

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Docker Deployment](#docker-deployment)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Health Checks](#health-checks)
5. [Monitoring](#monitoring)
6. [Troubleshooting](#troubleshooting)

---

## Environment Setup

### Required Environment Variables

```bash
# Langfuse Configuration
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key

# Service Configuration
PROMPT_SERVICE_PORT=8000
PROMPT_SERVICE_LOG_LEVEL=info

# Cache Configuration
CACHE_ENABLED=true
CACHE_TTL=300
CACHE_MAX_SIZE=1000
```

### Optional Environment Variables

```bash
# API Authentication (if using API keys)
PROMPT_SERVICE_API_KEY=your-api-key

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Timeouts
REQUEST_TIMEOUT_SECONDS=30
```

---

## Docker Deployment

### Build the Image

```bash
docker build -f Dockerfile.prompt-service -t prompt-service:latest .
```

### Run the Container

```bash
docker run -d \
  --name prompt-service \
  -p 8000:8000 \
  --env-file .env \
  prompt-service:latest
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  prompt-service:
    build:
      context: .
      dockerfile: Dockerfile.prompt-service
    ports:
      - "8000:8000"
    environment:
      - LANGFUSE_HOST=${LANGFUSE_HOST}
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - PROMPT_SERVICE_LOG_LEVEL=info
      - CACHE_ENABLED=true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
```

Run with:

```bash
docker-compose up -d
```

---

## Kubernetes Deployment

### Deployment Manifest

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prompt-service
  labels:
    app: prompt-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: prompt-service
  template:
    metadata:
      labels:
        app: prompt-service
    spec:
      containers:
      - name: prompt-service
        image: prompt-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: LANGFUSE_HOST
          valueFrom:
            secretKeyRef:
              name: langfuse-secrets
              key: host
        - name: LANGFUSE_PUBLIC_KEY
          valueFrom:
            secretKeyRef:
              name: langfuse-secrets
              key: public-key
        - name: LANGFUSE_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: langfuse-secrets
              key: secret-key
        - name: PROMPT_SERVICE_LOG_LEVEL
          value: "info"
        - name: CACHE_ENABLED
          value: "true"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: prompt-service
spec:
  selector:
    app: prompt-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Create Secrets

```bash
kubectl create secret generic langfuse-secrets \
  --from-literal=host=https://cloud.langfuse.com \
  --from-literal=public-key=your-public-key \
  --from-literal=secret-key=your-secret-key
```

### Deploy

```bash
kubectl apply -f k8s/deployment.yaml
```

---

## Health Checks

### Health Endpoint

```bash
GET /health
```

Response:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "langfuse": "connected",
    "cache": "enabled"
  },
  "uptime_ms": 123456.789
}
```

### Health Status Values

| Status | Description |
|--------|-------------|
| `healthy` | All components operational |
| `degraded` | Service running but some features limited |
| `unhealthy` | Service not functioning properly |

---

## Monitoring

### Metrics to Monitor

1. **Request Metrics**
   - Request rate (requests/second)
   - Response time (p50, p95, p99)
   - Error rate (4xx, 5xx)

2. **Cache Metrics**
   - Cache hit rate
   - Cache size
   - Cache evictions

3. **Langfuse Connection**
   - Connection status
   - API call latency
   - Failure rate

### Logging

Logs are structured JSON with the following fields:

```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "logger": "prompt_service.services.prompt_retrieval",
  "message": "Prompt retrieved",
  "trace_id": "abc-123-def",
  "template_id": "my_prompt",
  "version_id": 1,
  "from_cache": false
}
```

### Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostic information |
| `INFO` | Normal operational messages |
| `WARNING` | Warning conditions |
| `ERROR` | Error conditions |
| `CRITICAL` | Critical conditions requiring immediate attention |

---

## Troubleshooting

### Service Won't Start

1. **Check environment variables**:
   ```bash
   docker logs prompt-service
   ```

2. **Verify Langfuse credentials**:
   - Check that `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are correct
   - Test connection to Langfuse host

3. **Check port availability**:
   ```bash
   netstat -tuln | grep 8000
   ```

### High Error Rates

1. **Check Langfuse status**:
   ```bash
   curl http://localhost:8000/health?detailed=true
   ```

2. **Review logs for errors**:
   ```bash
   docker logs prompt-service --tail 100 | grep ERROR
   ```

3. **Monitor cache performance**:
   - Low cache hit rates may indicate cache size issues
   - Consider increasing `CACHE_MAX_SIZE`

### Slow Response Times

1. **Check Langfuse latency**:
   - High Langfuse API latency can slow down prompt retrieval
   - Consider caching frequently accessed prompts

2. **Review cache settings**:
   ```bash
   # Check cache hit rate
   curl http://localhost:8000/health?detailed=true
   ```

3. **Monitor resource usage**:
   ```bash
   docker stats prompt-service
   ```

---

## Scaling

### Horizontal Scaling

The service is stateless and can be scaled horizontally:

```bash
kubectl scale deployment prompt-service --replicas=5
```

### Load Balancing

Use a load balancer (NGINX, HAProxy, AWS ALB) to distribute traffic across instances.

### Cache Considerations

- Each instance maintains its own L1 cache
- For distributed deployments, consider adding a Redis cache
- Configure cache warming for frequently accessed prompts

---

## Security Considerations

1. **API Authentication**
   - Use API keys for client authentication
   - Implement rate limiting per API key
   - Use HTTPS in production

2. **Input Validation**
   - All inputs are validated using Pydantic models
   - Variable interpolation uses Jinja2 `StrictUndefined`
   - Template injection protection

3. **Secrets Management**
   - Store secrets in Kubernetes secrets or equivalent
   - Never commit secrets to version control
   - Rotate credentials regularly

4. **Network Security**
   - Use network policies to restrict pod-to-pod communication
   - Implement rate limiting
   - Configure CORS appropriately
