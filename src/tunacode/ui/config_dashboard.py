"""
Interactive configuration dashboard UI component.

Provides terminal-based visualization of configuration state with
navigation, filtering, and detailed inspection capabilities.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rich.box import ROUNDED
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from textual.containers import Vertical

from tunacode.constants import UI_COLORS
from tunacode.utils.config_comparator import (
    ConfigAnalysis,
    ConfigComparator,
    ConfigDifference,
    create_config_report,
)
from tunacode.utils.file_utils import DotDict

colors = DotDict(UI_COLORS)


@dataclass
class DashboardConfig:
    """Configuration for dashboard behavior."""

    show_defaults: bool = True
    show_custom: bool = True
    show_missing: bool = True
    show_extra: bool = True
    show_type_mismatches: bool = True
    max_section_items: int = 20
    sort_by: str = "section"  # "section", "type", "key"
    filter_section: Optional[str] = None
    filter_type: Optional[str] = None


class ConfigDashboard:
    """Interactive configuration dashboard with Rich UI."""

    def __init__(self, user_config: Optional[Dict[str, Any]] = None):
        """Initialize the configuration dashboard."""
        self.console = Console()
        self.analysis: Optional[ConfigAnalysis] = None
        self.config = DashboardConfig()
        self.selected_item: Optional[ConfigDifference] = None

        # Load and analyze configuration
        if user_config is None:
            from tunacode.utils.user_configuration import load_config

            user_config = load_config()
            if user_config is None:
                raise ValueError("No user configuration found")

        self.load_analysis(user_config)

    def load_analysis(self, user_config: Dict[str, Any]) -> None:
        """Load and analyze the user configuration."""
        comparator = ConfigComparator()
        self.analysis = comparator.analyze_config(user_config)

    def render_overview(self) -> Panel:
        """Render the overview panel with key statistics."""
        if not self.analysis:
            return Panel("No configuration loaded", title="Overview", box=ROUNDED)

        stats = ConfigComparator().get_summary_stats(self.analysis)

        # Create overview table
        table = Table.grid(padding=(0, 2))
        table.add_column("Metric", style=colors.primary, no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("Total Keys", str(stats["total_keys_analyzed"]))
        table.add_row(
            "Custom Keys", f"{stats['custom_keys_count']} ({stats['custom_percentage']:.1f}%)"
        )
        table.add_row("Missing Keys", str(stats["missing_keys_count"]))
        table.add_row("Extra Keys", str(stats["extra_keys_count"]))
        table.add_row("Type Mismatches", str(stats["type_mismatches_count"]))
        table.add_row("Sections", str(stats["sections_analyzed"]))

        health_status = "✅ Healthy" if not stats["has_issues"] else "⚠️ Issues Found"
        health_style = colors.success if not stats["has_issues"] else colors.warning
        table.add_row("Status", Text(health_status, style=health_style))

        return Panel(table, title="Configuration Overview", box=ROUNDED, border_style=colors.border)

    def render_section_tree(self) -> Panel:
        """Render the configuration section tree."""
        if not self.analysis:
            return Panel("No configuration loaded", title="Sections", box=ROUNDED)

        tree = Tree("Configuration Structure")

        for section in sorted(self.analysis.sections_analyzed):
            section_diffs = [diff for diff in self.analysis.differences if diff.section == section]

            if section_diffs:
                section_node = tree.add(f"[bold]{section}[/bold] ({len(section_diffs)} items)")

                for diff in section_diffs[: self.config.max_section_items]:
                    self._add_diff_to_tree(section_node, diff)

                if len(section_diffs) > self.config.max_section_items:
                    more_count = len(section_diffs) - self.config.max_section_items
                    section_node.add(Text(f"[dim]... and {more_count} more[/dim]"))
            else:
                tree.add(f"[dim]{section}[/dim]")

        return Panel(tree, title="Configuration Sections", box=ROUNDED, border_style=colors.border)

    def _add_diff_to_tree(self, parent: Tree, diff: ConfigDifference) -> None:
        """Add a configuration difference to the tree."""
        icon_map = {"custom": "✏️", "missing": "❌", "extra": "➕", "type_mismatch": "⚠️"}

        style_map = {
            "custom": colors.warning,
            "missing": colors.error,
            "extra": colors.primary_dark,
            "type_mismatch": f"bold {colors.error}",
        }

        icon = icon_map.get(diff.difference_type, "❓")
        style = style_map.get(diff.difference_type, "white")

        diff_text = f"{icon} [dim]{diff.key_path}[/dim]"

        if diff.user_value is not None:
            # Mask sensitive values
            display_value = self._mask_sensitive_value(diff.user_value)
            diff_text += f": [white]{display_value}[/white]"

        parent.add(Text(diff_text, style=style))

    def render_differences_table(self) -> Panel:
        """Render the detailed differences table."""
        if not self.analysis:
            return Panel("No configuration loaded", title="Differences", box=ROUNDED)

        # Filter differences based on config
        filtered_diffs = self._filter_differences()

        if not filtered_diffs:
            return Panel("No differences to display", title="Differences", box=ROUNDED)

        # Create differences table
        table = Table(box=ROUNDED, show_header=True, header_style=f"bold {colors.accent}")

        table.add_column("Key", style=colors.primary, no_wrap=True)
        table.add_column("Type", style=colors.warning)
        table.add_column("User Value", style="white")
        table.add_column("Default Value", style=colors.muted)
        table.add_column("Section", style=colors.secondary)

        for diff in filtered_diffs[: self.config.max_section_items]:
            user_value = self._mask_sensitive_value(diff.user_value, diff.key_path)
            default_value = self._mask_sensitive_value(diff.default_value, diff.key_path)

            # Format type with icon
            type_map = {
                "custom": "✏️ Custom",
                "missing": "❌ Missing",
                "extra": "➕ Extra",
                "type_mismatch": "⚠️ Type Mismatch",
            }

            diff_type = type_map.get(diff.difference_type, diff.difference_type)

            table.add_row(
                diff.key_path,
                diff_type,
                str(user_value) if user_value is not None else "",
                str(default_value) if default_value is not None else "",
                diff.section,
            )

        if len(filtered_diffs) > self.config.max_section_items:
            table.add_row(
                "",
                f"[dim]... and {len(filtered_diffs) - self.config.max_section_items} more[/dim]",
                "",
                "",
                "",
            )

        return Panel(
            table,
            title=f"Configuration Differences ({len(filtered_diffs)} items)",
            box=ROUNDED,
            border_style=colors.accent,
        )

    def _filter_differences(self) -> List[ConfigDifference]:
        """Filter differences based on dashboard configuration."""
        if not self.analysis:
            return []

        filtered = []

        for diff in self.analysis.differences:
            # Apply type filter
            if self.config.filter_type and diff.difference_type != self.config.filter_type:
                continue

            # Apply section filter
            if self.config.filter_section and diff.section != self.config.filter_section:
                continue

            # Apply show/hide filters
            if diff.difference_type == "custom" and not self.config.show_custom:
                continue
            elif diff.difference_type == "missing" and not self.config.show_missing:
                continue
            elif diff.difference_type == "extra" and not self.config.show_extra:
                continue
            elif diff.difference_type == "type_mismatch" and not self.config.show_type_mismatches:
                continue

            filtered.append(diff)

        # Sort differences
        if self.config.sort_by == "section":
            filtered.sort(key=lambda d: (d.section, d.key_path))
        elif self.config.sort_by == "type":
            filtered.sort(key=lambda d: (d.difference_type, d.key_path))
        else:  # key
            filtered.sort(key=lambda d: d.key_path)

        return filtered

    def _mask_sensitive_value(self, value: Any, key_path: str = "") -> str:
        """Mask sensitive configuration values for display with service identification."""
        if value is None:
            return ""

        value_str = str(value)

        # Empty values should show as empty
        if not value_str.strip():
            return "[dim]<not configured>[/dim]"

        # Check if this is an API key based on key path
        service_type = self._get_service_type_from_key_path(key_path)
        if service_type:
            return self._format_api_key_with_service(value_str, service_type)

        # Check for common API key patterns
        if value_str.startswith("sk-"):
            # OpenAI-style keys
            service = "OpenAI" if "openai" in key_path.lower() else "Unknown"
            return self._format_api_key_with_service(value_str, service.lower())
        elif value_str.startswith("sk-ant-"):
            return self._format_api_key_with_service(value_str, "anthropic")
        elif value_str.startswith("sk-or-"):
            return self._format_api_key_with_service(value_str, "openrouter")
        elif value_str.startswith("AIza"):
            return self._format_api_key_with_service(value_str, "google")

        # Check for other sensitive patterns (non-API keys)
        sensitive_patterns = [
            "secret",
            "token",
            "password",
            "credential",
        ]

        for pattern in sensitive_patterns:
            if pattern in key_path.lower() or pattern in value_str.lower():
                return "•" * 8  # Fully mask non-API key secrets

        return value_str

    def _get_service_type_from_key_path(self, key_path: str) -> str:
        """Determine service type from configuration key path."""
        key_lower = key_path.lower()

        if "openai_api_key" in key_lower:
            return "openai"
        elif "anthropic_api_key" in key_lower:
            return "anthropic"
        elif "openrouter_api_key" in key_lower:
            return "openrouter"
        elif "gemini_api_key" in key_lower:
            return "google"

        return ""

    def _format_api_key_with_service(self, api_key: str, service_type: str) -> str:
        """Format API key with service identification and partial masking."""
        service_names = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "openrouter": "OpenRouter",
            "google": "Google",
        }

        service_name = service_names.get(service_type, service_type.title())

        if len(api_key) <= 8:
            # Short keys - just show service and mask
            return f"[{colors.primary}]{service_name}:[/{colors.primary}] •••••••"
        else:
            # Show first 4 and last 4 characters with service label
            masked = f"{api_key[:4]}...{api_key[-4:]}"
            return f"[{colors.primary}]{service_name}:[/{colors.primary}] {masked}"

    def render_recommendations(self) -> Panel:
        """Render configuration recommendations."""
        if not self.analysis:
            return Panel("No configuration loaded", title="Recommendations", box=ROUNDED)

        recommendations = ConfigComparator().get_recommendations(self.analysis)

        if not recommendations:
            return Panel(
                "✅ No recommendations - configuration looks good!",
                title="Recommendations",
                box=ROUNDED,
                border_style=colors.success,
            )

        rec_text = "\n".join(f"• {rec}" for rec in recommendations)

        return Panel(rec_text, title="Recommendations", box=ROUNDED, border_style=colors.warning)

    def render_custom_settings(self) -> Panel:
        """Render panel showing only custom (user-modified) settings."""
        if not self.analysis:
            return Panel("No configuration loaded", title="Your Customizations", box=ROUNDED)

        # Filter for only custom settings
        custom_diffs = [
            diff for diff in self.analysis.differences if diff.difference_type == "custom"
        ]

        if not custom_diffs:
            message = (
                "✨ You're using all default settings!\n\n"
                "This means TunaCode is running with its built-in configuration. "
                "You can customize settings by editing ~/.config/tunacode.json"
            )
            return Panel(
                message,
                title="🔧 Your Customizations (0)",
                box=ROUNDED,
                border_style=colors.success,
            )

        # Create table for custom settings
        table = Table(box=ROUNDED, show_header=True, header_style=f"bold {colors.primary}")
        table.add_column("Setting", style=colors.primary, no_wrap=True)
        table.add_column("Your Value", style="white")
        table.add_column("Default Value", style=colors.muted)
        table.add_column("Category", style=colors.secondary)

        for diff in custom_diffs[:15]:  # Limit to prevent overflow
            user_value = self._mask_sensitive_value(diff.user_value, diff.key_path)
            default_value = self._mask_sensitive_value(diff.default_value, diff.key_path)

            # Get category from key descriptions
            from tunacode.configuration.key_descriptions import get_key_description

            desc = get_key_description(diff.key_path)
            category = desc.category if desc else diff.section.title()

            table.add_row(
                diff.key_path,
                str(user_value) if user_value is not None else "",
                str(default_value) if default_value is not None else "",
                category,
            )

        if len(custom_diffs) > 15:
            table.add_row("", f"[dim]... and {len(custom_diffs) - 15} more[/dim]", "", "")

        summary = (
            f"You have customized {len(custom_diffs)} out of "
            f"{self.analysis.total_keys} available settings"
        )

        content = Group(Text(summary, style="bold"), Text(""), table)

        return Panel(
            content,
            title=f"🔧 Your Customizations ({len(custom_diffs)})",
            box=ROUNDED,
            border_style=colors.primary,
        )

    def render_default_settings_summary(self) -> Panel:
        """Render panel showing summary of default settings by category."""
        if not self.analysis:
            return Panel("No configuration loaded", title="Default Settings", box=ROUNDED)

        # Get all default settings (not customized)
        custom_keys = {
            diff.key_path for diff in self.analysis.differences if diff.difference_type == "custom"
        }

        # Import here to avoid circular imports
        from tunacode.configuration.key_descriptions import get_categories

        categories = get_categories()

        # Count settings by category
        category_counts = {}
        category_examples = {}

        for category, descriptions in categories.items():
            default_count = 0
            examples: List[str] = []

            for desc in descriptions:
                if desc.name not in custom_keys:
                    default_count += 1
                    if len(examples) < 3:  # Show up to 3 examples
                        examples.append(f"• {desc.name}")

            if default_count > 0:
                category_counts[category] = default_count
                category_examples[category] = examples

        if not category_counts:
            return Panel(
                "All settings have been customized", title="📋 Default Settings", box=ROUNDED
            )

        # Create summary table
        table = Table.grid(padding=(0, 2))
        table.add_column("Category", style=colors.warning, no_wrap=True)
        table.add_column("Count", style="white")
        table.add_column("Examples", style=colors.muted)

        for category, count in sorted(category_counts.items()):
            examples_text = "\n".join(category_examples[category])
            table.add_row(category, f"{count} settings", examples_text)

        total_defaults = sum(category_counts.values())
        summary = f"Using TunaCode defaults for {total_defaults} settings"

        content = Group(Text(summary, style="bold"), Text(""), table)

        return Panel(
            content,
            title=f"📋 Default Settings ({total_defaults})",
            box=ROUNDED,
            border_style=colors.border,
        )

    def render_help(self) -> Panel:
        """Render help information with configuration key glossary."""
        # Import here to avoid circular imports
        from tunacode.configuration.key_descriptions import get_configuration_glossary

        help_text = """
[bold]Configuration Dashboard Guide[/bold]

[cyan]Dashboard Sections:[/cyan]
• [yellow]Your Customizations[/yellow]: Settings you've changed from defaults (🔧)
• [yellow]Default Settings[/yellow]: TunaCode's built-in settings you're using (📋)
• [yellow]All Differences[/yellow]: Complete comparison view

[cyan]API Key Display:[/cyan]
• [cyan]OpenAI:[/cyan] sk-abc...xyz - Shows service and partial key
• [cyan]Anthropic:[/cyan] sk-ant...xyz - Secure but identifiable
• [dim]<not configured>[/dim] - No API key set

[cyan]Visual Indicators:[/cyan]
• 🔧 Custom: Values you've changed from defaults
• 📋 Default: TunaCode's built-in settings
• ❌ Missing: Required configuration keys not found
• ➕ Extra: Keys not in default configuration
• ⚠️ Type Mismatch: Wrong data type for configuration

[cyan]Exit:[/cyan]
• Press Ctrl+C to return to TunaCode
        """

        glossary = get_configuration_glossary()

        content = Vertical(Text(help_text.strip()), Text(""), Text(glossary))

        return Panel(content, title="Help & Glossary", box=ROUNDED, border_style=colors.border)

    def render_dashboard(self) -> Layout:
        """Render the complete dashboard layout with improved organization."""
        layout = Layout()

        # Split into main areas - increase footer size for glossary
        layout.split_column(
            Layout(name="header", size=3), Layout(name="main"), Layout(name="footer", size=12)
        )

        # Split main area into three columns for better organization
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=1),
            Layout(name="right", ratio=1),
        )

        # Left column: Overview and custom settings
        layout["left"].split_column(
            Layout(name="overview", size=8), Layout(name="custom_settings", ratio=1)
        )

        # Center column: Default settings and section tree
        layout["center"].split_column(
            Layout(name="default_settings", ratio=1), Layout(name="sections", ratio=1)
        )

        # Right column: All differences and recommendations
        layout["right"].split_column(
            Layout(name="differences", ratio=2), Layout(name="recommendations", size=6)
        )

        # Add content to each area
        header_panel = Panel(
            "🐟 TunaCode Configuration Dashboard",
            style=f"bold {colors.primary}",
            box=ROUNDED,
        )
        layout["header"].update(header_panel)

        layout["overview"].update(self.render_overview())
        layout["custom_settings"].update(self.render_custom_settings())
        layout["default_settings"].update(self.render_default_settings_summary())
        layout["sections"].update(self.render_section_tree())
        layout["differences"].update(self.render_differences_table())
        layout["recommendations"].update(self.render_recommendations())
        layout["footer"].update(self.render_help())

        return layout

    def show(self, wait_for_input: bool = True) -> None:
        """Display the interactive dashboard.

        Args:
            wait_for_input: If True, wait for user to press Enter.
                Set to False for non-interactive usage.
        """
        if not self.analysis:
            self.console.print("[red]No configuration analysis available[/red]")
            return

        layout = self.render_dashboard()

        try:
            with Live(layout, console=self.console, refresh_per_second=4):
                # In a real implementation, this would handle user input
                # For now, we'll just display the dashboard
                if wait_for_input:
                    input("Press Enter to continue...")
        except KeyboardInterrupt:
            self.console.print("\n[dim]Dashboard closed[/dim]")

    def generate_report(self) -> str:
        """Generate a text report of the configuration analysis."""
        if not self.analysis:
            return "No configuration analysis available"

        return create_config_report(self.analysis)


def show_config_dashboard(
    user_config: Optional[Dict[str, Any]] = None, wait_for_input: bool = False
) -> None:
    """Convenience function to show the configuration dashboard.

    Args:
        user_config: Optional user configuration dictionary.
        wait_for_input: If True, wait for user to press Enter. Defaults to False for CLI usage.
    """
    dashboard = ConfigDashboard(user_config)
    dashboard.show(wait_for_input=wait_for_input)


def generate_config_report(user_config: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to generate a configuration report."""
    dashboard = ConfigDashboard(user_config)
    return dashboard.generate_report()
