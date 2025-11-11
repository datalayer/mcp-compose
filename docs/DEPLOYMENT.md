# MCP Compose - Deployment Guide

## Table of Contents

1. [Deployment Options](#deployment-options)
2. [Docker Deployment](#docker-deployment)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Production Configuration](#production-configuration)
5. [Monitoring & Observability](#monitoring--observability)
6. [Security Hardening](#security-hardening)
7. [Performance Tuning](#performance-tuning)
8. [Backup & Recovery](#backup--recovery)

## Deployment Options

### Option 1: Direct Installation

Best for: Development, testing, simple deployments

**Pros:**
- Simple setup
- Easy debugging
- Direct control

**Cons:**
- Manual dependency management
- Less isolated
- Harder to scale

### Option 2: Docker

Best for: Production, consistent environments, easy scaling

**Pros:**
- Isolated environment
- Easy scaling
- Consistent across platforms
- Simple rollback

**Cons:**
- Requires Docker knowledge
- Additional overhead

### Option 3: Kubernetes

Best for: Large-scale production, high availability

**Pros:**
- Auto-scaling
- Self-healing
- Load balancing
- Rolling updates

**Cons:**
- Complex setup
- Requires Kubernetes expertise
- Higher resource requirements

## Docker Deployment

### Dockerfile

Create `Dockerfile`:

```dockerfile
# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml README.md ./
COPY mcp_compose/ ./mcp_compose/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy configuration
COPY examples/mcp_compose.toml /etc/mcp-composer/config.toml

# Copy Web UI
COPY ui/dist /app/ui/dist

# Create non-root user
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
USER mcp

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application
CMD ["mcp-composer", "serve", "--config", "/etc/mcp-composer/config.toml", "--host", "0.0.0.0"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mcp-composer:
    build: .
    container_name: mcp-composer
    ports:
      - "8000:8000"
    volumes:
      # Configuration
      - ./config:/etc/mcp-composer:ro
      # Data directory (if needed for file-based servers)
      - ./data:/data
      # Logs
      - ./logs:/var/log/mcp-composer
    environment:
      - MCP_COMPOSER_LOG_LEVEL=INFO
      - MCP_COMPOSER_HOST=0.0.0.0
      - MCP_COMPOSER_PORT=8000
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - mcp-network

  # Prometheus for metrics
  prometheus:
    image: prom/prometheus:latest
    container_name: mcp-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped
    networks:
      - mcp-network

  # Grafana for visualization
  grafana:
    image: grafana/grafana:latest
    container_name: mcp-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana-dashboards:/etc/grafana/provisioning/dashboards:ro
    restart: unless-stopped
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge

volumes:
  prometheus-data:
  grafana-data:
```

### Prometheus Configuration

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'mcp-composer'
    static_configs:
      - targets: ['mcp-composer:8000']
    metrics_path: '/metrics'
```

### Building and Running

```bash
# Build image
docker build -t mcp-composer:latest .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f mcp-composer

# Stop
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Docker Best Practices

1. **Use multi-stage builds** for smaller images:
```dockerfile
# Build stage
FROM python:3.10 as builder
WORKDIR /app
COPY . .
RUN pip install --user -e .

# Runtime stage
FROM python:3.10-slim
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
CMD ["mcp-composer", "serve"]
```

2. **Use .dockerignore**:
```
.git
.gitignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.pytest_cache
.coverage
htmlcov/
*.log
node_modules/
.vscode/
.idea/
```

3. **Set resource limits**:
```yaml
services:
  mcp-composer:
    # ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

## Kubernetes Deployment

### Deployment Manifest

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-composer
  namespace: mcp-system
  labels:
    app: mcp-composer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-composer
  template:
    metadata:
      labels:
        app: mcp-composer
    spec:
      containers:
      - name: mcp-composer
        image: mcp-composer:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: MCP_COMPOSER_HOST
          value: "0.0.0.0"
        - name: MCP_COMPOSER_LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /api/v1/status
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        volumeMounts:
        - name: config
          mountPath: /etc/mcp-composer
          readOnly: true
        - name: data
          mountPath: /data
      volumes:
      - name: config
        configMap:
          name: mcp-composer-config
      - name: data
        persistentVolumeClaim:
          claimName: mcp-composer-data
```

### Service Manifest

Create `k8s/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mcp-composer
  namespace: mcp-system
  labels:
    app: mcp-composer
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: http
  selector:
    app: mcp-composer
```

### ConfigMap

Create `k8s/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-composer-config
  namespace: mcp-system
data:
  config.toml: |
    [composer]
    name = "production-composer"
    conflict_resolution = "prefix"

    [[servers]]
    name = "filesystem"
    command = "python"
    args = ["-m", "mcp_server_filesystem", "/data"]
    transport = "stdio"
```

### Ingress

Create `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-composer-ingress
  namespace: mcp-system
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - mcp-composer.example.com
    secretName: mcp-composer-tls
  rules:
  - host: mcp-composer.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mcp-composer
            port:
              number: 80
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace mcp-system

# Apply configurations
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl get pods -n mcp-system
kubectl get svc -n mcp-system
kubectl logs -f deployment/mcp-composer -n mcp-system

# Scale
kubectl scale deployment/mcp-composer --replicas=5 -n mcp-system

# Update
kubectl set image deployment/mcp-composer mcp-composer=mcp-composer:v1.1.0 -n mcp-system

# Rollback
kubectl rollout undo deployment/mcp-composer -n mcp-system
```

## Production Configuration

### Environment Variables

```bash
# Server Configuration
export MCP_COMPOSER_HOST=0.0.0.0
export MCP_COMPOSER_PORT=8000
export MCP_COMPOSER_WORKERS=4

# Logging
export MCP_COMPOSER_LOG_LEVEL=INFO
export MCP_COMPOSER_LOG_FORMAT=json
export MCP_COMPOSER_LOG_FILE=/var/log/mcp-composer/app.log

# Security
export MCP_COMPOSER_AUTH_TOKEN=your-secure-token-here
export MCP_COMPOSER_CORS_ORIGINS=https://app.example.com

# Performance
export MCP_COMPOSER_MAX_CONNECTIONS=1000
export MCP_COMPOSER_TIMEOUT=30
export MCP_COMPOSER_KEEPALIVE=5

# Monitoring
export MCP_COMPOSER_METRICS_ENABLED=true
export MCP_COMPOSER_TRACING_ENABLED=true
```

### Configuration File (Production)

`production.toml`:

```toml
[composer]
name = "production-composer"
conflict_resolution = "prefix"
max_tool_invocation_time = 60
enable_metrics = true
enable_health_checks = true

[logging]
level = "INFO"
format = "json"
file = "/var/log/mcp-composer/app.log"

[security]
auth_enabled = true
cors_origins = ["https://app.example.com"]
rate_limit_per_minute = 100

[[servers]]
name = "filesystem"
command = "python"
args = ["-m", "mcp_server_filesystem", "/data"]
transport = "stdio"
auto_start = true
restart_on_failure = true
max_restarts = 3
restart_delay = 10

[servers.env]
LOG_LEVEL = "INFO"
CACHE_ENABLED = "true"
```

## Monitoring & Observability

### Grafana Dashboard

Import dashboard JSON (create `grafana-dashboards/mcp-composer.json`):

```json
{
  "dashboard": {
    "title": "MCP Compose",
    "panels": [
      {
        "title": "HTTP Requests",
        "targets": [
          {
            "expr": "rate(mcp_http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Tool Invocations",
        "targets": [
          {
            "expr": "rate(mcp_tool_invocations_total[5m])"
          }
        ]
      },
      {
        "title": "Server Status",
        "targets": [
          {
            "expr": "mcp_servers_running"
          }
        ]
      }
    ]
  }
}
```

### Alerts

Create `prometheus-alerts.yml`:

```yaml
groups:
  - name: mcp_composer
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(mcp_http_requests_total{status="500"}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} requests/s"

      - alert: ServerDown
        expr: mcp_servers_running < mcp_servers_total
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "MCP server is down"
          description: "{{ $value }} servers are not running"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P95 latency is {{ $value }}s"
```

### Log Aggregation

**Using Fluentd:**

Create `fluentd.conf`:

```xml
<source>
  @type forward
  port 24224
</source>

<match mcp.**>
  @type elasticsearch
  host elasticsearch
  port 9200
  index_name mcp-composer
  type_name _doc
</match>
```

## Security Hardening

### 1. Enable Authentication

```bash
export MCP_COMPOSER_AUTH_TOKEN=$(openssl rand -hex 32)
```

### 2. Use HTTPS

```nginx
server {
    listen 443 ssl http2;
    server_name mcp-composer.example.com;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Firewall Rules

```bash
# Allow only specific IPs
ufw allow from 192.168.1.0/24 to any port 8000

# Rate limiting
iptables -A INPUT -p tcp --dport 8000 -m limit --limit 100/min -j ACCEPT
```

### 4. Network Policies (Kubernetes)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-composer-policy
spec:
  podSelector:
    matchLabels:
      app: mcp-composer
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: mcp-system
    ports:
    - protocol: TCP
      port: 8000
```

## Performance Tuning

### 1. Uvicorn Workers

```bash
mcp-composer serve --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### 2. Connection Pooling

```python
# In configuration
[performance]
max_connections = 1000
keepalive_timeout = 5
request_timeout = 30
```

### 3. Caching

```nginx
# Nginx caching
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=mcp_cache:10m max_size=100m;

location /api/v1/ {
    proxy_cache mcp_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_key "$request_uri";
}
```

### 4. Database Optimization

If using persistent storage:

```python
# Connection pooling
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 40
SQLALCHEMY_POOL_RECYCLE = 3600
```

## Backup & Recovery

### Backup Configuration

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/mcp-composer"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" /etc/mcp-composer/

# Backup data
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" /data/

# Backup logs
tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" /var/log/mcp-composer/

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
```

### Restore Procedure

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

# Stop service
docker-compose down

# Restore configuration
tar -xzf "$BACKUP_FILE" -C /

# Start service
docker-compose up -d
```

### Disaster Recovery Plan

1. **Regular Backups**: Daily automated backups
2. **Off-site Storage**: Store backups in S3/GCS
3. **Testing**: Monthly restore testing
4. **Documentation**: Maintain runbooks
5. **Monitoring**: Alert on backup failures

## Scaling Strategies

### Horizontal Scaling

```bash
# Docker Swarm
docker service scale mcp-composer=5

# Kubernetes
kubectl scale deployment/mcp-composer --replicas=5
```

### Vertical Scaling

```yaml
resources:
  limits:
    memory: "4Gi"
    cpu: "4000m"
  requests:
    memory: "2Gi"
    cpu: "2000m"
```

### Auto-scaling (Kubernetes)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mcp-composer-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mcp-composer
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Troubleshooting Production Issues

### High Memory Usage

```bash
# Check memory usage
docker stats mcp-composer

# Restart with limits
docker run --memory=2g --memory-swap=2g mcp-composer
```

### High CPU Usage

```bash
# Profile application
py-spy top --pid $(pgrep -f mcp-composer)

# Check slow endpoints
curl http://localhost:8000/api/v1/status/metrics
```

### Connection Issues

```bash
# Check connections
netstat -an | grep 8000

# Check DNS
nslookup mcp-composer.example.com

# Test connectivity
curl -v http://localhost:8000/api/v1/health
```

---

## Production Checklist

- [ ] SSL/TLS enabled
- [ ] Authentication configured
- [ ] Monitoring setup (Prometheus + Grafana)
- [ ] Logging aggregation configured
- [ ] Backups automated
- [ ] Resource limits set
- [ ] Health checks configured
- [ ] Auto-scaling enabled
- [ ] Firewall rules applied
- [ ] Rate limiting enabled
- [ ] Alerts configured
- [ ] Documentation updated
- [ ] Disaster recovery tested
- [ ] Security audit completed

## Support

- Documentation: https://github.com/datalayer/mcp-compose
- Issues: https://github.com/datalayer/mcp-compose/issues
