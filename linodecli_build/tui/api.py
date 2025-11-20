"""Linode API wrapper with rate limiting and caching for TUI."""

import asyncio
import time
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import json


class APICache:
    """Simple TTL-based cache for API responses."""
    
    def __init__(self, ttl: int = 5):
        """Initialize cache with TTL in seconds."""
        self.ttl = ttl
        self.cache: Dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Cache a value with current timestamp."""
        self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cached values."""
        self.cache.clear()


class RateLimiter:
    """Rate limiter to prevent API throttling."""
    
    def __init__(self, calls_per_minute: int = 10):
        """Initialize rate limiter with calls per minute limit."""
        self.calls_per_minute = calls_per_minute
        self.calls: List[float] = []
    
    async def wait_if_needed(self) -> None:
        """Wait if we're over the rate limit."""
        now = time.time()
        # Remove calls older than 1 minute
        self.calls = [t for t in self.calls if now - t < 60]
        
        if len(self.calls) >= self.calls_per_minute:
            # Wait until oldest call is > 1 minute old
            wait_time = 60 - (now - self.calls[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            # Clean up old calls again
            now = time.time()
            self.calls = [t for t in self.calls if now - t < 60]
        
        self.calls.append(time.time())


class LinodeAPIClient:
    """Async wrapper for Linode API calls with rate limiting and caching."""
    
    def __init__(self, client, rate_limit: int = 10, cache_ttl: int = 5):
        """
        Initialize API client.
        
        Args:
            client: The linode-cli client instance
            rate_limit: Maximum API calls per minute
            cache_ttl: Cache time-to-live in seconds
        """
        self.client = client
        self.rate_limiter = RateLimiter(rate_limit)
        self.cache = APICache(cache_ttl)
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def _sync_call(self, operation: str, action: str, args: List[str]) -> tuple[int, Any]:
        """Make synchronous API call (to be run in executor)."""
        try:
            return self.client.call_operation(operation, action, args)
        except Exception as e:
            return (1, {"error": str(e)})
    
    async def _call_api(self, operation: str, action: str, args: List[str], use_cache: bool = True) -> tuple[int, Any]:
        """
        Make an async API call with rate limiting and caching.
        
        Args:
            operation: API operation (e.g., 'linodes')
            action: API action (e.g., 'view')
            args: Arguments for the API call
            use_cache: Whether to use cached responses
            
        Returns:
            Tuple of (status_code, response_data)
        """
        cache_key = f"{operation}:{action}:{':'.join(args)}"
        
        # Check cache first
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Rate limit
        await self.rate_limiter.wait_if_needed()
        
        # Make API call in executor to avoid blocking
        loop = asyncio.get_event_loop()
        status, response = await loop.run_in_executor(
            self.executor,
            self._sync_call,
            operation,
            action,
            args
        )
        
        # Cache successful responses
        if status == 0 and use_cache:
            self.cache.set(cache_key, (status, response))
        
        return status, response
    
    async def get_instance(self, instance_id: int) -> Optional[Dict[str, Any]]:
        """
        Get instance details with caching.
        
        Args:
            instance_id: Linode instance ID
            
        Returns:
            Instance data dictionary or None on error
        """
        try:
            status, response = await self._call_api('linodes', 'view', [str(instance_id)])
            if status == 0:
                return response
        except Exception as e:
            print(f"Error fetching instance {instance_id}: {e}")
        return None
    
    async def get_instance_logs(self, instance_id: int, lines: int = 50) -> Optional[str]:
        """
        Get cloud-init/console logs for an instance.
        
        Note: This is a placeholder. Linode API may not provide direct log access.
        In production, you might need to use Lish or SSH.
        
        Args:
            instance_id: Linode instance ID
            lines: Number of log lines to retrieve
            
        Returns:
            Log content as string or None
        """
        # TODO: Implement actual log retrieval
        # This might require SSH access or Lish console API
        return None
    
    async def list_instances(self) -> List[Dict[str, Any]]:
        """
        List all instances.
        
        Returns:
            List of instance dictionaries
        """
        try:
            status, response = await self._call_api('linodes', 'list', [], use_cache=True)
            if status == 0 and isinstance(response, list):
                return response
        except Exception as e:
            print(f"Error listing instances: {e}")
        return []
    
    async def get_container_status(self, instance: Dict[str, Any], ssh_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get Docker container status (via SSH or other means).
        
        Note: This requires SSH access to the instance.
        For MVP, this might just return placeholder data.
        
        Args:
            instance: Instance data dictionary
            ssh_key: Optional SSH key path for authentication
            
        Returns:
            Container status dictionary or None
        """
        # TODO: Implement SSH-based container status check
        # For MVP, return placeholder
        return {
            "name": "app",
            "status": "running",
            "uptime": "N/A",
            "health": "unknown"
        }
    
    def clear_cache(self) -> None:
        """Clear all cached API responses."""
        self.cache.clear()
    
    async def fetch_buildwatch_status(self, ipv4: str) -> Optional[Dict[str, Any]]:
        """
        Fetch BuildWatch status from deployed instance.
        
        Args:
            ipv4: Instance IPv4 address
            
        Returns:
            BuildWatch status dictionary or None on error
        """
        try:
            url = f"http://{ipv4}:9090/status"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                self._http_get,
                url,
                3  # timeout
            )
            return response
        except Exception as e:
            # Service may not be ready yet or instance down
            return None
    
    async def fetch_buildwatch_events(self, ipv4: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent container events from BuildWatch.
        
        Args:
            ipv4: Instance IPv4 address
            limit: Maximum number of events to fetch
            
        Returns:
            List of event dictionaries
        """
        try:
            url = f"http://{ipv4}:9090/events?limit={limit}"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                self._http_get,
                url,
                3  # timeout
            )
            if response and 'events' in response:
                return response['events']
        except Exception:
            pass
        return []
    
    async def fetch_buildwatch_issues(self, ipv4: str) -> List[Dict[str, Any]]:
        """
        Fetch detected issues from BuildWatch.
        
        Args:
            ipv4: Instance IPv4 address
            
        Returns:
            List of issue dictionaries
        """
        try:
            url = f"http://{ipv4}:9090/issues"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                self._http_get,
                url,
                3  # timeout
            )
            if response and 'issues' in response:
                return response['issues']
        except Exception:
            pass
        return []
    
    async def fetch_container_logs(self, ipv4: str, container: str, lines: int = 100) -> List[str]:
        """
        Fetch container logs via BuildWatch.
        
        Args:
            ipv4: Instance IPv4 address
            container: Container name
            lines: Number of log lines to fetch
            
        Returns:
            List of log lines
        """
        try:
            url = f"http://{ipv4}:9090/logs?container={container}&lines={lines}"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                self._http_get,
                url,
                5  # timeout
            )
            if response and 'logs' in response:
                return response['logs']
        except Exception:
            pass
        return []
    
    def _http_get(self, url: str, timeout: int = 3) -> Optional[Dict[str, Any]]:
        """
        Make synchronous HTTP GET request.
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            Parsed JSON response or None on error
        """
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = response.read()
                return json.loads(data.decode('utf-8'))
        except Exception:
            return None
    
    async def close(self) -> None:
        """Clean up resources."""
        self.executor.shutdown(wait=False)
