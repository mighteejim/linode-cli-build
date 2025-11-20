# BuildWatch Capability Refactoring

## Overview

BuildWatch has been refactored from hardcoded cloud-init logic into a proper **Capability** in the CapabilitiesManager system. This makes it consistent with other infrastructure features (Docker, GPU, PostgreSQL, etc.) and more modular.

## Changes Made

### 1. **New BuildWatchCapability Class** (`linodecli_build/core/capabilities.py`)

Added a new capability class that encapsulates BuildWatch installation:

```python
class BuildWatchCapability(Capability):
    """Provides BuildWatch container monitoring service."""
    
    def __init__(self, deployment_id: str, app_name: str):
        self.deployment_id = deployment_id
        self.app_name = app_name
    
    def name(self) -> str:
        return "buildwatch"
    
    def get_fragments(self) -> CapabilityFragments:
        # Returns write_files and runcmd for BuildWatch installation
        ...
```

**What it provides:**
- Writes BuildWatch service script to `/usr/local/bin/build-watcher`
- Writes systemd unit file
- Writes logrotate configuration
- Creates necessary directories
- Enables and starts the service

### 2. **CapabilityManager Enhancement** (`linodecli_build/core/capabilities.py`)

Added a dedicated method to add BuildWatch:

```python
def add_buildwatch(self, deployment_id: str, app_name: str) -> None:
    """Add BuildWatch monitoring capability."""
    buildwatch_cap = BuildWatchCapability(deployment_id, app_name)
    self.capabilities.append(buildwatch_cap)
```

### 3. **CloudInitConfig Simplification** (`linodecli_build/core/cloud_init.py`)

**Before:**
```python
@dataclass
class CloudInitConfig:
    # ... other fields ...
    deployment_id: Optional[str] = None
    app_name: Optional[str] = None
```

**After:**
```python
@dataclass
class CloudInitConfig:
    # ... other fields ...
    # No BuildWatch-specific fields needed!
```

### 4. **Removed Hardcoded BuildWatch Logic** (`linodecli_build/core/cloud_init.py`)

**Before:** Cloud-init generator had hardcoded logic:
```python
# Add BuildWatch service files
if config.deployment_id and config.app_name:
    write_files.extend([...])  # Hardcoded BuildWatch files
    
# Start BuildWatch service
if config.deployment_id and config.app_name:
    runcmd.extend([...])  # Hardcoded BuildWatch commands
```

**After:** Completely removed - handled by capability system:
```python
# Get capability fragments from the capability manager
cap_fragments = config.capability_manager.assemble_fragments()

# Add capability write_files (includes BuildWatch if added)
write_files.extend(cap_fragments.write_files)

# Then run capability commands (includes BuildWatch setup if added)
runcmd.extend(cap_fragments.runcmd)
```

### 5. **Deploy Command Update** (`linodecli_build/commands/deploy.py`)

**Before:**
```python
config_obj = cloud_init.CloudInitConfig(
    # ...
    deployment_id=deployment_id,
    app_name=app_name,
)
```

**After:**
```python
# Generate deployment_id before creating cloud-init config
deployment_id = _generate_deployment_id()

# Create capability manager from template
capability_manager = capabilities.create_capability_manager(template.data)

# Add BuildWatch monitoring capability
capability_manager.add_buildwatch(deployment_id, app_name)

config_obj = cloud_init.CloudInitConfig(
    # ... no BuildWatch-specific params needed
    capability_manager=capability_manager,
)
```

## Architecture Benefits

### ✅ **Better Separation of Concerns**
- BuildWatch is now a self-contained capability
- Cloud-init generator doesn't need to know about BuildWatch specifics
- Each capability handles its own installation logic

### ✅ **Consistency**
- BuildWatch follows the same pattern as Docker, GPU, and other capabilities
- Uses standard `get_fragments()` interface
- Integrated into capability assembly process

### ✅ **Modularity**
- BuildWatch can be easily enabled/disabled
- Could potentially be made optional in the future
- Easier to test in isolation

### ✅ **Cleaner Code**
- Removed special-case logic from cloud_init.py
- CloudInitConfig dataclass is simpler
- deploy.py explicitly shows BuildWatch being added

### ✅ **Extensibility**
- Easy to add configuration options to BuildWatch capability
- Could add monitoring level (basic/verbose), custom ports, etc.
- Template authors could potentially control BuildWatch behavior

## How It Works

1. **Deploy starts** → Generates `deployment_id` and determines `app_name`
2. **Capability manager created** → From template's `capabilities:` section
3. **BuildWatch added** → `capability_manager.add_buildwatch(deployment_id, app_name)`
4. **Fragments assembled** → All capabilities return their cloud-init fragments
5. **Cloud-init generated** → BuildWatch installation included automatically
6. **Instance boots** → BuildWatch service starts monitoring containers

## Code Flow

```
deploy.py
  ↓
  Creates CapabilityManager
  ↓
  Adds BuildWatchCapability(deployment_id, app_name)
  ↓
  Passes to CloudInitConfig
  ↓
  generate_cloud_init() calls capability_manager.assemble_fragments()
  ↓
  BuildWatchCapability.get_fragments() returns:
    - write_files: [service script, systemd unit, logrotate config]
    - runcmd: [create dirs, enable service, start service]
  ↓
  Combined with other capability fragments
  ↓
  Final cloud-init YAML generated
```

## Future Possibilities

Now that BuildWatch is a capability, it could be enhanced with:

### **Optional Monitoring**
```python
# In deploy.py
if args.enable_monitoring:  # Optional flag
    capability_manager.add_buildwatch(deployment_id, app_name)
```

### **Configuration Options**
```python
class BuildWatchCapability:
    def __init__(self, deployment_id: str, app_name: str, 
                 port: int = 9090, log_level: str = "INFO"):
        # Configurable monitoring
```

### **Template Control**
```yaml
# In deploy.yml
capabilities:
  features:
    - buildwatch  # Template can request it
  buildwatch:
    enabled: true
    port: 9090
    log_level: DEBUG
```

## Testing

All files compile successfully:
```bash
✅ linodecli_build/core/capabilities.py
✅ linodecli_build/core/cloud_init.py
✅ linodecli_build/commands/deploy.py
```

## Summary

This refactoring:
- ✅ Makes BuildWatch a first-class capability
- ✅ Removes hardcoded logic from cloud_init.py
- ✅ Follows existing capability patterns
- ✅ Maintains all functionality
- ✅ Improves code organization
- ✅ Enables future enhancements

BuildWatch is now properly integrated into the capability system, making the codebase more maintainable and extensible! 🎯
