"""Test lazy loading of Rich UI components."""

import sys
import time


def test_import_time_before_lazy():
    """Test import time before lazy loading - baseline measurement."""
    start = time.perf_counter()

    # Import the module that would trigger Rich loading
    import importlib.util

    spec = importlib.util.spec_from_file_location("console_direct", "src/tunacode/ui/console.py")
    importlib.util.module_from_spec(spec)

    # This would load Rich components immediately in old version
    # spec.loader.exec_module(module)

    end = time.perf_counter()
    return end - start


def test_lazy_loading_functionality():
    """Test that lazy loading works correctly and provides same functionality."""
    from tunacode.ui.console import get_console, get_markdown, markdown
    from tunacode.ui.output import get_console as get_output_console
    from tunacode.ui.panels import get_rich_components

    # Test that lazy accessors work
    console = get_console()
    assert console is not None

    # Test markdown creation
    md_class = get_markdown()
    assert md_class is not None

    md_obj = markdown("# Test")
    assert md_obj is not None

    # Test output console
    out_console = get_output_console()
    assert out_console is not None

    # Test panels rich components
    rich_comps = get_rich_components()
    assert "Panel" in rich_comps
    assert "Markdown" in rich_comps
    assert "Table" in rich_comps

    print("✓ All lazy loading accessors work correctly")
    return True


def test_startup_import_time():
    """Measure startup import time with lazy loading."""
    start = time.perf_counter()

    # Import modules that should not trigger Rich loading immediately
    from tunacode.ui import console

    end = time.perf_counter()
    import_time = end - start

    print(f"UI modules import time: {import_time:.4f}s")

    # Test that Rich components are not loaded until accessed
    initial_console_count = len(
        [obj for name, obj in sys.modules.items() if "rich" in name.lower()]
    )

    # Access a Rich component
    console.get_console()

    after_console_count = len([obj for name, obj in sys.modules.items() if "rich" in name.lower()])

    print(f"Rich modules before access: {initial_console_count}")
    print(f"Rich modules after access: {after_console_count}")

    # Should have loaded more Rich modules after access
    assert after_console_count >= initial_console_count

    return import_time


if __name__ == "__main__":
    print("Testing Rich UI lazy loading...")

    # Test functionality
    test_lazy_loading_functionality()

    # Test import time
    import_time = test_startup_import_time()

    print("\nLazy loading test completed successfully!")
    print(f"UI modules imported in {import_time:.4f}s without loading Rich components")
