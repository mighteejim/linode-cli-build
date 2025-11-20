# BuildWatch Usage Guide

> **Note:** BuildWatch is now an **optional capability**. See the main [Capabilities Reference](capabilities.md) for comprehensive documentation.

## Quick Start

BuildWatch provides real-time Docker container monitoring with automatic issue detection.

### Enable BuildWatch

Add to your template's capabilities:

```yaml
capabilities:
  runtime: docker
  features:
    - buildwatch  # Enable monitoring
```

### With Custom Configuration

```yaml
capabilities:
  features:
    - name: buildwatch
      config:
        port: 9090              # API port (default: 9090)
        log_retention_days: 7   # Rotation (default: 7)
        enable_metrics: true    # Metrics (default: true)
```

## Accessing BuildWatch

### 1. TUI Dashboard

```bash
linode-cli build tui
```

Real-time events, issues, and recommendations.

### 2. CLI Status

```bash
linode-cli build status --verbose
```

Recent events and detected issues in terminal.

### 3. HTTP API

```bash
curl http://<instance-ip>:9090/events
curl http://<instance-ip>:9090/issues
curl http://<instance-ip>:9090/status
curl http://<instance-ip>:9090/health
```

### 4. SSH + Logs

```bash
ssh root@<instance-ip>
tail -f /var/log/build-watcher/events.log
tail -f /var/log/build-watcher/errors.log
systemctl status build-watcher
```

## What BuildWatch Monitors

- ✅ Container starts, stops, restarts
- ✅ Container crashes (with exit codes)
- ✅ OOM (Out of Memory) kills
- ✅ Restart loops (3+ restarts in 5 minutes)
- ✅ System metrics (CPU, memory, disk)

## Issue Detection

**🔴 Critical: OOM Kill (exit code 137)**
- Container killed due to out of memory
- Recommendation: Increase memory or optimize app

**🟡 Warning: Restart Loop**
- 3+ restarts in 5 minutes
- Recommendation: Check application logs

## When to Use BuildWatch

✅ **Recommended for:**
- GPU workloads (detect OOM issues)
- Production deployments
- Long-running services
- Debugging container issues

❌ **Skip for:**
- Simple test deployments
- Minimal resource requirements
- No monitoring needed

## Complete Documentation

For comprehensive BuildWatch documentation including:
- API endpoints
- Log file formats
- Advanced usage examples
- Custom monitoring scripts
- Troubleshooting guide

See: **[Capabilities Reference - BuildWatch Section](capabilities.md#buildwatch-container-monitoring)**

## Migration Note

BuildWatch was previously auto-installed on all deployments. As of version 2.0, it's now optional. To continue using BuildWatch, add it to your template's capabilities list.

See: [Migration Guide](../BUILDWATCH_OPTIONAL_CAPABILITY.md)
