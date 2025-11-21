"""Interactive initialization wizard for creating and deploying projects."""

import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.widgets import Header, Footer, Static, DataTable, Input, Button, Checkbox, Label
from textual.binding import Binding
from rich.text import Text

from ..api import LinodeAPIClient
from ...core import templates as template_core
from ...core import init_operations
from ...core import deploy_operations


class InitWizardCoordinator:
    """Manages state across wizard steps."""
    
    def __init__(self, api_client: LinodeAPIClient, config):
        self.api_client = api_client
        self.config = config
        self.state = {
            'template': None,
            'region': None,
            'instance_type': None,
            'app_name': None,
            'environment': 'default',
            'directory': None,
            'capabilities': []
        }
    
    def set(self, key: str, value):
        """Set a state value."""
        self.state[key] = value
    
    def get(self, key: str, default=None):
        """Get a state value."""
        return self.state.get(key, default)


class TemplateSelectionScreen(ModalScreen):
    """Select from available templates."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select"),
        Binding("q", "cancel", "Quit"),
    ]
    
    CSS = """
    TemplateSelectionScreen {
        align: center middle;
    }
    
    #modal-container {
        width: 65%;
        height: 55%;
        background: $surface;
        border: thick $primary;
    }
    
    #header-info {
        height: 1;
        background: $primary;
        padding: 0 1;
        dock: top;
    }
    
    #content-container {
        height: 1fr;
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
    }
    
    #help-text {
        height: 2;
        padding: 0 1;
        background: $panel;
        dock: bottom;
    }
    """
    
    def __init__(self, coordinator: InitWizardCoordinator, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator
        self.templates = []
    
    def compose(self):
        with Container(id="modal-container"):
            yield Static(
                "Step 1/5: Select Template",
                id="header-info"
            )
            
            with Container(id="content-container"):
                yield DataTable()
            
            yield Static(
                "↑↓ Navigate  [Enter] Select Template  [Esc] Cancel",
                id="help-text"
            )
    
    def on_mount(self):
        """Load templates when screen mounts."""
        self.notify("Template screen mounted", timeout=2)
        self.load_templates()
        table = self.query_one(DataTable)
        table.focus()
        self.notify(f"Table focused, {len(self.templates)} templates loaded", timeout=2)
    
    def load_templates(self):
        """Load all available templates."""
        records = template_core.list_template_records()
        
        table = self.query_one(DataTable)
        table.clear(columns=True)
        
        table.add_column("Template", width=25)
        table.add_column("Description", width=55)
        table.add_column("Source", width=10)
        
        self.templates = []
        for record in records:
            try:
                template = template_core.load_template(record.name)
                self.templates.append(template)
                table.add_row(
                    template.display_name,
                    template.description[:60] if template.description else "",
                    record.source
                )
            except Exception as e:
                # Skip templates that fail to load
                continue
        
        if not self.templates:
            table.add_row("No templates found", "", "")
    
    def action_select(self):
        """Select the current template and move to next step."""
        self.notify("action_select called!", timeout=3)
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row
        
        self.notify(f"Cursor row: {cursor_row}, Templates: {len(self.templates)}", timeout=3)
        
        if cursor_row is None or cursor_row >= len(self.templates):
            self.notify("Please select a template", severity="warning")
            return
        
        selected_template = self.templates[cursor_row]
        self.coordinator.set('template', selected_template)
        
        # Set default app name
        self.coordinator.set('app_name', selected_template.name)
        
        self.notify(f"Selected: {selected_template.display_name}", timeout=2)
        
        # Move to region selection
        self.app.push_screen(RegionSelectionScreen(self.coordinator))
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Handle row selection via Enter key or click."""
        self.notify("on_data_table_row_selected fired!", timeout=3)
        self.action_select()
    
    def on_key(self, event):
        """Handle key presses - explicitly handle Enter."""
        self.notify(f"Key pressed: {event.key}", timeout=1)
        if event.key == "enter":
            self.notify("Enter detected, calling action_select", timeout=2)
            self.action_select()
            event.prevent_default()
            event.stop()
    
    def action_cancel(self):
        """Cancel wizard and return to dashboard."""
        self.dismiss()


class RegionSelectionScreen(ModalScreen):
    """Select Linode region."""
    
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("enter", "select", "Select"),
        Binding("b", "back", "Back"),
    ]
    
    CSS = """
    RegionSelectionScreen {
        align: center middle;
    }
    
    #modal-container {
        width: 65%;
        height: 55%;
        background: $surface;
        border: thick $primary;
    }
    
    #header-info {
        height: 1;
        background: $primary;
        padding: 0 1;
        dock: top;
    }
    
    #content-container {
        height: 1fr;
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
    }
    
    #help-text {
        height: 2;
        padding: 0 1;
        background: $panel;
        dock: bottom;
    }
    """
    
    def __init__(self, coordinator: InitWizardCoordinator, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator
        self.regions = []
        self.region_list = []  # Flattened list for row index mapping
    
    def compose(self):
        template = self.coordinator.get('template')
        template_name = template.display_name if template else "Unknown"
        
        with Container(id="modal-container"):
            yield Static(
                f"Step 2/5: Select Region | Template: {template_name}",
                id="header-info"
            )
            
            with Container(id="content-container"):
                yield DataTable()
            
            yield Static(
                "↑↓ Navigate  [Enter] Select Region  [B] Back  [Esc] Cancel",
                id="help-text"
            )
    
    def on_mount(self):
        """Load regions when screen mounts."""
        self.notify("Region screen mounted", timeout=2)
        self.load_regions()
        table = self.query_one(DataTable)
        table.focus()
        self.notify(f"Table focused, {len(self.region_list)} regions loaded", timeout=2)
    
    def load_regions(self):
        """Load regions from API grouped by geography."""
        try:
            status, response = self.coordinator.api_client.client.call_operation('regions', 'list')
            self.regions = response.get('data', []) if status == 200 else []
        except Exception as e:
            self.notify(f"Error loading regions: {e}", severity="error", timeout=5)
            self.regions = []
        
        # Geographic groupings
        geo_groups = {
            'Americas': ['us', 'ca'],
            'South America': ['br', 'cl', 'ar'],
            'Europe': ['gb', 'uk', 'de', 'fr', 'nl', 'se', 'it', 'es', 'pl'],
            'Asia': ['jp', 'sg', 'in', 'id', 'kr', 'ae'],
            'Oceania': ['au', 'nz']
        }
        
        # Group regions
        grouped = {geo: [] for geo in geo_groups}
        other = []
        
        for region in self.regions:
            region_id = region.get('id', '')
            country_code = region_id.split('-')[0] if '-' in region_id else ''
            
            placed = False
            for geo, codes in geo_groups.items():
                if country_code in codes:
                    grouped[geo].append(region)
                    placed = True
                    break
            
            if not placed:
                other.append(region)
        
        # Get template default
        template = self.coordinator.get('template')
        default_region = template.data.get('deploy', {}).get('linode', {}).get('region_default', 'us-east')
        
        # Build table
        table = self.query_one(DataTable)
        table.clear(columns=True)
        
        table.add_column("Region ID", width=16)
        table.add_column("Location", width=25)
        table.add_column("", width=10)
        
        self.region_list = []
        
        # Display each geographic group
        for geo in ['Americas', 'Europe', 'Asia', 'South America', 'Oceania']:
            group_regions = sorted(grouped[geo], key=lambda r: r.get('id', ''))
            if not group_regions:
                continue
            
            # Add header row
            table.add_row(
                Text(f"─── {geo} ───", style="bold cyan"),
                "", ""
            )
            
            for region in group_regions:
                region_id = region.get('id', 'unknown')
                label = region.get('label', region_id)
                default_marker = "(default)" if region_id == default_region else ""
                
                self.region_list.append(region)
                table.add_row(region_id, label, default_marker)
        
        # Add other regions if any
        if other:
            table.add_row(Text("─── Other ───", style="bold cyan"), "", "")
            for region in sorted(other, key=lambda r: r.get('id', '')):
                region_id = region.get('id', 'unknown')
                label = region.get('label', region_id)
                default_marker = "(default)" if region_id == default_region else ""
                
                self.region_list.append(region)
                table.add_row(region_id, label, default_marker)
    
    def on_key(self, event):
        """Handle key presses - explicitly handle Enter."""
        self.notify(f"Region key: {event.key}", timeout=1)
        if event.key == "enter":
            self.notify("Region: Enter detected, calling action_select", timeout=2)
            self.action_select()
            event.prevent_default()
            event.stop()
    
    def action_select(self):
        """Select region and move to next step."""
        self.notify("Region action_select called!", timeout=3)
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row
        
        if cursor_row is None:
            self.notify("Please select a region", severity="warning")
            return
        
        # Get the actual data row (accounting for header rows)
        try:
            # Get cell value from first column
            cell_value = table.get_cell_at((cursor_row, 0))
            if isinstance(cell_value, Text):
                # Skip header rows (they use Text styling)
                if "───" in str(cell_value):
                    self.notify("Please select a region, not a header", severity="warning")
                    return
            
            # Find corresponding region
            region_id = str(table.get_cell_at((cursor_row, 0)))
            selected_region = next((r for r in self.region_list if r.get('id') == region_id), None)
            
            if selected_region:
                self.coordinator.set('region', selected_region.get('id'))
                self.notify(f"Selected region: {selected_region.get('id')}", timeout=1)
                self.app.push_screen(PlanSelectionScreen(self.coordinator))
            else:
                self.notify("Invalid selection", severity="warning")
        except Exception as e:
            self.notify(f"Error selecting region: {e}", severity="error")
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Handle row selection via Enter key or click."""
        self.action_select()
    
    def action_back(self):
        """Go back to template selection."""
        self.dismiss()


class PlanSelectionScreen(ModalScreen):
    """Select Linode plan/instance type."""
    
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("enter", "select", "Select"),
        Binding("b", "back", "Back"),
    ]
    
    CSS = """
    PlanSelectionScreen {
        align: center middle;
    }
    
    #modal-container {
        width: 65%;
        height: 55%;
        background: $surface;
        border: thick $primary;
    }
    
    #header-info {
        height: 1;
        background: $primary;
        padding: 0 1;
        dock: top;
    }
    
    #content-container {
        height: 1fr;
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
    }
    
    #help-text {
        height: 2;
        padding: 0 1;
        background: $panel;
        dock: bottom;
    }
    """
    
    def __init__(self, coordinator: InitWizardCoordinator, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator
        self.types = []
        self.type_list = []
    
    def compose(self):
        template = self.coordinator.get('template')
        region = self.coordinator.get('region')
        template_name = template.display_name if template else "Unknown"
        
        with Container(id="modal-container"):
            yield Static(
                f"Step 3/5: Select Plan | Template: {template_name} | Region: {region}",
                id="header-info"
            )
            
            with Container(id="content-container"):
                yield DataTable()
            
            yield Static(
                "↑↓ Navigate  [Enter] Select Plan  [B] Back  [Esc] Cancel",
                id="help-text"
            )
    
    def on_mount(self):
        """Load instance types when screen mounts."""
        self.load_types()
        table = self.query_one(DataTable)
        table.focus()
    
    def load_types(self):
        """Load instance types from API grouped by category."""
        try:
            status, response = self.coordinator.api_client.client.call_operation('linodes', 'types')
            self.types = response.get('data', []) if status == 200 else []
        except Exception as e:
            self.notify(f"Error loading instance types: {e}", severity="error", timeout=5)
            self.types = []
        
        # Categorize types
        categorized = {
            'Shared CPU': [],
            'Dedicated CPU': [],
            'High Memory': [],
            'Premium': [],
            'GPU': []
        }
        
        for t in self.types:
            type_id = t.get('id', '')
            type_class = t.get('class', '')
            
            if type_class == 'gpu':
                categorized['GPU'].append(t)
            elif type_class == 'premium' or type_id.startswith('g7-premium'):
                categorized['Premium'].append(t)
            elif 'highmem' in type_id:
                categorized['High Memory'].append(t)
            elif 'dedicated' in type_id or type_class == 'dedicated':
                categorized['Dedicated CPU'].append(t)
            elif type_class == 'standard':
                categorized['Shared CPU'].append(t)
        
        # Sort each category by price
        for category in categorized:
            categorized[category].sort(key=lambda t: t.get('price', {}).get('hourly', 0))
        
        # Get template default
        template = self.coordinator.get('template')
        default_type = template.data.get('deploy', {}).get('linode', {}).get('type_default', 'g6-nanode-1')
        
        # Build table
        table = self.query_one(DataTable)
        table.clear(columns=True)
        
        table.add_column("Type ID", width=22)
        table.add_column("RAM", width=10)
        table.add_column("vCPUs", width=8)
        table.add_column("Price/hr", width=10)
        table.add_column("", width=10)
        
        self.type_list = []
        
        # Display categories
        for category in ['Shared CPU', 'Dedicated CPU', 'High Memory', 'Premium', 'GPU']:
            category_types = categorized[category]
            if not category_types:
                continue
            
            # Add header row
            table.add_row(
                Text(f"─── {category} ───", style="bold cyan"),
                "", "", "", ""
            )
            
            # Limit display for large categories
            display_limit = 10 if category == 'Shared CPU' else len(category_types)
            
            for t in category_types[:display_limit]:
                type_id = t.get('id', 'unknown')
                memory = t.get('memory', 0)
                vcpus = t.get('vcpus', 0)
                price = t.get('price', {}).get('hourly', 0)
                default_marker = "(default)" if type_id == default_type else ""
                
                self.type_list.append(t)
                table.add_row(
                    type_id,
                    f"{memory}MB",
                    str(vcpus),
                    f"${price:.2f}",
                    default_marker
                )
            
            if len(category_types) > display_limit:
                table.add_row(f"... {len(category_types) - display_limit} more", "", "", "", "")
    
    def on_key(self, event):
        """Handle key presses - explicitly handle Enter."""
        if event.key == "enter":
            self.action_select()
            event.prevent_default()
            event.stop()
    
    def action_select(self):
        """Select instance type and move to next step."""
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row
        
        if cursor_row is None:
            self.notify("Please select an instance type", severity="warning")
            return
        
        try:
            # Get cell value from first column
            cell_value = table.get_cell_at((cursor_row, 0))
            if isinstance(cell_value, Text):
                if "───" in str(cell_value):
                    self.notify("Please select an instance type, not a header", severity="warning")
                    return
            
            # Find corresponding type
            type_id = str(table.get_cell_at((cursor_row, 0)))
            selected_type = next((t for t in self.type_list if t.get('id') == type_id), None)
            
            if selected_type:
                self.coordinator.set('instance_type', selected_type.get('id'))
                self.notify(f"Selected plan: {selected_type.get('id')}", timeout=1)
                self.app.push_screen(ConfigurationScreen(self.coordinator))
            else:
                self.notify("Invalid selection", severity="warning")
        except Exception as e:
            self.notify(f"Error selecting plan: {e}", severity="error")
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Handle row selection via Enter key or click."""
        self.action_select()
    
    def action_back(self):
        """Go back to region selection."""
        self.dismiss()


class ConfigurationScreen(ModalScreen):
    """Configure app name, environment, directory, and capabilities."""
    
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+s", "submit", "Continue"),
        Binding("b", "back", "Back"),
    ]
    
    CSS = """
    ConfigurationScreen {
        align: center middle;
    }
    
    #modal-container {
        width: 60%;
        height: 50%;
        background: $surface;
        border: thick $primary;
    }
    
    #header-info {
        height: 1;
        background: $primary;
        padding: 0 1;
        dock: top;
    }
    
    #content-container {
        height: 1fr;
        padding: 1;
    }
    
    #form-container {
        height: auto;
        padding: 1;
        background: $panel;
        border: solid $primary;
    }
    
    .form-row {
        height: auto;
        padding: 0 0 1 0;
    }
    
    Label {
        width: 20;
        padding: 0 1 0 0;
    }
    
    Input {
        width: 60;
    }
    
    #capabilities-section {
        height: auto;
        padding: 1 0 0 0;
    }
    
    #button-container {
        height: auto;
        padding: 1 0 0 0;
        align: center middle;
    }
    
    Button {
        margin: 0 1;
    }
    
    #help-text {
        height: 2;
        padding: 0 1;
        background: $panel;
        dock: bottom;
    }
    """
    
    def __init__(self, coordinator: InitWizardCoordinator, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator
    
    def compose(self):
        template = self.coordinator.get('template')
        template_name = template.display_name if template else "Unknown"
        
        with Container(id="modal-container"):
            yield Static(
                f"Step 4/5: Configuration | Template: {template_name}",
                id="header-info"
            )
            
            with Container(id="content-container"):
                with Container(id="form-container"):
                    with Horizontal(classes="form-row"):
                        yield Label("App Name:")
                        yield Input(
                            value=self.coordinator.get('app_name', ''),
                            placeholder="my-app",
                            id="app_name_input"
                        )
                    
                    with Horizontal(classes="form-row"):
                        yield Label("Environment:")
                        yield Input(
                            value=self.coordinator.get('environment', 'default'),
                            placeholder="default",
                            id="environment_input"
                        )
                    
                    with Horizontal(classes="form-row"):
                        yield Label("Directory:")
                        yield Input(
                            value=self.coordinator.get('directory', '') or f"./{self.coordinator.get('app_name', 'my-app')}",
                            placeholder="./my-app",
                            id="directory_input"
                        )
                    
                    # Capabilities section (if template has capabilities)
                    template_obj = self.coordinator.get('template')
                    if template_obj and hasattr(template_obj, 'data'):
                        capabilities_data = template_obj.data.get('capabilities', [])
                        
                        # Only show if capabilities is a list of capability configs
                        if isinstance(capabilities_data, list) and capabilities_data:
                            with Vertical(id="capabilities-section"):
                                yield Static("Capabilities:", classes="form-label")
                                for cap in capabilities_data:
                                    if isinstance(cap, dict):
                                        cap_id = cap.get('id', '')
                                        cap_name = cap.get('name', cap_id)
                                        cap_desc = cap.get('description', '')
                                        yield Checkbox(
                                            f"{cap_name} - {cap_desc}",
                                            value=False,
                                            id=f"cap_{cap_id}"
                                        )
                
                with Horizontal(id="button-container"):
                    yield Button("Back", variant="default", id="back_button")
                    yield Button("Continue", variant="primary", id="continue_button")
            
            yield Static(
                "[Ctrl+S] Continue  [B] Back  [Esc] Cancel",
                id="help-text"
            )
    
    def on_mount(self):
        """Focus first input when screen mounts."""
        app_name_input = self.query_one("#app_name_input", Input)
        app_name_input.focus()
    
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button clicks."""
        if event.button.id == "continue_button":
            self.action_submit()
        elif event.button.id == "back_button":
            self.action_back()
    
    def action_submit(self):
        """Validate inputs and move to confirmation."""
        # Get input values
        app_name = self.query_one("#app_name_input", Input).value.strip()
        environment = self.query_one("#environment_input", Input).value.strip()
        directory = self.query_one("#directory_input", Input).value.strip()
        
        # Validate
        if not app_name:
            self.notify("App name is required", severity="error")
            return
        
        if not environment:
            environment = "default"
        
        if not directory:
            directory = f"./{app_name}"
        
        # Store values
        self.coordinator.set('app_name', app_name)
        self.coordinator.set('environment', environment)
        self.coordinator.set('directory', directory)
        
        # Get selected capabilities (only if they exist as a list)
        template_obj = self.coordinator.get('template')
        capabilities_data = []
        if template_obj and hasattr(template_obj, 'data'):
            capabilities_data = template_obj.data.get('capabilities', [])
            if not isinstance(capabilities_data, list):
                capabilities_data = []
        
        selected_caps = []
        
        for cap in capabilities_data:
            if isinstance(cap, dict):
                cap_id = cap.get('id', '')
                try:
                    checkbox = self.query_one(f"#cap_{cap_id}", Checkbox)
                    if checkbox.value:
                        selected_caps.append(cap_id)
                except:
                    pass  # Checkbox might not exist
        
        self.coordinator.set('capabilities', selected_caps)
        
        # Move to confirmation
        self.app.push_screen(ConfirmationScreen(self.coordinator))
    
    def action_back(self):
        """Go back to plan selection."""
        self.dismiss()


class ConfirmationScreen(ModalScreen):
    """Review selections and execute init + deploy."""
    
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+d", "deploy", "Deploy"),
        Binding("b", "back", "Back"),
    ]
    
    CSS = """
    ConfirmationScreen {
        align: center middle;
    }
    
    #modal-container {
        width: 60%;
        height: 50%;
        background: $surface;
        border: thick $primary;
    }
    
    #header-info {
        height: 1;
        background: $primary;
        padding: 0 1;
        dock: top;
    }
    
    #content-container {
        height: 1fr;
        padding: 1;
    }
    
    #summary-container {
        height: auto;
        padding: 1;
        background: $panel;
        border: solid $primary;
    }
    
    .summary-row {
        height: auto;
        padding: 0;
    }
    
    #button-container {
        height: auto;
        padding: 1 0 0 0;
        align: center middle;
    }
    
    Button {
        margin: 0 1;
    }
    
    #help-text {
        height: 2;
        padding: 0 1;
        background: $panel;
        dock: bottom;
    }
    
    #status-text {
        height: auto;
        padding: 1;
        background: $panel;
    }
    """
    
    def __init__(self, coordinator: InitWizardCoordinator, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator
        self.is_deploying = False
        self.status_messages = []  # Track status messages
    
    def compose(self):
        with Container(id="modal-container"):
            yield Static(
                "Step 5/5: Confirmation & Deploy",
                id="header-info"
            )
            
            with Container(id="content-container"):
                with Vertical(id="summary-container"):
                    yield Static("Review your deployment configuration:", classes="summary-row")
                    yield Static("", classes="summary-row")
                    
                    template = self.coordinator.get('template')
                    yield Static(f"Template:       {template.display_name} (v{template.version})", classes="summary-row")
                    yield Static(f"Region:         {self.coordinator.get('region')}", classes="summary-row")
                    yield Static(f"Plan:           {self.coordinator.get('instance_type')}", classes="summary-row")
                    yield Static(f"App Name:       {self.coordinator.get('app_name')}", classes="summary-row")
                    yield Static(f"Environment:    {self.coordinator.get('environment')}", classes="summary-row")
                    yield Static(f"Directory:      {self.coordinator.get('directory')}", classes="summary-row")
                    
                    capabilities = self.coordinator.get('capabilities', [])
                    if capabilities:
                        yield Static(f"Capabilities:   {', '.join(capabilities)}", classes="summary-row")
                
                yield Static("", id="status-text")
                
                with Horizontal(id="button-container"):
                    yield Button("Back", variant="default", id="back_button")
                    yield Button("Initialize & Deploy", variant="success", id="deploy_button")
            
            yield Static(
                "[Ctrl+D] Deploy  [B] Back  [Esc] Cancel",
                id="help-text"
            )
    
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button clicks."""
        if event.button.id == "deploy_button":
            self.action_deploy()
        elif event.button.id == "back_button":
            self.action_back()
    
    def action_deploy(self):
        """Execute initialization and deployment."""
        if self.is_deploying:
            return
        
        self.is_deploying = True
        
        # Disable buttons
        try:
            self.query_one("#deploy_button", Button).disabled = True
            self.query_one("#back_button", Button).disabled = True
        except:
            pass
        
        # Run deployment in background
        self.run_worker(self._execute_deployment(), exclusive=True)
    
    async def _execute_deployment(self):
        """Execute the initialization and deployment process."""
        status_text = self.query_one("#status-text", Static)
        
        def add_status(msg: str):
            """Helper to add status messages."""
            self.status_messages.append(msg)
            status_text.update("\n".join(self.status_messages))
        
        try:
            # Step 1: Initialize project
            add_status("⏳ Initializing project...")
            
            template = self.coordinator.get('template')
            directory = Path(self.coordinator.get('directory'))
            region = self.coordinator.get('region')
            instance_type = self.coordinator.get('instance_type')
            
            # Run init in thread pool to avoid blocking
            await asyncio.to_thread(
                init_operations.initialize_project,
                template=template,
                directory=directory,
                region=region,
                instance_type=instance_type
            )
            
            add_status("✓ Project initialized")
            add_status("⏳ Starting deployment...")
            await asyncio.sleep(0.5)
            
            # Step 2: Deploy project
            overrides = {
                'app_name': self.coordinator.get('app_name'),
                'env_name': self.coordinator.get('environment'),
            }
            
            # Progress callback
            def update_progress(msg: str, severity: str = "info"):
                try:
                    add_status(msg)
                except:
                    pass
            
            result = await asyncio.to_thread(
                deploy_operations.deploy_project,
                config=self.coordinator.config,
                directory=directory,
                overrides=overrides,
                wait=False,
                progress_callback=update_progress
            )
            
            add_status("")
            add_status("✓ Deployment complete!")
            await asyncio.sleep(1)
            
            # Close wizard and refresh dashboard
            self.notify(
                f"✓ Deployed {result['app_name']} to {result['region']}!",
                severity="success",
                timeout=5
            )
            
            # Pop all wizard screens and refresh dashboard
            for _ in range(5):  # Pop all wizard screens
                try:
                    self.app.pop_screen()
                except:
                    break
            
            # Refresh dashboard
            try:
                from .dashboard import DashboardScreen
                dashboard = self.app.query_one(DashboardScreen)
                dashboard.load_deployments()
                dashboard.refresh_table()
            except:
                pass
            
        except FileExistsError as e:
            add_status(f"❌ Error: {e}")
            add_status("")
            add_status("The directory or files already exist. Please choose a different location.")
            self.notify(f"Error: {e}", severity="error", timeout=10)
            self.is_deploying = False
            try:
                self.query_one("#deploy_button", Button).disabled = False
                self.query_one("#back_button", Button).disabled = False
            except:
                pass
            
        except Exception as e:
            add_status(f"❌ Error: {e}")
            self.notify(f"Deployment failed: {e}", severity="error", timeout=10)
            self.is_deploying = False
            try:
                self.query_one("#deploy_button", Button).disabled = False
                self.query_one("#back_button", Button).disabled = False
            except:
                pass
    
    def action_back(self):
        """Go back to configuration."""
        if not self.is_deploying:
            self.dismiss()
