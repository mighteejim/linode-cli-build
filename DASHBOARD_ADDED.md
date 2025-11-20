# Dashboard Screen Added! 🎉

## What Changed

Added a default dashboard view so you can run `linode-cli build tui` without any subcommand!

## New Dashboard Features

### 📊 Deployments Dashboard (`screens/dashboard.py`)

A central view that shows all your deployments at a glance:

**Features:**
- **Auto-Discovery**: Scans current directory and subdirectories for deployments
- **Deployment Table**: Shows app name, environment, instance ID, status, and directory
- **Navigation**: Use arrow keys (↑↓) or vim keys (j/k) to navigate
- **Quick Access**: Press Enter on any deployment to view its live status
- **Refresh**: Press R to reload the deployment list
- **Help**: Press ? for keyboard shortcuts

**Layout:**
```
┌─ 🚀 Linode Build - Deployments Dashboard ─────────────────┐
│                                                             │
│  Application    Environment    Instance ID    Status  Dir  │
│  ──────────────────────────────────────────────────────    │
│  ml-pipeline    production     12345678       ●      ./ml  │
│  chat-agent     staging        87654321       ●      ./ch  │
│  llm-api        dev            11223344       ●      ./llm │
│                                                             │
│  ↑↓ Navigate  [Enter] View  [R] Refresh  [Q] Quit  [?]    │
│                                                             │
│  Found 3 deployment(s) | Current: /home/user/projects      │
└─────────────────────────────────────────────────────────────┘
```

### Updated Command Behavior

**Before:**
```bash
linode-cli build tui         # Showed help text
linode-cli build tui deploy  # Monitor deployment
linode-cli build tui status  # View status
```

**Now:**
```bash
linode-cli build tui         # 🆕 Launch dashboard (default)
linode-cli build tui deploy  # Monitor deployment
linode-cli build tui status  # View status
```

### Default Behavior

When you run `linode-cli build tui` without arguments:
1. Launches the dashboard screen
2. Scans current directory for `.linode/state.json` files
3. Checks subdirectories (one level deep) for deployments
4. Displays all found deployments in a table
5. Allows you to select and view any deployment

If no deployments are found, it shows a helpful message:
```
No deployments found

Run 'linode-cli build init <template>' to create one
```

## Implementation Details

### Files Modified

1. **`tui/screens/dashboard.py`** (NEW)
   - DashboardScreen class with DataTable widget
   - Auto-discovery of deployments
   - Navigation and selection logic
   - ~200 lines

2. **`tui/screens/__init__.py`** (UPDATED)
   - Added DashboardScreen export

3. **`tui/app.py`** (UPDATED)
   - Added "dashboard" mode support
   - Imports DashboardScreen
   - Routes to dashboard when mode="dashboard"

4. **`commands/tui.py`** (UPDATED)
   - Defaults to dashboard when no subcommand given
   - Updated help text
   - Passes "dashboard" mode to run_tui()

5. **`README.md`** (UPDATED)
   - Added dashboard to command reference table
   - Updated usage examples
   - Added dashboard features list
   - Added navigation keyboard shortcuts

## Usage Examples

### Launch Dashboard
```bash
# From any directory with deployments
linode-cli build tui
```

### Navigate Deployments
```bash
# Use arrow keys or j/k to move up/down
# Press Enter to view the selected deployment's status
# Press R to refresh the list
# Press Q or Esc to quit
```

### From Project Directory
```bash
cd my-projects
linode-cli build tui  # Shows all deployments in subdirectories
```

### Workflow
```bash
# 1. Create some deployments
mkdir projects && cd projects
linode-cli build init ml-pipeline --directory ml
linode-cli build init chat-agent --directory chat
linode-cli build init llm-api --directory api

# 2. Launch dashboard
linode-cli build tui

# 3. Select a deployment with arrow keys + Enter
# 4. View live status, SSH command, etc.
# 5. Press Esc to go back to dashboard
```

## Keyboard Shortcuts

### Dashboard View
- `↑↓` or `j/k` - Navigate deployments
- `Enter` - View selected deployment status
- `R` - Refresh deployment list
- `Q` / `Esc` - Quit
- `?` - Show help
- `Ctrl+C` - Quit

### From Status View
- `Esc` - Back to dashboard
- `R` - Refresh status
- `S` - Show SSH command
- `D` - Destroy deployment (with confirmation)

## Technical Details

### Deployment Discovery

The dashboard scans for deployments by looking for `.linode/state.json` files:

```
current-directory/
├── .linode/
│   └── state.json          ← Found!
├── project-1/
│   └── .linode/
│       └── state.json      ← Found!
└── project-2/
    └── .linode/
        └── state.json      ← Found!
```

### State File Structure

Each deployment's state file contains:
```json
{
  "instance_id": 12345678,
  "app_name": "ml-pipeline",
  "environment": "production",
  "created": "2024-11-19T17:00:00Z"
}
```

### Benefits

1. **Quick Overview**: See all deployments at once
2. **Easy Navigation**: Jump to any deployment quickly
3. **Context Aware**: Shows deployments relative to current directory
4. **No Arguments Needed**: Simple `linode-cli build tui` command
5. **Keyboard Driven**: Fast navigation without mouse

## Statistics

- **New Files**: 1 (dashboard.py, ~200 lines)
- **Modified Files**: 4
- **Total Lines Added**: ~250
- **New Features**: 1 (Dashboard screen)
- **Breaking Changes**: 0 (fully backward compatible)

## Success!

Now you can simply run:
```bash
linode-cli build tui
```

And get a beautiful dashboard showing all your deployments! 🎉

---

**Next Steps:**
- Deploy some applications
- Run `linode-cli build tui` to see them in the dashboard
- Press Enter on any deployment to view its live status
- Enjoy the TUI experience! 🚀
