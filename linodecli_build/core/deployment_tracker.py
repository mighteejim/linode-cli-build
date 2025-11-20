"""API-first deployment tracking using Linode tags."""

from pathlib import Path
import json
from typing import Optional, List, Dict, Any
import yaml


class DeploymentTracker:
    """API-first deployment tracking using Linode tags."""
    
    def __init__(self, client):
        self.client = client
        self.metadata_file = Path.home() / ".config/linode-cli.d/build/deployment-metadata.json"
    
    def list_deployments(self, app_name: Optional[str] = None, env: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all deployments from Linode API.
        
        Returns deployments with live state from API + cached metadata.
        """
        status, response = self.client.call_operation('linodes', 'list', [])
        
        if status != 200:
            raise Exception(f"Failed to list Linodes: {response}")
        
        deployments = []
        
        for linode in response.get('data', []):
            tags = linode.get('tags', [])
            
            # Parse build tags
            build_tags = self._parse_build_tags(tags)
            
            # Must have build-id tag to be a deployment
            if not build_tags.get('id'):
                continue
            
            # Apply filters
            if app_name and build_tags.get('app') != app_name:
                continue
            if env and build_tags.get('env') != env:
                continue
            
            # Get cached metadata
            metadata = self._get_metadata(linode['id'])
            
            # Build deployment object from live API data
            deployment = {
                # Primary identifier
                'deployment_id': build_tags['id'],
                'linode_id': linode['id'],
                
                # From tags
                'app_name': build_tags.get('app', 'unknown'),
                'env': build_tags.get('env', 'default'),
                'template': build_tags.get('tmpl', 'unknown'),
                
                # Live from API
                'status': linode.get('status', 'unknown'),
                'ipv4': linode.get('ipv4', []),
                'region': linode.get('region', 'unknown'),
                'type': linode.get('type', 'unknown'),
                'created': linode.get('created'),
                'label': linode.get('label'),
                
                # From cached metadata (supplementary)
                'created_from': metadata.get('created_from'),
                'health_config': metadata.get('health_config'),
                'hostname': metadata.get('hostname'),
                'external_port': metadata.get('external_port'),
                'internal_port': metadata.get('internal_port'),
            }
            
            deployments.append(deployment)
        
        return deployments
    
    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Get specific deployment by ID."""
        deployments = self.list_deployments()
        for dep in deployments:
            if dep['deployment_id'] == deployment_id or dep['deployment_id'].startswith(deployment_id):
                return dep
        return None
    
    def get_deployment_by_linode_id(self, linode_id: int) -> Optional[Dict[str, Any]]:
        """Get deployment by Linode ID."""
        deployments = self.list_deployments()
        for dep in deployments:
            if dep['linode_id'] == linode_id:
                return dep
        return None
    
    def find_deployment_for_directory(self, directory: Path) -> Optional[Dict[str, Any]]:
        """
        Find deployment(s) that were created from this directory.
        
        Uses cached metadata to match directory.
        Returns most recent if multiple.
        """
        dir_str = str(directory.absolute())
        
        deployments = self.list_deployments()
        matches = [d for d in deployments if d.get('created_from') == dir_str]
        
        if not matches:
            # Fallback: try to match by app name from deploy.yml
            deploy_yml = directory / "deploy.yml"
            if deploy_yml.exists():
                try:
                    data = yaml.safe_load(deploy_yml.read_text())
                    app_name = data.get('name')
                    if app_name:
                        matches = self.list_deployments(app_name=app_name)
                except:
                    pass
        
        if not matches:
            return None
        
        # Return most recent
        matches.sort(key=lambda d: d.get('created', ''), reverse=True)
        return matches[0]
    
    def _parse_build_tags(self, tags: List[str]) -> Dict[str, str]:
        """Parse build-* tags into dict."""
        build_tags = {}
        for tag in tags:
            if tag.startswith('build-'):
                parts = tag.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].replace('build-', '')
                    build_tags[key] = parts[1]
        return build_tags
    
    def save_metadata(self, linode_id: int, metadata: Dict[str, Any]) -> None:
        """Save supplementary metadata for a deployment."""
        all_metadata = self._load_metadata_file()
        all_metadata[str(linode_id)] = metadata
        self._save_metadata_file(all_metadata)
    
    def _get_metadata(self, linode_id: int) -> Dict[str, Any]:
        """Get cached metadata for a deployment."""
        all_metadata = self._load_metadata_file()
        return all_metadata.get(str(linode_id), {})
    
    def cleanup_stale_metadata(self) -> int:
        """Remove metadata for Linodes that no longer exist."""
        all_metadata = self._load_metadata_file()
        
        # Get all current Linode IDs from API
        deployments = self.list_deployments()
        current_ids = {str(d['linode_id']) for d in deployments}
        
        # Remove metadata for non-existent Linodes
        stale_ids = set(all_metadata.keys()) - current_ids
        for linode_id in stale_ids:
            del all_metadata[linode_id]
        
        self._save_metadata_file(all_metadata)
        return len(stale_ids)
    
    def _load_metadata_file(self) -> Dict[str, Dict[str, Any]]:
        """Load metadata from disk."""
        if not self.metadata_file.exists():
            return {}
        try:
            return json.loads(self.metadata_file.read_text())
        except:
            return {}
    
    def _save_metadata_file(self, metadata: Dict[str, Dict[str, Any]]) -> None:
        """Save metadata to disk."""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_file.write_text(json.dumps(metadata, indent=2))
