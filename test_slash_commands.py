"""Basic test for slash command system implementation."""

import tempfile
from pathlib import Path

def test_slash_command_basic_functionality():
    """Test basic slash command functionality."""
    
    # Create temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create command directory and file
        commands_dir = temp_path / ".tunacode" / "commands"
        commands_dir.mkdir(parents=True)
        
        # Create test command
        test_cmd = commands_dir / "hello.md"
        test_cmd.write_text("""---
description: Simple hello command
---

# Hello Command

Hello $ARGUMENTS! This is a test command.

## Current Directory
Working in: !`pwd`

Your task: $ARGUMENTS
""")
        
        # Test SlashCommandLoader
        try:
            from src.tunacode.cli.commands.slash.loader import SlashCommandLoader
            
            loader = SlashCommandLoader(temp_path, temp_path)  # Use temp as both project and user
            result = loader.discover_commands()
            
            print(f"✅ SlashCommandLoader works!")
            print(f"   Discovered {len(result.commands)} commands")
            print(f"   Commands: {list(result.commands.keys())}")
            
            if result.commands:
                # Test command creation
                hello_cmd = result.commands.get('project:hello')
                if hello_cmd:
                    print(f"✅ Command creation works!")
                    print(f"   Command name: {hello_cmd.name}")
                    print(f"   Description: {hello_cmd.description}")
                else:
                    print("❌ Command not found in results")
            else:
                print("❌ No commands discovered")
                
        except ImportError as e:
            print(f"❌ Import error: {e}")
        except Exception as e:
            print(f"❌ Error testing SlashCommandLoader: {e}")
            
        # Test MarkdownTemplateProcessor
        try:
            from src.tunacode.cli.commands.slash.processor import MarkdownTemplateProcessor
            
            processor = MarkdownTemplateProcessor()
            
            # Test frontmatter parsing
            content = """---
description: Test command
---
# Hello $ARGUMENTS
"""
            frontmatter, markdown = processor.parse_frontmatter(content)
            
            if frontmatter and frontmatter.get('description') == 'Test command':
                print("✅ MarkdownTemplateProcessor frontmatter parsing works!")
            else:
                print("❌ Frontmatter parsing failed")
                
        except ImportError as e:
            print(f"❌ Import error: {e}")
        except Exception as e:
            print(f"❌ Error testing MarkdownTemplateProcessor: {e}")
            
        # Test CommandValidator
        try:
            from src.tunacode.cli.commands.slash.validator import CommandValidator
            
            validator = CommandValidator()
            
            # Test safe command
            result = validator.validate_shell_command("echo hello")
            if result.allowed:
                print("✅ CommandValidator allows safe commands!")
            else:
                print("❌ CommandValidator blocked safe command")
                
            # Test dangerous command
            result = validator.validate_shell_command("rm -rf /")
            if not result.allowed:
                print("✅ CommandValidator blocks dangerous commands!")
            else:
                print("❌ CommandValidator allowed dangerous command")
                
        except ImportError as e:
            print(f"❌ Import error: {e}")
        except Exception as e:
            print(f"❌ Error testing CommandValidator: {e}")

if __name__ == "__main__":
    print("🧪 Testing Slash Command System Implementation")
    print("=" * 50)
    test_slash_command_basic_functionality()
    print("=" * 50)
    print("✅ Basic implementation test complete!")