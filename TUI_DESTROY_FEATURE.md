# TUI Destroy Feature - Implementation

## Overview
Added ability to destroy deployments directly from the TUI with a confirmation modal. Users can press **D** on any deployment in the dashboard or status view to destroy it.

## Features

### 1. Confirmation Modal Widget
**New File:** `linodecli_build/tui/widgets/confirm_modal.py`

- Modal dialog with red border and error styling
- Shows deployment details before destruction
- Keyboard shortcuts: **Y** to confirm, **N** or **ESC** to cancel
- Blocks interaction with underlying screens until dismissed

### 2. Dashboard Integration
**Modified:** `linodecli_build/tui/screens/dashboard.py`

- Added **[D]** key binding for "Destroy Selected"
- Shows confirmation modal with deployment details
- Calls Linode API to delete instance
- Refreshes deployment list after successful deletion
- Shows success/error notifications

### 3. Status View Integration
**Modified:** `linodecli_build/tui/screens/status_view.py`

- Added **[D]** key binding on status view
- Finds deployment by instance_id
- Shows same confirmation modal
- Stops monitoring before deletion
- Returns to dashboard after successful deletion

## Usage

### From Dashboard
1. Navigate to a deployment using arrow keys
2. Press **D** to destroy
3. Review deployment details in modal
4. Press **Y** to confirm or **N**/**ESC** to cancel
5. Dashboard refreshes automatically

### From Status View
1. While viewing a deployment's status, press **D**
2. Review deployment details in modal
3. Press **Y** to confirm or **N**/**ESC** to cancel
4. Returns to dashboard after deletion

## User Interface

### Confirmation Modal
```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║              ⚠ Destroy Deployment                    ║
║                                                       ║
║  This will permanently delete the Linode instance    ║
║  and all its data.                                   ║
║  This action CANNOT be undone.                       ║
║                                                       ║
║  ┌─────────────────────────────────────────────┐    ║
║  │  Deployment ID: k7m3p9x2                    │    ║
║  │  Application: chat-agent                    │    ║
║  │  Environment: production                    │    ║
║  │  Instance: 12345678                         │    ║
║  │  Region: us-ord                             │    ║
║  └─────────────────────────────────────────────┘    ║
║                                                       ║
║   ┌──────────────┐        ┌──────────────┐          ║
║   │ Cancel [N]   │        │ Confirm [Y]  │          ║
║   └──────────────┘        └──────────────┘          ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
```

## Keyboard Shortcuts

### Dashboard View
- **D** - Destroy selected deployment
- **Y** (in modal) - Confirm destruction
- **N** (in modal) - Cancel destruction
- **ESC** (in modal) - Cancel destruction

### Status View
- **D** - Destroy current deployment
- **Y** (in modal) - Confirm destruction
- **N** (in modal) - Cancel destruction
- **ESC** (in modal) - Cancel destruction

## Implementation Details

### API Integration
Uses the existing Linode API client:
```python
status, response = self.api_client.client.call_operation(
    'linodes', 'delete', [str(instance_id)]
)
```

### Registry Cleanup
Also removes deployment from the legacy registry:
```python
from ...core import registry
registry.remove_deployment(deployment_id)
```

### Error Handling
- Shows error notifications if API call fails
- Validates deployment exists before deletion
- Handles missing deployment data gracefully

### User Feedback
- "Destroying {app_name}..." notification during deletion
- "✓ Destroyed {app_name} ({deployment_id})" on success
- "Destroy cancelled" if user cancels
- Error messages with details if deletion fails

## Safety Features

1. **Confirmation Required** - Always shows modal before deletion
2. **Clear Warning** - Modal explicitly states data loss is permanent
3. **Detailed Information** - Shows exactly what will be deleted
4. **Easy Cancellation** - Multiple ways to cancel (N, ESC, Cancel button)
5. **Visual Indicators** - Red error styling makes danger clear

## Files Modified

- ✅ `linodecli_build/tui/widgets/confirm_modal.py` (NEW)
- ✅ `linodecli_build/tui/widgets/__init__.py` (Updated exports)
- ✅ `linodecli_build/tui/screens/dashboard.py` (Added destroy action)
- ✅ `linodecli_build/tui/screens/status_view.py` (Added destroy action)

## Testing

Test the destroy functionality:

```bash
# Start TUI
linode-cli build tui

# From Dashboard:
# 1. Select a deployment
# 2. Press 'D'
# 3. Press 'Y' to confirm
# 4. Verify deployment is deleted
# 5. Verify dashboard refreshes

# From Status View:
# 1. Select a deployment and press Enter
# 2. Press 'D'
# 3. Press 'Y' to confirm
# 4. Verify returns to dashboard
# 5. Verify deployment is deleted
```

## Benefits

✅ **Fast** - Destroy deployments without leaving TUI
✅ **Safe** - Requires explicit confirmation
✅ **Consistent** - Same experience in dashboard and status views
✅ **Informative** - Shows exactly what will be deleted
✅ **Integrated** - Uses existing destroy command logic
✅ **User-friendly** - Clear keyboard shortcuts and visual feedback

## Future Enhancements

Possible improvements:
- Bulk destroy (select multiple deployments)
- Soft delete with confirmation period
- Export deployment config before deletion
- Destroy history/undo capability
