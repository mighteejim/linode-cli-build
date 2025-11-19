"""Generate comprehensive instructions for LLMs to create templates.

This module generates detailed documentation and context for LLMs (like Claude, GPT-4)
to assist users in creating new templates for the linode-cli-ai system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import yaml


class LLMInstructionsGenerator:
    """Generate comprehensive instructions for LLMs to create templates."""
    
    def __init__(self):
        self.example_templates = self._load_example_templates()
    
    def _load_example_templates(self) -> Dict[str, str]:
        """Load example templates from the templates directory."""
        examples = {}
        
        # Try to load bundled templates as examples
        try:
            from importlib import resources
            
            templates_to_load = ["llm-api", "chat-agent", "embeddings-python"]
            
            for template_name in templates_to_load:
                try:
                    resource = resources.files("linodecli_ai").joinpath(
                        f"templates/{template_name}/template.yml"
                    )
                    if resource.is_file():
                        examples[template_name] = resource.read_text(encoding="utf-8")
                except Exception:
                    continue
        except Exception:
            pass
        
        return examples
    
    def generate(self, user_input: Dict[str, Any], stub_path: str) -> str:
        """Generate comprehensive LLM instructions.
        
        Args:
            user_input: Dictionary with user's answers to prompts
            stub_path: Path to the template stub file
        
        Returns:
            Full markdown instructions for the LLM
        """
        sections = [
            self._render_header(user_input),
            self._render_task_description(),
            self._render_system_docs(),
            self._render_capabilities_reference(),
            self._render_example_templates(),
            self._render_schema_reference(),
            self._render_best_practices(),
            self._render_requirements(user_input),
            self._render_validation_checklist(),
            self._render_stub_content(stub_path),
        ]
        
        return "\n\n".join(sections)
    
    def _render_header(self, user_input: Dict[str, Any]) -> str:
        return f"""# Template Generation Instructions

## User Requirements

**Service**: {user_input.get('service_description', 'N/A')}  
**GPU Required**: {user_input.get('requires_gpu', False)}  
**Dependencies**: {user_input.get('dependencies', 'None specified')}  
**Container Image**: {user_input.get('container_image', 'To be determined')}  
**Health Check Path**: {user_input.get('health_check_path', '/health')}  
**Startup Time**: {user_input.get('startup_time', '60')} seconds  
"""
    
    def _render_task_description(self) -> str:
        return """## Task

Complete the template.yml file for this service following the linode-cli-ai template system structure.

Your goal is to create a production-ready template that:
- Uses the capabilities system for declarative requirements
- Includes comprehensive environment variable documentation
- Provides health checks with appropriate timeouts
- Includes helpful usage examples in the guidance section
- Follows best practices from existing templates
"""
    
    def _render_system_docs(self) -> str:
        return """## Template System Documentation

### Overview

The linode-cli-ai template system allows users to deploy AI services to Linode cloud instances
with minimal configuration. Templates define:

1. **What to deploy**: Container image, ports, environment variables
2. **Where to deploy**: Default region, instance type, base OS image
3. **How to set up**: Capabilities (GPU, Docker, packages) or custom scripts
4. **How to use**: Guidance, examples, and documentation

### Template Structure

A template.yml must include these core sections:

```yaml
name: unique-identifier
display_name: Human Readable Name
version: 0.1.0
description: |
  Multi-line description of what this template does

capabilities:           # Optional: Declarative requirements
  runtime: docker
  features:
    - gpu-nvidia
  packages: []

deploy:
  target: linode
  linode:
    image: linode/ubuntu22.04
    region_default: us-mia
    type_default: g6-standard-8
    tags: []
    container:
      image: docker/image:tag
      internal_port: 8000
      external_port: 80
      command: optional command override
      env: {}
      health:
        type: http
        path: /health
        port: 8000
        success_codes: [200]
        initial_delay_seconds: 60
        timeout_seconds: 10
        max_retries: 30

env:
  required: []
  optional: []

guidance:
  summary: |
    Usage instructions
  examples: []
```
"""
    
    def _render_capabilities_reference(self) -> str:
        return """## Available Capabilities

The capabilities system lets you declare requirements without writing setup scripts.

### Runtime Options

```yaml
capabilities:
  runtime: docker | native | k3s
```

- **docker**: Installs Docker and runs containerized services (most common)
- **native**: No container runtime, for native binaries/scripts
- **k3s**: Lightweight Kubernetes (advanced use cases)

### Available Features

```yaml
capabilities:
  features:
    - gpu-nvidia          # NVIDIA drivers + container toolkit
    - docker-optimize     # Enable 10 concurrent downloads
    - python-3.10         # Python 3.10 runtime
    - python-3.11         # Python 3.11 runtime  
    - python-3.12         # Python 3.12 runtime
    - nodejs-18           # Node.js 18 runtime
    - nodejs-20           # Node.js 20 runtime
    - redis               # Redis server
    - postgresql-14       # PostgreSQL 14 server
    - postgresql-15       # PostgreSQL 15 server
```

### Custom Packages

```yaml
capabilities:
  packages:
    - libcurl4
    - build-essential
    - any-apt-package
```

### Custom Setup Scripts (Advanced)

For complex scenarios not covered by capabilities:

```yaml
setup:
  script: |
    #!/bin/bash
    # Your custom setup commands
    echo "Custom setup running..."
  files:
    - path: /etc/myapp/config.yml
      content: |
        setting: value
```
"""
    
    def _render_example_templates(self) -> str:
        examples_md = """## Example Templates

Study these real templates from the system:

"""
        
        for name, content in self.example_templates.items():
            examples_md += f"""### Example: {name}

```yaml
{content.strip()}
```

"""
        
        return examples_md
    
    def _render_schema_reference(self) -> str:
        return """## Template Schema Reference

### Required Fields

**name** (string, required)
- Unique template identifier, lowercase with hyphens
- Example: `"ml-api"`, `"database-backup"`

**display_name** (string, required)
- Human-readable name shown in CLI
- Example: `"ML API"`, `"Database Backup"`

**version** (string, required)
- Semantic version: MAJOR.MINOR.PATCH
- Example: `"0.1.0"`, `"1.2.3"`

**description** (string, required)
- Multi-line description of what this template does
- Explain use case, features, and requirements
- Use YAML multi-line syntax (`|` or `>`)

**deploy** (object, required)
- Main deployment configuration
- Must include `target` and `linode` sections

**deploy.target** (string, required)
- Deployment target, always `"linode"`

**deploy.linode** (object, required)
- Linode-specific configuration
- Required fields: `image`, `region_default`, `type_default`

**deploy.linode.image** (string, required)
- Base OS image (e.g., `"linode/ubuntu22.04"`)
- **Always use `linode/ubuntu22.04` for GPU instances**

**deploy.linode.region_default** (string, required)
- Default region (e.g., `"us-mia"`, `"us-southeast"`)

**deploy.linode.type_default** (string, required)
- Default instance type (e.g., `"g6-standard-8"`, `"g6-standard-2"`)

**deploy.linode.tags** (array, required)
- Tags for organization (e.g., `["ai", "llm", "gpu"]`)

**deploy.linode.container** (object, required for Docker runtime)
- Container configuration
- Required fields: `image`, `internal_port`, `external_port`

**deploy.linode.container.image** (string, required)
- Docker image to run (e.g., `"vllm/vllm-openai:latest"`)

**deploy.linode.container.internal_port** (integer, required)
- Port the container listens on internally

**deploy.linode.container.external_port** (integer, required)
- Port to expose on the host (usually 80 or 443)

### Optional but Recommended Fields

**capabilities** (object, optional but recommended)
- Declarative requirements (runtime, features, packages)
- Preferred over custom scripts when possible

**deploy.linode.container.requires_gpu** (boolean, optional)
- Set to `true` for GPU workloads
- **Deprecated**: Use `capabilities.features: [gpu-nvidia]` instead

**deploy.linode.container.command** (string, optional)
- Override container CMD
- Supports variable expansion: `${VAR}`, `${VAR:-default}`

**deploy.linode.container.env** (object, optional)
- Default environment variables
- Supports variable expansion from user's .env file

**deploy.linode.container.health** (object, optional but highly recommended)
- Health check configuration
- Helps CLI determine when service is ready

**deploy.linode.container.health.type** (string)
- Health check type: `http`, `tcp`, or `exec`

**deploy.linode.container.health.path** (string, for http)
- HTTP path to check (e.g., `"/health"`)

**deploy.linode.container.health.port** (integer)
- Port to check (usually same as internal_port)

**deploy.linode.container.health.success_codes** (array)
- HTTP status codes considered successful (e.g., `[200]`)

**deploy.linode.container.health.initial_delay_seconds** (integer)
- Delay before first check (allow time for startup)

**deploy.linode.container.health.timeout_seconds** (integer)
- Timeout for each check (default: 10)

**deploy.linode.container.health.max_retries** (integer)
- Maximum retry attempts (e.g., 30 for 5 minutes at 10s intervals)

**deploy.linode.container.post_start_script** (string, optional)
- Script to run after container starts
- Useful for initialization tasks

**env** (object, optional)
- Environment variable requirements

**env.required** (array, optional)
- Required environment variables
- Format: `[{name: "VAR_NAME", description: "What this does"}]`

**env.optional** (array, optional)
- Optional environment variables with defaults or fallbacks
- Include usage examples in multi-line descriptions

**guidance** (object, optional but highly recommended)
- Usage instructions shown after deployment

**guidance.summary** (string, optional)
- Multi-line explanation of how to use the service

**guidance.examples** (array, optional)
- Usage examples with commands
- Format: `[{description: "What to do", command: "curl ..."}]`
- Use `{host}` placeholder for hostname
"""
    
    def _render_best_practices(self) -> str:
        return """## Best Practices

### GPU Templates

1. **Use capabilities**: Add `gpu-nvidia` to features instead of `requires_gpu: true`
   ```yaml
   capabilities:
     runtime: docker
     features:
       - gpu-nvidia
   ```

2. **Use Ubuntu 22.04**: GPU instances should use `linode/ubuntu22.04` for proven stability
   ```yaml
   deploy:
     linode:
       image: linode/ubuntu22.04
   ```

3. **Generous health check timeouts**: Model loading takes time
   ```yaml
   health:
     initial_delay_seconds: 180  # 3 minutes minimum
     max_retries: 60             # 10 minutes total (60 * 10s)
   ```

### Environment Variables

1. **Clear descriptions**: Use multi-line format with examples
   ```yaml
   env:
     optional:
       - name: MODEL_NAME
         description: |
           HuggingFace model to load. Popular options:
           - microsoft/Phi-3-mini-4k-instruct (context: 4k)
           - mistralai/Mistral-7B-Instruct-v0.3 (context: 32k)
           Default: meta-llama/Meta-Llama-3-8B-Instruct
   ```

2. **Don't hardcode model-specific values**: Let tools auto-detect when possible
   ```yaml
   # Bad: Hardcoded context length
   command: --model ${MODEL_NAME} --max-model-len 8192
   
   # Good: Auto-detect from model
   command: --model ${MODEL_NAME} ${MAX_MODEL_LEN:+--max-model-len ${MAX_MODEL_LEN}}
   ```

3. **Use variable expansion**: Support defaults and overrides
   ```yaml
   command: --model ${MODEL_NAME:-meta-llama/Meta-Llama-3-8B-Instruct}
   ```

### Health Checks

1. **Always include health checks**: Even for development templates
2. **Match service reality**: Use `/health` if available, `/` for simple services
3. **Account for initialization**: Set `initial_delay_seconds` appropriately
   - Simple services: 10-30 seconds
   - Model loading: 60-180 seconds
   - Large models: 180-300 seconds

### Documentation

1. **Guidance section**: Include practical examples users can copy-paste
2. **Use {host} placeholder**: Makes examples easy to adapt
3. **Show common operations**: Health check, basic API calls, advanced usage
4. **List popular options**: Models, configurations, alternatives

### Instance Sizing

1. **Sensible defaults**: Choose instance types that work for most users
   - Small models (< 7B params): `g6-standard-4`
   - Medium models (7-13B): `g6-standard-8`
   - Large models (13-30B): `g6-dedicated-16`

2. **Document requirements**: Explain why certain sizes are needed

3. **GPU vs CPU**: Use GPU types (`g6-*`) for AI workloads, standard types for utilities
"""
    
    def _render_requirements(self, user_input: Dict[str, Any]) -> str:
        gpu_check = "✓" if user_input.get('requires_gpu') else " "
        docker_check = "✓" if user_input.get('container_image') != 'native' else " "
        
        return f"""## Requirements for This Template

Based on user requirements:

- [{docker_check}] Runtime: Docker (containerized service)
- [{gpu_check}] GPU: NVIDIA GPU support required
- [ ] Dependencies: {user_input.get('dependencies', 'None specified')}
- [ ] Health check: HTTP endpoint at {user_input.get('health_check_path', '/health')}
- [ ] Environment variables: Define required and optional vars
- [ ] Startup time: Allow {user_input.get('startup_time', '60')} seconds in health check

### Key Decisions to Make

1. **Container Image**: 
   - User specified: `{user_input.get('container_image', 'Not specified')}`
   - If "custom", note that a Dockerfile will be needed

2. **Instance Type**:
   - For GPU workload: Recommend `g6-standard-8` or higher
   - For CPU workload: Recommend `g6-standard-2` or `g6-standard-4`

3. **Health Check**:
   - Type: Usually `http` for web services
   - Path: `{user_input.get('health_check_path', '/health')}`
   - Initial delay: {user_input.get('startup_time', '60')} seconds (user estimate)
   - Add buffer: Recommend initial_delay_seconds = user_estimate * 1.5

4. **Environment Variables**:
   - What does the service need to run?
   - What can users customize?
   - What credentials or tokens are required?

5. **Port Configuration**:
   - What port does the container listen on internally?
   - External port should typically be 80 for HTTP or 443 for HTTPS
"""
    
    def _render_validation_checklist(self) -> str:
        return """## Validation Checklist

After generating the template, verify:

- [ ] All required fields are present (name, display_name, version, description, deploy)
- [ ] Health check is configured with appropriate timeouts
- [ ] All environment variables are documented with clear descriptions
- [ ] Guidance section includes usage examples
- [ ] Uses capabilities system (gpu-nvidia, docker, etc.) instead of legacy flags
- [ ] Instance type matches the workload (GPU for AI, appropriate size for model)
- [ ] Base image is correct (ubuntu22.04 for GPU, ubuntu24.04 for CPU)
- [ ] Tags are relevant and descriptive
- [ ] Command supports variable expansion for flexibility
- [ ] startup time estimates account for model loading, dependency installation, etc.

### Testing Your Template

After generation, the user should:

1. Run validation: `linode-cli ai templates validate <name>`
2. Test deployment: `linode-cli ai templates test <name> --dry-run`
3. Deploy for real: `linode-cli ai init <name> && cd <name> && linode-cli ai deploy --wait`
"""
    
    def _render_stub_content(self, stub_path: str) -> str:
        """Render the stub content section."""
        try:
            with open(stub_path, 'r') as f:
                stub_content = f.read()
        except Exception:
            stub_content = "# Error reading stub file"
        
        return f"""## Template Stub

The following stub has been created in `{stub_path}`. Complete it according to the requirements above:

```yaml
{stub_content.strip()}
```

## Your Task Summary

1. **Read and understand** the user requirements and template system docs above
2. **Study the example templates** to see patterns and best practices
3. **Complete the stub** with all required fields and appropriate values
4. **Validate** your work against the checklist
5. **Test** with validation command before deployment

Remember:
- Use capabilities for GPU, Docker, packages (not legacy flags)
- Include comprehensive env var docs with examples
- Set realistic health check timeouts
- Provide helpful guidance with copy-paste examples
- Follow patterns from existing templates

Good luck! Generate a production-ready template that users will love.
"""


def generate_template_stub(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a basic template stub from user input.
    
    Args:
        user_input: Dictionary with user's answers
        
    Returns:
        Template stub as a dictionary
    """
    template_name = user_input.get('template_name', 'my-template')
    requires_gpu = user_input.get('requires_gpu', False)
    container_image = user_input.get('container_image', '')
    
    # Determine instance type based on GPU requirement
    if requires_gpu:
        instance_type = "g6-standard-8"
        base_image = "linode/ubuntu22.04"
        tags = ["ai", "gpu"]
    else:
        instance_type = "g6-standard-2"
        base_image = "linode/ubuntu24.04"
        tags = ["ai"]
    
    # Build capabilities
    capabilities = {
        "runtime": "docker",
        "features": [],
    }
    
    if requires_gpu:
        capabilities["features"].append("gpu-nvidia")
    
    # Parse dependencies for additional features
    dependencies = user_input.get('dependencies', '').lower()
    if 'redis' in dependencies:
        capabilities["features"].append("redis")
    if 'postgres' in dependencies:
        capabilities["features"].append("postgresql-14")
    if 'node' in dependencies:
        capabilities["features"].append("nodejs-18")
    if 'python' in dependencies:
        capabilities["features"].append("python-3.11")
    
    # Build health check
    startup_time = int(user_input.get('startup_time', 60))
    health_check = {
        "type": "http",
        "path": user_input.get('health_check_path', '/health'),
        "port": 8000,  # Default, to be adjusted
        "success_codes": [200],
        "initial_delay_seconds": max(60, int(startup_time * 1.5)),
        "timeout_seconds": 10,
        "max_retries": 30,
    }
    
    stub = {
        "name": template_name,
        "display_name": template_name.replace('-', ' ').title(),
        "version": "0.1.0",
        "description": f"{user_input.get('service_description', 'TODO: Add description')}\n",
        "capabilities": capabilities,
        "deploy": {
            "target": "linode",
            "linode": {
                "image": base_image,
                "region_default": "us-mia",
                "type_default": instance_type,
                "tags": tags,
                "container": {
                    "image": container_image or "TODO: Specify Docker image",
                    "internal_port": 8000,
                    "external_port": 80,
                    "command": "TODO: Optional command override",
                    "env": {},
                    "health": health_check,
                },
            },
        },
        "env": {
            "required": [],
            "optional": [],
        },
        "guidance": {
            "summary": "TODO: Add usage instructions\n",
            "examples": [
                {
                    "description": "Health check",
                    "command": "curl http://{host}" + health_check["path"],
                },
                {
                    "description": "TODO: Add more examples",
                    "command": "curl http://{host}/",
                },
            ],
        },
    }
    
    return stub
