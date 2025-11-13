"""Thin Linode API wrapper using HTTP requests."""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, Optional

import requests


class LinodeAPIError(RuntimeError):
    """Raised when API operations fail."""


class LinodeAPI:
    def __init__(self, context) -> None:
        token = getattr(context, "token", None)
        client = getattr(context, "client", None)
        if not token or client is None:
            raise LinodeAPIError("Plugin context missing Linode CLI client or token")

        spec_base_url = getattr(client, "ops", {}).get("_base_url") if getattr(client, "ops", None) else None
        if spec_base_url:
            base_url = spec_base_url
        else:
            base_url = getattr(client, "base_url", "https://api.linode.com/v4")
            if not base_url.rstrip("/").endswith("/v4"):
                base_url = base_url.rstrip("/") + "/v4"
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": getattr(client, "user_agent", "linode-cli-ai"),
            }
        )

    # API endpoints -----------------------------------------------------

    def create_instance(
        self,
        *,
        region: str,
        linode_type: str,
        image: str,
        label: str,
        tags: Optional[list[str]] = None,
        user_data: str,
        root_pass: str,
        group: str = "build-ai",
    ) -> Dict[str, Any]:
        b64_user_data = base64.b64encode(user_data.encode("utf-8")).decode("utf-8")
        payload = {
            "type": linode_type,
            "region": region,
            "image": image,
            "label": label,
            "tags": tags or [],
            "group": group,
            "root_pass": root_pass,
            "metadata": {"user_data": b64_user_data},
        }
        response = self._request("post", "linode/instances", payload)
        return response

    def get_instance(self, instance_id: int) -> Dict[str, Any]:
        return self._request("get", f"linode/instances/{instance_id}")

    def delete_instance(self, instance_id: int) -> None:
        self._request("delete", f"linode/instances/{instance_id}")

    # Helpers -----------------------------------------------------------

    @staticmethod
    def derive_hostname(ipv4: str) -> str:
        octets = ipv4.split(".")
        return f"{'-'.join(octets)}.ip.linodeusercontent.com"

    def wait_for_status(
        self, instance_id: int, desired: str = "running", timeout: int = 600, poll: int = 10
    ) -> Dict[str, Any]:
        """Poll Linode until it reaches the desired status or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self.get_instance(instance_id)
            if data.get("status") == desired:
                return data
            time.sleep(poll)
        raise LinodeAPIError(
            f"Linode {instance_id} did not reach status {desired} within {timeout}s"
        )

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self._base_url}/{path}"
        try:
            response = self._session.request(method.upper(), url, json=payload, timeout=120)
        except requests.RequestException as exc:
            raise LinodeAPIError(str(exc)) from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise LinodeAPIError(f"API error ({response.status_code}): {detail}")

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise LinodeAPIError("Failed to parse API response as JSON") from exc
