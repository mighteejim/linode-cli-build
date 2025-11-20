# BuildWatch Usage Guide

## Overview

**BuildWatch is automatically enabled for all deployments** - no template configuration required! It monitors your Docker containers in real-time and provides observability through multiple interfaces.

## For Template Authors

### ✅ **Good News: Nothing to Configure!**

BuildWatch works automatically with any template. Here's a minimal working template:

```yaml
name: my-app
display_name: My Application
version: 1.0.0
description: My awesome application

capabilities:
  runtime: docker          # BuildWatch monitors Docker containers
  features: []
  packages: []

deploy:
  linode:
    region_default: us-ord
    type_default: g6-standard-2
    image: linode/ubuntu24.04
    
    container:
      image: my-app:latest
      internal_port: 8000
      external_port: 80
      env:
        API_KEY: ${API_KEY}
```

**That's it!** BuildWatch is automatically:
- Installed during deployment
- Monitoring all Docker events (start, stop, die, restart)
- Detecting issues (OOM kills, crash loops)
- Logging to `/var/log/build-watcher/`
- Providing HTTP API on port 9090

### 🎯 **What BuildWatch Monitors**

BuildWatch automatically tracks:
- ✅ Container starts and stops
- ✅ Container crashes (with exit codes)
- ✅ OOM (Out of Memory) kills
- ✅ Frequent restart loops (3+ restarts in 5 minutes)
- ✅ Health check failures
- ✅ System metrics (CPU, memory, disk)

## For Users: Accessing BuildWatch

### 1. **TUI Dashboard** (Recommended)

```bash
linode-cli build tui <deployment-id>
```

**What you see:**
- Real-time container events (updated every 5 seconds)
- Color-coded event types:
  - 🟢 Green: Container starts
  - 🔴 Red: Container crashes/dies
  - 🟡 Yellow: Container stops
  - 🔵 Cyan: Container restarts
- Detected issues with severity levels
- Actionable recommendations

**Example output in TUI:**
```
Recent Activity
────────────────────────────────────────
[19:00:15] app started
[19:02:30] app died (exit: 137)
[19:02:35] app restarted

⚠ Issues Detected:
  ✕ CRITICAL: Container killed - likely out of memory
    → Increase memory limit or optimize application
```

### 2. **CLI Status Command**

```bash
# Basic status
linode-cli build status

# Detailed with BuildWatch info
linode-cli build status --verbose
```

**Verbose output includes:**
```
  ID: k7m3p9x2
  App: chat-agent
  Env: production
  Status: running
  URL: http://123.45.67.89

  BuildWatch Status:

    Recent Events:
      [19:00:15] ✓ app started
      [19:02:30] ✕ app died (exit code: 137)
      [19:02:35] ↻ app restarted
      [19:05:30] ✓ app started

    Issues Detected:
      ✕ CRITICAL: Container killed due to out of memory
        → Increase memory limit or optimize application
      ⚠ WARNING: Container restarted 3 times in 5 minutes

    No issues detected
```

### 3. **Direct HTTP API**

BuildWatch exposes an HTTP API on port 9090:

#### **Get Recent Events**
```bash
curl http://<instance-ip>:9090/events?limit=50
```

Response:
```json
{
  "events": [
    {
      "timestamp": "2025-11-19T19:00:00Z",
      "type": "start",
      "container": "app",
      "image": "my-app:latest",
      "id": "a1b2c3d4e5f6"
    },
    {
      "timestamp": "2025-11-19T19:02:15Z",
      "type": "die",
      "container": "app",
      "exit_code": 137,
      "id": "a1b2c3d4e5f6"
    }
  ],
  "count": 2
}
```

#### **Get Detected Issues**
```bash
curl http://<instance-ip>:9090/issues
```

Response:
```json
{
  "issues": [
    {
      "timestamp": "2025-11-19T19:02:15Z",
      "severity": "critical",
      "type": "oom_killed",
      "container": "app",
      "message": "Container killed - likely out of memory",
      "recommendation": "Increase memory limit or optimize application",
      "resolved": false
    }
  ],
  "count": 1
}
```

#### **Get Container Logs**
```bash
curl http://<instance-ip>:9090/logs?container=app&lines=100
```

Response:
```json
{
  "container": "app",
  "logs": [
    "[2025-11-19 19:00:00] Server started on port 8000",
    "[2025-11-19 19:00:01] Database connected",
    "[2025-11-19 19:02:00] Error: Out of memory"
  ]
}
```

#### **Get Full Status**
```bash
curl http://<instance-ip>:9090/status
```

Response:
```json
{
  "containers": {
    "app": {
      "id": "x7y8z9a0b1c2",
      "image": "my-app:latest",
      "status": "running",
      "started_at": "2025-11-19T19:02:35Z",
      "restart_count": 3,
      "last_exit_code": 137
    }
  },
  "deployment": {
    "id": "k7m3p9x2",
    "app_name": "chat-agent",
    "started_at": "2025-11-19T17:00:00Z"
  },
  "issues": [...]
}
```

#### **Health Check**
```bash
curl http://<instance-ip>:9090/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-19T19:00:00Z",
  "service": "buildwatch"
}
```

## Log Files on Instance

BuildWatch maintains several log files on the deployed instance:

```
/var/log/build-watcher/
├── events.log      # Container lifecycle events (JSON lines)
├── status.log      # Periodic status snapshots (every 5 min)
├── metrics.log     # System metrics (every 1 min)
└── errors.log      # Detected issues and errors
```

### Accessing Logs via SSH

```bash
# SSH to your instance
ssh root@<instance-ip>

# View recent events
tail -f /var/log/build-watcher/events.log

# View detected issues
tail -f /var/log/build-watcher/errors.log

# View metrics
tail -f /var/log/build-watcher/metrics.log

# Check service status
systemctl status build-watcher
```

### Log Format Examples

**events.log** (JSON lines):
```json
{"timestamp":"2025-11-19T19:00:00Z","type":"start","container":"app","image":"my-app:latest","id":"a1b2c3d4e5f6"}
{"timestamp":"2025-11-19T19:02:15Z","type":"die","container":"app","exit_code":137}
```

**metrics.log** (JSON lines):
```json
{"timestamp":"2025-11-19T19:00:00Z","cpu_load":0.45,"memory_used_percent":50.2,"disk_used_percent":20.5}
```

## Issue Detection

BuildWatch automatically detects common problems:

### 🔴 **OOM Kills (Out of Memory)**
- **Detection**: Exit code 137 (SIGKILL)
- **Severity**: Critical
- **Recommendation**: Increase memory limit or optimize application

### 🟡 **Frequent Restarts**
- **Detection**: 3+ restarts within 5 minutes
- **Severity**: Warning
- **Recommendation**: Check application logs for crash cause

### 🟡 **Health Check Failures**
- **Detection**: Container health status becomes unhealthy
- **Severity**: Warning
- **Recommendation**: Verify application health endpoint

## Advanced Usage

### Custom Monitoring Scripts

You can build custom monitoring tools using the BuildWatch API:

```python
import requests
import time

INSTANCE_IP = "123.45.67.89"
API_URL = f"http://{INSTANCE_IP}:9090"

def monitor_deployment():
    """Monitor deployment and alert on issues."""
    while True:
        # Check for new issues
        response = requests.get(f"{API_URL}/issues")
        issues = response.json()
        
        for issue in issues['issues']:
            if not issue['resolved'] and issue['severity'] == 'critical':
                send_alert(issue)  # Your alerting logic
        
        time.sleep(30)  # Check every 30 seconds

def send_alert(issue):
    """Send alert to Slack, email, etc."""
    print(f"🚨 ALERT: {issue['message']}")
    # Send to Slack, PagerDuty, etc.
```

### Grafana/Prometheus Integration

The metrics log can be parsed and exported to monitoring systems:

```bash
# Example: Export metrics to Prometheus format
tail -f /var/log/build-watcher/metrics.log | while read line; do
  # Parse JSON and export as Prometheus metrics
  echo "$line" | jq -r '"cpu_load \(.cpu_load)"'
done
```

## Troubleshooting

### BuildWatch Not Running

```bash
# Check service status
systemctl status build-watcher

# View service logs
journalctl -u build-watcher -f

# Restart service
systemctl restart build-watcher
```

### API Not Responding

```bash
# Check if port 9090 is open
netstat -tulpn | grep 9090

# Check firewall
ufw status

# Test locally on instance
curl http://localhost:9090/health
```

### Missing Events

```bash
# Check Docker is running
docker ps

# Check build-watcher can access Docker
docker events  # Should show real-time events

# Check logs for errors
tail -f /var/log/build-watcher/errors.log
```

## FAQ

### Q: Do I need to configure BuildWatch in my template?
**A:** No! BuildWatch is automatically enabled for all deployments.

### Q: Can I disable BuildWatch?
**A:** Not currently, but it's lightweight and doesn't impact application performance. If needed, it could be made optional in a future update.

### Q: Does BuildWatch work with multiple containers?
**A:** Yes! BuildWatch monitors all Docker containers on the instance, not just your main application container.

### Q: How much disk space do logs use?
**A:** Logs are automatically rotated daily and kept for 7 days (configurable via `/etc/logrotate.d/build-watcher`).

### Q: Can I customize the monitoring port?
**A:** Not currently. Port 9090 is hardcoded. This could be made configurable as a future enhancement.

### Q: Does BuildWatch work with Docker Compose?
**A:** Yes! BuildWatch monitors all Docker containers regardless of how they were started.

## Summary

BuildWatch provides **zero-configuration container monitoring** for all deployments:

- ✅ **Automatic** - No template changes needed
- ✅ **Real-time** - Instant event notification
- ✅ **Smart** - Automatic issue detection
- ✅ **Accessible** - TUI, CLI, and HTTP API
- ✅ **Persistent** - Logs and state survive restarts
- ✅ **Lightweight** - Minimal resource usage

Just deploy your template and start monitoring! 🎯
