#!/usr/bin/env python3
"""BuildWatch - Real-time Container Monitoring Service

Watches Docker events, tracks container lifecycle, detects issues,
and provides HTTP API for status and logs.
"""

import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


# Configuration
LOG_DIR = Path("/var/log/build-watcher")
STATE_DIR = Path("/var/lib/build-watcher")
STATE_FILE = STATE_DIR / "state.json"
HTTP_PORT = 9090
MAX_EVENTS_IN_MEMORY = 500
MAX_ISSUES_IN_MEMORY = 100


class DockerWatcher(threading.Thread):
    """Background thread that watches Docker events in real-time."""
    
    def __init__(self, state_manager, issue_detector):
        super().__init__(daemon=True)
        self.state_manager = state_manager
        self.issue_detector = issue_detector
        self.running = True
        self.events = deque(maxlen=MAX_EVENTS_IN_MEMORY)
        self.lock = threading.Lock()
        
    def run(self):
        """Main event watching loop."""
        log_info("Docker watcher started")
        
        while self.running:
            try:
                # Wait for Docker to be available
                if not self._wait_for_docker():
                    continue
                
                # Start docker events process
                process = subprocess.Popen(
                    ['docker', 'events', '--format', '{{json .}}'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                log_info("Watching docker events...")
                
                # Process events line by line
                for line in iter(process.stdout.readline, ''):
                    if not self.running:
                        process.terminate()
                        break
                        
                    if line.strip():
                        try:
                            event = json.loads(line)
                            self.handle_event(event)
                        except json.JSONDecodeError as e:
                            log_error(f"Failed to parse docker event: {e}")
                
                # Clean up process
                process.wait(timeout=5)
                
                # Process exited, restart if still running
                if self.running:
                    log_info("Docker events stream ended, reconnecting in 5s...")
                    time.sleep(5)
                    
            except Exception as e:
                log_error(f"Error in docker watcher: {e}")
                if self.running:
                    time.sleep(5)
    
    def _wait_for_docker(self, max_wait: int = 60) -> bool:
        """Wait for Docker to be available.
        
        Args:
            max_wait: Maximum seconds to wait
            
        Returns:
            True if Docker is available, False if should stop
        """
        waited = 0
        while self.running and waited < max_wait:
            try:
                result = subprocess.run(
                    ['docker', 'info'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass
            
            if waited == 0:
                log_info("Waiting for Docker to be available...")
            time.sleep(2)
            waited += 2
        
        return self.running  # False if stopped, True if max_wait exceeded
    
    def handle_event(self, event: Dict[str, Any]):
        """Process a Docker event."""
        try:
            event_type = event.get('status', '')
            actor = event.get('Actor', {})
            attributes = actor.get('Attributes', {})
            container_name = attributes.get('name', '')
            container_id = event.get('id', '')[:12]
            image = attributes.get('image', '')
            
            # Skip non-container events
            if event.get('Type') != 'container':
                return
            
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Build log event
            log_event = {
                "timestamp": timestamp,
                "type": event_type,
                "container": container_name,
                "image": image,
                "id": container_id
            }
            
            # Add extra info for specific event types
            if event_type == 'die':
                exit_code = attributes.get('exitCode', '')
                log_event['exit_code'] = int(exit_code) if exit_code else None
            
            # Store event in memory
            with self.lock:
                self.events.append(log_event)
            
            # Write to log file
            log_to_file(LOG_DIR / "events.log", log_event)
            
            # Update container state
            self.state_manager.update_container_state(event)
            
            # Check for issues
            self.issue_detector.check_for_issues(event)
            
        except Exception as e:
            log_error(f"Error handling event: {e}")
    
    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent events from memory."""
        with self.lock:
            events_list = list(self.events)
        
        # Return most recent first
        return list(reversed(events_list[-limit:]))
    
    def stop(self):
        """Stop the watcher thread."""
        self.running = False


class IssueDetector:
    """Detects common container issues."""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.restart_counts = {}
        self.last_restart_time = {}
        self.issues = deque(maxlen=MAX_ISSUES_IN_MEMORY)
        self.lock = threading.Lock()
    
    def check_for_issues(self, event: Dict[str, Any]):
        """Analyze event for potential issues."""
        try:
            event_type = event.get('status', '')
            actor = event.get('Actor', {})
            attributes = actor.get('Attributes', {})
            container_name = attributes.get('name', '')
            
            # OOM Kill detection
            if event_type == 'die':
                exit_code = attributes.get('exitCode', '')
                if exit_code == '137':  # SIGKILL (often OOM)
                    self.log_issue({
                        "type": "oom_killed",
                        "severity": "critical",
                        "container": container_name,
                        "message": "Container killed - likely out of memory",
                        "recommendation": "Increase memory limit or optimize application"
                    })
            
            # Frequent restart detection
            if event_type == 'start':
                now = time.time()
                if container_name in self.last_restart_time:
                    time_since_last = now - self.last_restart_time[container_name]
                    
                    if time_since_last < 300:  # Within 5 minutes
                        self.restart_counts[container_name] = self.restart_counts.get(container_name, 0) + 1
                        
                        if self.restart_counts[container_name] >= 3:
                            self.log_issue({
                                "type": "frequent_restarts",
                                "severity": "warning",
                                "container": container_name,
                                "restart_count": self.restart_counts[container_name],
                                "message": f"Container restarted {self.restart_counts[container_name]} times in 5 minutes"
                            })
                    else:
                        # Reset count if more than 5 minutes passed
                        self.restart_counts[container_name] = 0
                
                self.last_restart_time[container_name] = now
            
            # Health check failures
            if 'unhealthy' in event_type:
                self.log_issue({
                    "type": "health_check_failed",
                    "severity": "warning",
                    "container": container_name,
                    "message": "Container health check failing"
                })
                
        except Exception as e:
            log_error(f"Error checking for issues: {e}")
    
    def log_issue(self, issue: Dict[str, Any]):
        """Log a detected issue."""
        timestamp = datetime.now(timezone.utc).isoformat()
        issue['timestamp'] = timestamp
        issue['resolved'] = False
        
        with self.lock:
            self.issues.append(issue)
        
        # Write to log file
        log_to_file(LOG_DIR / "errors.log", issue)
        
        # Update state
        self.state_manager.add_issue(issue)
        
        log_info(f"Issue detected: {issue['type']} - {issue['message']}")
    
    def get_issues(self, unresolved_only: bool = False) -> List[Dict[str, Any]]:
        """Get detected issues."""
        with self.lock:
            issues_list = list(self.issues)
        
        if unresolved_only:
            issues_list = [i for i in issues_list if not i.get('resolved', False)]
        
        return list(reversed(issues_list))


class StateManager:
    """Manages container state and persistence."""
    
    def __init__(self):
        self.state = {
            "containers": {},
            "deployment": {
                "id": os.environ.get("BUILD_DEPLOYMENT_ID", "unknown"),
                "app_name": os.environ.get("BUILD_APP_NAME", "unknown"),
                "started_at": datetime.now(timezone.utc).isoformat()
            },
            "issues": []
        }
        self.lock = threading.Lock()
        self.load_state()
    
    def load_state(self):
        """Load state from disk."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    self.state = json.load(f)
                log_info("Loaded state from disk")
        except Exception as e:
            log_error(f"Failed to load state: {e}")
    
    def save_state(self):
        """Save state to disk."""
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            log_error(f"Failed to save state: {e}")
    
    def update_container_state(self, event: Dict[str, Any]):
        """Update container state based on event."""
        try:
            event_type = event.get('status', '')
            actor = event.get('Actor', {})
            attributes = actor.get('Attributes', {})
            container_name = attributes.get('name', '')
            container_id = event.get('id', '')[:12]
            image = attributes.get('image', '')
            
            with self.lock:
                if container_name not in self.state['containers']:
                    self.state['containers'][container_name] = {
                        "id": container_id,
                        "image": image,
                        "status": "unknown",
                        "restart_count": 0,
                        "total_uptime_seconds": 0
                    }
                
                container = self.state['containers'][container_name]
                container['id'] = container_id
                
                if event_type == 'start':
                    container['status'] = 'running'
                    container['started_at'] = datetime.now(timezone.utc).isoformat()
                    if 'stopped_at' in container:
                        container['restart_count'] = container.get('restart_count', 0) + 1
                
                elif event_type in ('stop', 'die', 'kill'):
                    container['status'] = 'stopped'
                    container['stopped_at'] = datetime.now(timezone.utc).isoformat()
                    
                    if event_type == 'die':
                        exit_code = attributes.get('exitCode', '')
                        container['last_exit_code'] = int(exit_code) if exit_code else None
            
            # Save state periodically (every state change)
            self.save_state()
            
        except Exception as e:
            log_error(f"Error updating container state: {e}")
    
    def add_issue(self, issue: Dict[str, Any]):
        """Add an issue to state."""
        with self.lock:
            self.state['issues'].append(issue)
            # Keep only last 100 issues
            self.state['issues'] = self.state['issues'][-100:]
        self.save_state()
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        with self.lock:
            return dict(self.state)


class MetricsCollector(threading.Thread):
    """Collects system metrics periodically."""
    
    def __init__(self, interval: int = 60):
        super().__init__(daemon=True)
        self.interval = interval
        self.running = True
    
    def run(self):
        """Collect metrics periodically."""
        log_info(f"Metrics collector started (interval: {self.interval}s)")
        
        while self.running:
            try:
                self.collect_metrics()
                time.sleep(self.interval)
            except Exception as e:
                log_error(f"Error collecting metrics: {e}")
                time.sleep(self.interval)
    
    def collect_metrics(self):
        """Collect and log system metrics."""
        try:
            # Get CPU load
            with open('/proc/loadavg') as f:
                load_avg = f.read().split()[0]
            
            # Get memory usage
            mem_total = 0
            mem_available = 0
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_total = int(line.split()[1])
                    elif line.startswith('MemAvailable:'):
                        mem_available = int(line.split()[1])
            
            mem_used_percent = ((mem_total - mem_available) / mem_total * 100) if mem_total > 0 else 0
            
            # Get disk usage
            result = subprocess.run(
                ['df', '-h', '/'],
                capture_output=True,
                text=True
            )
            disk_used_percent = 0
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) > 4:
                        disk_used_percent = float(parts[4].rstrip('%'))
            
            metrics = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cpu_load": float(load_avg),
                "memory_used_percent": round(mem_used_percent, 2),
                "disk_used_percent": disk_used_percent
            }
            
            log_to_file(LOG_DIR / "metrics.log", metrics)
            
        except Exception as e:
            log_error(f"Error in collect_metrics: {e}")
    
    def stop(self):
        """Stop the metrics collector."""
        self.running = False


class StatusLogger(threading.Thread):
    """Logs periodic status snapshots."""
    
    def __init__(self, state_manager, interval: int = 300):
        super().__init__(daemon=True)
        self.state_manager = state_manager
        self.interval = interval
        self.running = True
    
    def run(self):
        """Log status periodically."""
        log_info(f"Status logger started (interval: {self.interval}s)")
        
        while self.running:
            try:
                self.log_status()
                time.sleep(self.interval)
            except Exception as e:
                log_error(f"Error logging status: {e}")
                time.sleep(self.interval)
    
    def log_status(self):
        """Log current container status."""
        try:
            # Get container stats
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{json .}}'],
                capture_output=True,
                text=True
            )
            
            containers = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container = json.loads(line)
                        containers.append({
                            "name": container.get('Names', ''),
                            "status": container.get('Status', ''),
                            "image": container.get('Image', '')
                        })
            
            status = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "containers": containers
            }
            
            log_to_file(LOG_DIR / "status.log", status)
            
        except Exception as e:
            log_error(f"Error logging status: {e}")
    
    def stop(self):
        """Stop the status logger."""
        self.running = False


class BuildWatchHandler(BaseHTTPRequestHandler):
    """HTTP request handler for BuildWatch API."""
    
    def do_GET(self):
        """Handle GET requests."""
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query_params = parse_qs(parsed.query)
            
            if path == '/health':
                self.handle_health()
            elif path == '/status':
                self.handle_status()
            elif path == '/events':
                limit = int(query_params.get('limit', ['50'])[0])
                self.handle_events(limit)
            elif path == '/issues':
                self.handle_issues()
            elif path == '/logs':
                container = query_params.get('container', [None])[0]
                lines = int(query_params.get('lines', ['100'])[0])
                self.handle_logs(container, lines)
            elif path == '/container':
                name = query_params.get('name', [None])[0]
                self.handle_container(name)
            else:
                self.send_error(404, "Not found")
        
        except Exception as e:
            log_error(f"Error handling request: {e}")
            self.send_error(500, str(e))
    
    def handle_health(self):
        """Health check endpoint."""
        response = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "buildwatch"
        }
        self.send_json_response(response)
    
    def handle_status(self):
        """Get current state."""
        state = self.server.state_manager.get_state()
        self.send_json_response(state)
    
    def handle_events(self, limit: int):
        """Get recent events."""
        events = self.server.docker_watcher.get_recent_events(limit)
        response = {
            "events": events,
            "count": len(events)
        }
        self.send_json_response(response)
    
    def handle_issues(self):
        """Get detected issues."""
        issues = self.server.issue_detector.get_issues()
        response = {
            "issues": issues,
            "count": len(issues)
        }
        self.send_json_response(response)
    
    def handle_logs(self, container: Optional[str], lines: int):
        """Get container logs."""
        if not container:
            self.send_error(400, "container parameter required")
            return
        
        try:
            result = subprocess.run(
                ['docker', 'logs', '--tail', str(lines), container],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            response = {
                "container": container,
                "logs": result.stdout.split('\n')
            }
            self.send_json_response(response)
            
        except subprocess.TimeoutExpired:
            self.send_error(504, "Timeout getting logs")
        except Exception as e:
            self.send_error(500, str(e))
    
    def handle_container(self, name: Optional[str]):
        """Get specific container info."""
        if not name:
            self.send_error(400, "name parameter required")
            return
        
        try:
            # Get container details
            result = subprocess.run(
                ['docker', 'inspect', name],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.send_error(404, f"Container {name} not found")
                return
            
            container_info = json.loads(result.stdout)[0]
            
            # Get stats
            stats_result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', '{{json .}}', name],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            stats = {}
            if stats_result.returncode == 0 and stats_result.stdout.strip():
                stats = json.loads(stats_result.stdout)
            
            response = {
                "name": name,
                "info": container_info,
                "stats": stats
            }
            self.send_json_response(response)
            
        except Exception as e:
            self.send_error(500, str(e))
    
    def send_json_response(self, data: Any):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass


def log_info(message: str):
    """Log info message."""
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] INFO: {message}", flush=True)


def log_error(message: str):
    """Log error message."""
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] ERROR: {message}", file=sys.stderr, flush=True)


def log_to_file(filepath: Path, data: Dict[str, Any]):
    """Append JSON line to log file."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'a') as f:
            f.write(json.dumps(data) + '\n')
    except Exception as e:
        log_error(f"Failed to write to {filepath}: {e}")


def main():
    """Main entry point."""
    log_info("Starting BuildWatch service...")
    
    # Ensure directories exist
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    state_manager = StateManager()
    issue_detector = IssueDetector(state_manager)
    docker_watcher = DockerWatcher(state_manager, issue_detector)
    metrics_collector = MetricsCollector(interval=60)
    status_logger = StatusLogger(state_manager, interval=300)
    
    # Start background threads
    docker_watcher.start()
    metrics_collector.start()
    status_logger.start()
    
    # Create HTTP server
    server = HTTPServer(('0.0.0.0', HTTP_PORT), BuildWatchHandler)
    server.state_manager = state_manager
    server.docker_watcher = docker_watcher
    server.issue_detector = issue_detector
    
    log_info(f"BuildWatch API listening on port {HTTP_PORT}")
    log_info("Service ready")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_info("Shutting down...")
        docker_watcher.stop()
        metrics_collector.stop()
        status_logger.stop()
        server.shutdown()


if __name__ == '__main__':
    main()

