"""Utility functions for TUI components."""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


def format_uptime(seconds: int) -> str:
    """
    Format seconds into human-readable uptime.
    
    Args:
        seconds: Number of seconds
        
    Returns:
        Formatted string like "2h 15m" or "45s"
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    minutes = minutes % 60
    
    if hours < 24:
        return f"{hours}h {minutes}m"
    
    days = hours // 24
    hours = hours % 24
    return f"{days}d {hours}h"


def format_timestamp(timestamp: str) -> str:
    """
    Format ISO timestamp to relative time.
    
    Args:
        timestamp: ISO format timestamp string
        
    Returns:
        Relative time string like "2 hours ago"
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo)
        delta = now - dt
        
        if delta.total_seconds() < 60:
            return "just now"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"
    except Exception:
        return timestamp


def format_elapsed_time(start_time: float) -> str:
    """
    Format elapsed time from start timestamp.
    
    Args:
        start_time: Start time (time.time())
        
    Returns:
        Formatted elapsed time like "02:45"
    """
    import time
    elapsed = int(time.time() - start_time)
    minutes = elapsed // 60
    seconds = elapsed % 60
    return f"{minutes:02d}:{seconds:02d}"


def get_status_emoji(status: str) -> str:
    """
    Get emoji for instance/container status.
    
    Args:
        status: Status string
        
    Returns:
        Emoji character
    """
    status_map = {
        "running": "●",
        "provisioning": "⏳",
        "booting": "⏳",
        "offline": "○",
        "stopped": "○",
        "complete": "✓",
        "failed": "✗",
        "active": "⏳",
        "pending": "○",
    }
    return status_map.get(status.lower(), "○")


def get_status_color(status: str) -> str:
    """
    Get color for status display.
    
    Args:
        status: Status string
        
    Returns:
        Color name for Rich styling
    """
    status_map = {
        "running": "green",
        "provisioning": "yellow",
        "booting": "yellow",
        "offline": "red",
        "stopped": "red",
        "complete": "green",
        "failed": "red",
        "active": "yellow",
        "pending": "dim",
    }
    return status_map.get(status.lower(), "white")


def load_deployment_state(project_dir: str) -> Optional[Dict[str, Any]]:
    """
    Load deployment state from project directory.
    
    Args:
        project_dir: Project directory path
        
    Returns:
        Deployment state dictionary or None
    """
    state_file = os.path.join(project_dir, ".linode", "state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading deployment state: {e}")
    return None


def save_deployment_state(project_dir: str, state: Dict[str, Any]) -> bool:
    """
    Save deployment state to project directory.
    
    Args:
        project_dir: Project directory path
        state: State dictionary to save
        
    Returns:
        True if successful, False otherwise
    """
    state_dir = os.path.join(project_dir, ".linode")
    state_file = os.path.join(state_dir, "state.json")
    
    try:
        os.makedirs(state_dir, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving deployment state: {e}")
        return False


def truncate_text(text: str, max_length: int = 50) -> str:
    """
    Truncate text with ellipsis if too long.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def parse_docker_logs(logs: str, max_lines: int = 10) -> list[str]:
    """
    Parse Docker logs and return recent lines.
    
    Args:
        logs: Raw log string
        max_lines: Maximum number of lines to return
        
    Returns:
        List of log lines
    """
    if not logs:
        return []
    
    lines = logs.split('\n')
    # Filter empty lines
    lines = [line for line in lines if line.strip()]
    # Return last N lines
    return lines[-max_lines:]


def get_region_display_name(region_id: str) -> str:
    """
    Get human-readable region name.
    
    Args:
        region_id: Region ID like "us-ord"
        
    Returns:
        Display name like "Chicago, IL"
    """
    region_map = {
        "us-ord": "Chicago, IL",
        "us-east": "Newark, NJ",
        "us-central": "Dallas, TX",
        "us-west": "Fremont, CA",
        "us-southeast": "Atlanta, GA",
        "eu-west": "London, UK",
        "eu-central": "Frankfurt, DE",
        "ap-south": "Singapore, SG",
        "ap-northeast": "Tokyo, JP",
        "ap-west": "Mumbai, IN",
        "ca-central": "Toronto, CA",
        "ap-southeast": "Sydney, AU",
    }
    return region_map.get(region_id, region_id)


def format_price(hourly_price: float) -> str:
    """
    Format hourly price for display.
    
    Args:
        hourly_price: Price per hour
        
    Returns:
        Formatted price string
    """
    return f"${hourly_price:.2f}/hour"
