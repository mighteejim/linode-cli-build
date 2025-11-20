# BuildWatch Quick Reference

## 🎯 **TL;DR**

BuildWatch is **automatically enabled** on all deployments. No template config needed!

## 📝 **Template Configuration**

```yaml
# Nothing special needed! Just deploy normally:
capabilities:
  runtime: docker    # BuildWatch monitors Docker automatically
```

## 🖥️ **Accessing BuildWatch**

### Option 1: TUI (Interactive Dashboard)
```bash
linode-cli build tui <deployment-id>
```
→ Live events, issues, and recommendations

### Option 2: CLI (Terminal Output)
```bash
linode-cli build status --verbose
```
→ Recent events and detected issues

### Option 3: HTTP API (Programmatic)
```bash
curl http://<instance-ip>:9090/events?limit=20
curl http://<instance-ip>:9090/issues
curl http://<instance-ip>:9090/logs?container=app&lines=100
curl http://<instance-ip>:9090/status
curl http://<instance-ip>:9090/health
```

## 📊 **API Endpoints**

| Endpoint | Description |
|----------|-------------|
| `/health` | Service health check |
| `/status` | Full deployment state |
| `/events?limit=N` | Recent container events |
| `/issues` | Detected problems |
| `/logs?container=X&lines=N` | Container logs |
| `/container?name=X` | Container details |

## 🚨 **Issue Detection**

| Issue | Detection | Severity |
|-------|-----------|----------|
| OOM Kill | Exit code 137 | 🔴 Critical |
| Restart Loop | 3+ restarts in 5 min | 🟡 Warning |
| Health Failure | Unhealthy status | 🟡 Warning |

## 📁 **Log Files on Instance**

```
/var/log/build-watcher/
├── events.log      # Container events
├── status.log      # Status snapshots (5 min)
├── metrics.log     # System metrics (1 min)
└── errors.log      # Detected issues
```

## 🔧 **Service Management**

```bash
# Status
systemctl status build-watcher

# Logs
journalctl -u build-watcher -f

# Restart
systemctl restart build-watcher
```

## 💡 **Key Features**

✅ Zero configuration required  
✅ Real-time event monitoring  
✅ Automatic issue detection  
✅ Multiple access methods  
✅ Persistent logs (7-day rotation)  
✅ Lightweight & reliable  

## 📚 **Full Documentation**

See `docs/buildwatch-usage.md` for detailed usage guide.
