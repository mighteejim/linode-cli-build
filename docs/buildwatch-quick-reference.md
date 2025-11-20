# BuildWatch Quick Reference

> **Note:** BuildWatch is now **optional**. Add to your template explicitly.

## Enable BuildWatch

```yaml
capabilities:
  runtime: docker
  features:
    - buildwatch
```

Or with config:
```yaml
features:
  - name: buildwatch
    config:
      port: 9090
      log_retention_days: 7
      enable_metrics: true
```

## Access Methods

| Method | Command |
|--------|---------|
| **TUI** | `linode-cli build tui` |
| **CLI** | `linode-cli build status --verbose` |
| **API** | `curl http://<ip>:9090/events` |
| **SSH** | `tail -f /var/log/build-watcher/events.log` |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Service health check |
| `/status` | Full deployment state |
| `/events?limit=N` | Recent container events |
| `/issues` | Detected problems |
| `/logs?container=X&lines=N` | Container logs |

## Issue Detection

| Issue | Detection | Severity |
|-------|-----------|----------|
| OOM Kill | Exit code 137 | 🔴 Critical |
| Restart Loop | 3+ restarts in 5 min | 🟡 Warning |
| Health Failure | Unhealthy status | 🟡 Warning |

## Log Files

```
/var/log/build-watcher/
├── events.log      # Container events
├── status.log      # Status snapshots (5 min)
├── metrics.log     # System metrics (1 min)
└── errors.log      # Detected issues
```

## Service Management

```bash
systemctl status build-watcher
journalctl -u build-watcher -f
systemctl restart build-watcher
```

## When to Use

✅ GPU workloads, production, long-running services  
❌ Simple tests, minimal resource needs

## Full Documentation

See **[Capabilities Reference](capabilities.md#buildwatch-container-monitoring)** for complete documentation.
