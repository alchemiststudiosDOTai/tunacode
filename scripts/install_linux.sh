#!/usr/bin/env bash
# TunaCode CLI Installer - UV/pip Enhanced Version
#
# One-line install:
# curl -sSL https://raw.githubusercontent.com/alchemiststudiosDOTai/tunacode/master/scripts/install_linux.sh | bash
#
# Or with wget:
# wget -qO- https://raw.githubusercontent.com/alchemiststudiosDOTai/tunacode/master/scripts/install_linux.sh | bash

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

VENV_DIR="${HOME}/.tunacode-venv"
BIN_DIR="${HOME}/.local/bin"
PYTHON=${PYTHON:-python3}
USE_UV=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo -e "${BLUE}🐟 TunaCode CLI Installer${NC}"
echo "================================"

# Detect UV availability
if command -v uv &> /dev/null; then
    USE_UV=true
    UV_VERSION=$(uv --version 2>/dev/null | cut -d' ' -f2 || echo "unknown")
    echo -e "${GREEN}✓${NC} UV detected (version: $UV_VERSION) - Using fast installer"
else
    echo -e "${BLUE}Using standard pip installer${NC}"
    echo -e "  ${YELLOW}Tip:${NC} Install UV for 10-100x faster installations:"
    echo -e "  curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Enhanced installation detection with health checks
detect_installations() {
    local found_venv=false
    local found_global_system=false
    local found_global_user=false
    local venv_working=false
    local global_system_working=false
    local global_user_working=false

    echo -e "${BLUE}Scanning for existing TunaCode installations...${NC}"

    # Check venv installation
    if [ -f "$VENV_DIR/bin/tunacode" ]; then
        found_venv=true
        if "$VENV_DIR/bin/tunacode" --version &>/dev/null; then
            venv_working=true
            echo -e "${GREEN}✓${NC} Found working venv installation"
        else
            echo -e "${YELLOW}⚠${NC} Found venv installation but it's not working"
        fi
    fi

    # Check global system installation
    if command -v tunacode &>/dev/null; then
        local tunacode_path=$(command -v tunacode)
        if [[ "$tunacode_path" =~ ^/usr/local/bin/ ]] || [[ "$tunacode_path" =~ ^/usr/bin/ ]]; then
            found_global_system=true
            if tunacode --version &>/dev/null; then
                global_system_working=true
                echo -e "${GREEN}✓${NC} Found working global system installation"
            else
                echo -e "${YELLOW}⚠${NC} Found global system installation but it's not working"
            fi
        fi
    fi

    # Check global user installation (distinguish from wrapper script)
    if [ -f "$HOME/.local/bin/tunacode" ]; then
        # Check if it's our wrapper script or actual binary
        if grep -q "\.tunacode-venv/bin/tunacode" "$HOME/.local/bin/tunacode" 2>/dev/null; then
            # This is our wrapper script, not a user install
            echo -e "${BLUE}Found wrapper script pointing to venv${NC}"
        else
            # This is an actual user site-packages installation
            found_global_user=true
            if "$HOME/.local/bin/tunacode" --version &>/dev/null; then
                global_user_working=true
                echo -e "${GREEN}✓${NC} Found working global user installation"
            else
                echo -e "${YELLOW}⚠${NC} Found global user installation but it's not working"
            fi
        fi
    fi

    # Check wrapper script health (only if it's actually our wrapper)
    local wrapper_status="missing"
    if [ -f "$BIN_DIR/tunacode" ] && grep -q "\.tunacode-venv/bin/tunacode" "$BIN_DIR/tunacode" 2>/dev/null; then
        if [ -x "$BIN_DIR/tunacode" ]; then
            if "$BIN_DIR/tunacode" --version &>/dev/null; then
                wrapper_status="working"
                echo -e "${GREEN}✓${NC} Wrapper script is working"
            else
                wrapper_status="broken"
                echo -e "${YELLOW}⚠${NC} Wrapper script exists but not working"
            fi
        else
            wrapper_status="not_executable"
            echo -e "${YELLOW}⚠${NC} Wrapper script not executable"
        fi
    fi

    # Export detection results
    export FOUND_VENV=$found_venv
    export FOUND_GLOBAL_SYSTEM=$found_global_system
    export FOUND_GLOBAL_USER=$found_global_user
    export VENV_WORKING=$venv_working
    export GLOBAL_SYSTEM_WORKING=$global_system_working
    export GLOBAL_USER_WORKING=$global_user_working
    export WRAPPER_STATUS=$wrapper_status
}

# Backup current working installation
create_backup() {
    local backup_dir="/tmp/tunacode-backup-$(date +%s)"
    mkdir -p "$backup_dir"

    echo -e "${BLUE}Creating backup at $backup_dir...${NC}"

    # Backup venv if it exists
    if [ -d "$VENV_DIR" ]; then
        cp -r "$VENV_DIR" "$backup_dir/venv"
    fi

    # Backup wrapper script
    if [ -f "$BIN_DIR/tunacode" ]; then
        cp "$BIN_DIR/tunacode" "$backup_dir/wrapper"
    fi

    export BACKUP_DIR="$backup_dir"
    echo -e "${GREEN}✓${NC} Backup created at $backup_dir"
}

# Rollback from backup
rollback() {
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        echo -e "${YELLOW}Rolling back to previous installation...${NC}"

        # Restore venv
        if [ -d "$BACKUP_DIR/venv" ]; then
            rm -rf "$VENV_DIR" 2>/dev/null || true
            cp -r "$BACKUP_DIR/venv" "$VENV_DIR"
        fi

        # Restore wrapper
        if [ -f "$BACKUP_DIR/wrapper" ]; then
            cp "$BACKUP_DIR/wrapper" "$BIN_DIR/tunacode"
            chmod +x "$BIN_DIR/tunacode"
        fi

        echo -e "${GREEN}✓${NC} Rollback completed"
    else
        echo -e "${RED}✗${NC} No backup available for rollback"
    fi
}

# Smart update with retry and error handling
perform_update() {
    local install_method="$1"
    local max_retries=3
    local retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        echo -e "${BLUE}Update attempt $((retry_count + 1))/$max_retries using $install_method method...${NC}"

        case "$install_method" in
            "venv_uv")
                if uv pip install --python "$VENV_DIR/bin/python" --upgrade tunacode-cli --quiet; then
                    return 0
                fi
                ;;
            "venv_pip")
                if "$VENV_DIR/bin/pip" install --upgrade tunacode-cli --quiet; then
                    return 0
                fi
                ;;
            "global_system_uv")
                if uv pip install --system --upgrade tunacode-cli --quiet; then
                    return 0
                fi
                ;;
            "global_user_uv")
                if uv pip install --user --upgrade tunacode-cli --quiet; then
                    return 0
                fi
                ;;
            "global_user_pip")
                if pip install --user --upgrade tunacode-cli --quiet; then
                    return 0
                fi
                ;;
        esac

        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo -e "${YELLOW}⚠${NC} Update failed, retrying in 3 seconds..."
            sleep 3
        fi
    done

    return 1
}

# Verify installation after update
verify_installation() {
    local method="$1"

    echo -e "${BLUE}Verifying installation...${NC}"

    case "$method" in
        "venv"*)
            if [ -f "$VENV_DIR/bin/tunacode" ] && "$VENV_DIR/bin/tunacode" --version &>/dev/null; then
                echo -e "${GREEN}✓${NC} Venv installation verified"
                return 0
            fi
            ;;
        "global"*)
            if command -v tunacode &>/dev/null && tunacode --version &>/dev/null; then
                echo -e "${GREEN}✓${NC} Global installation verified"
                return 0
            fi
            ;;
    esac

    echo -e "${RED}✗${NC} Installation verification failed"
    return 1
}

# Repair or create wrapper script
repair_wrapper() {
    echo -e "${BLUE}Repairing wrapper script...${NC}"

    # Determine best target for wrapper
    if [ "$VENV_WORKING" = true ] || [ -f "$VENV_DIR/bin/tunacode" ]; then
        # Point to venv installation
        cat <<'EOW' >"$BIN_DIR/tunacode"
#!/usr/bin/env bash
exec "$HOME/.tunacode-venv/bin/tunacode" "$@"
EOW
        echo -e "${GREEN}✓${NC} Wrapper points to venv installation"
    elif [ "$GLOBAL_SYSTEM_WORKING" = true ] || [ "$GLOBAL_USER_WORKING" = true ]; then
        # Point to global installation
        cat <<'EOW' >"$BIN_DIR/tunacode"
#!/usr/bin/env bash
exec "$(command -v tunacode)" "$@"
EOW
        echo -e "${GREEN}✓${NC} Wrapper points to global installation"
    else
        echo -e "${RED}✗${NC} No working installation found for wrapper"
        return 1
    fi

    chmod +x "$BIN_DIR/tunacode"

    # Verify wrapper works
    if "$BIN_DIR/tunacode" --version &>/dev/null; then
        echo -e "${GREEN}✓${NC} Wrapper script working correctly"
        return 0
    else
        echo -e "${RED}✗${NC} Wrapper script still not working"
        return 1
    fi
}

# Cleanup backup after successful update
cleanup_backup() {
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        rm -rf "$BACKUP_DIR"
        echo -e "${GREEN}✓${NC} Backup cleaned up"
    fi
}

# Main update logic
if [ -d "$VENV_DIR" ] || [ -f "$BIN_DIR/tunacode" ] || command -v tunacode &>/dev/null; then
    echo -e "${YELLOW}TunaCode installation detected.${NC}"

    # Enhanced detection
    detect_installations

    # Count working installations
    working_count=0
    [ "$VENV_WORKING" = true ] && working_count=$((working_count + 1))
    [ "$GLOBAL_SYSTEM_WORKING" = true ] && working_count=$((working_count + 1))
    [ "$GLOBAL_USER_WORKING" = true ] && working_count=$((working_count + 1))

    if [ $working_count -eq 0 ]; then
        echo -e "${RED}No working installations found. Please run a fresh installation.${NC}"
        echo -e "Remove $VENV_DIR and $BIN_DIR/tunacode if they exist, then re-run this script."
        exit 1
    elif [ $working_count -gt 1 ]; then
        echo -e "${YELLOW}Multiple TunaCode installations detected:${NC}"
        [ "$VENV_WORKING" = true ] && echo -e "  - Venv installation (working)"
        [ "$GLOBAL_SYSTEM_WORKING" = true ] && echo -e "  - Global system installation (working)"
        [ "$GLOBAL_USER_WORKING" = true ] && echo -e "  - Global user installation (working)"
        echo -e "\n${YELLOW}Which installation would you like to update?${NC}"
        echo -e "1) Venv installation (recommended)"
        echo -e "2) Global system installation"
        echo -e "3) Global user installation"
        echo -e "4) Skip update"
        echo -e "\nChoice (1-4): "
        read -r choice

        case "$choice" in
            1) UPDATE_TARGET="venv" ;;
            2) UPDATE_TARGET="global_system" ;;
            3) UPDATE_TARGET="global_user" ;;
            4) echo -e "${BLUE}Skipping update.${NC}"; exit 0 ;;
            *) echo -e "${RED}Invalid choice. Skipping update.${NC}"; exit 1 ;;
        esac
    else
        # Single working installation - auto-detect
        if [ "$VENV_WORKING" = true ]; then
            UPDATE_TARGET="venv"
        elif [ "$GLOBAL_SYSTEM_WORKING" = true ]; then
            UPDATE_TARGET="global_system"
        elif [ "$GLOBAL_USER_WORKING" = true ]; then
            UPDATE_TARGET="global_user"
        fi
    fi

    echo -e "\nWould you like to update to the latest version? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Skipping update.${NC}"
        exit 0
    fi

    # Create backup before update
    create_backup

    # Set trap for rollback on failure
    trap 'echo -e "\n${RED}Update failed!${NC}"; rollback; exit 1' ERR

    echo -e "${BLUE}Updating TunaCode ($UPDATE_TARGET installation)...${NC}"

    # Determine update method
    update_method=""
    case "$UPDATE_TARGET" in
        "venv")
            if [ "$USE_UV" = true ]; then
                update_method="venv_uv"
            else
                update_method="venv_pip"
            fi
            ;;
        "global_system")
            if [ "$USE_UV" = true ]; then
                update_method="global_system_uv"
            else
                echo -e "${RED}Cannot update global system installation without UV${NC}"
                rollback
                exit 1
            fi
            ;;
        "global_user")
            if [ "$USE_UV" = true ]; then
                update_method="global_user_uv"
            else
                update_method="global_user_pip"
            fi
            ;;
    esac

    # Perform update with retry
    if ! perform_update "$update_method"; then
        echo -e "${RED}Update failed after multiple attempts${NC}"
        rollback
        exit 1
    fi

    # Verify update worked
    if ! verify_installation "$update_method"; then
        echo -e "${RED}Update verification failed${NC}"
        rollback
        exit 1
    fi

    # Repair wrapper script if needed
    if [ "$WRAPPER_STATUS" != "working" ]; then
        if ! repair_wrapper; then
            echo -e "${YELLOW}⚠${NC} Wrapper repair failed, but main installation is working"
        fi
    fi

    # Clear trap and cleanup
    trap - ERR
    cleanup_backup

    echo -e "\n${GREEN}✅ TunaCode updated successfully!${NC}"
    echo -e "Run ${BLUE}tunacode --version${NC} to verify the new version"
    exit 0
fi

# Check Python version
if ! command -v "$PYTHON" &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found!${NC}"
    echo "Please install Python 3.10 or higher first."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
# Check if Python version is less than 3.10 without using bc
if ! "$PYTHON" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo -e "${RED}Error: Python 3.10 or higher required${NC}"
    echo "Found Python $PYTHON_VERSION"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Remove old installation if exists
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Removing old installation...${NC}"
    rm -rf "$VENV_DIR"
fi

# Create virtual environment
echo -e "\n${BLUE}Creating virtual environment...${NC}"
if [ "$USE_UV" = true ]; then
    uv venv "$VENV_DIR"
else
    "$PYTHON" -m venv "$VENV_DIR"
fi

# Upgrade pip and install tunacode
echo -e "${BLUE}Installing TunaCode CLI...${NC}"
if [ "$USE_UV" = true ]; then
    # UV manages pip/setuptools automatically and is much faster
    uv pip install --python "$VENV_DIR/bin/python" tunacode-cli --quiet
else
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet
    "$VENV_DIR/bin/pip" install tunacode-cli --quiet
fi

# Create bin directory and wrapper script
mkdir -p "$BIN_DIR"
cat <<'EOW' >"$BIN_DIR/tunacode"
#!/usr/bin/env bash
exec "$HOME/.tunacode-venv/bin/tunacode" "$@"
EOW
chmod +x "$BIN_DIR/tunacode"

# --- auto-fallback if not in PATH ---
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  # If we're root, drop a symlink into /usr/local/bin
  if [[ $EUID -eq 0 ]]; then
    ln -s "$BIN_DIR/tunacode" /usr/local/bin/tunacode 2>/dev/null || true
  else
    # Non-root: append to ~/.profile so future logins get it
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
  fi
fi

# Create config directory and initial config file
CONFIG_DIR="${HOME}/.config"
CONFIG_FILE="$CONFIG_DIR/tunacode.json"
mkdir -p "$CONFIG_DIR"

# Create initial config file if it doesn't exist
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${BLUE}Creating initial configuration file...${NC}"
    cat <<'EOC' >"$CONFIG_FILE"
{
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENROUTER_API_KEY": ""
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "tool_ignore": ["read_file"],
        "guide_file": "AGENTS.md",
        "fallback_response": true,
        "fallback_verbosity": "normal",
        "context_window_size": 200000,
        "ripgrep": {
            "use_bundled": false,
            "timeout": 10,
            "max_buffer_size": 1048576,
            "max_results": 100,
            "enable_metrics": false,
            "debug": false
        }
    },
    "mcpServers": {}
}
EOC
    print_success "Created config file at $CONFIG_FILE"
else
    echo -e "${BLUE}Config file already exists at $CONFIG_FILE${NC}"
fi

# Check if bin directory is in PATH (after our auto-fallback)
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    if [[ $EUID -eq 0 ]]; then
        # Root user with symlink
        echo -e "\n${GREEN}✓${NC} Created symlink at /usr/local/bin/tunacode"
    else
        # Non-root user with ~/.profile update
        echo -e "\n${GREEN}✓${NC} Added $BIN_DIR to PATH in ~/.profile"
        echo -e "${YELLOW}Note:${NC} Run ${GREEN}source ~/.profile${NC} or log out and back in to use 'tunacode' command"
    fi
fi

echo -e "\n${GREEN}✨ Installation complete!${NC}"

# Test if we can run tunacode
if command -v tunacode &> /dev/null; then
    echo -e "\n${GREEN}✓${NC} tunacode command is available"
else
    echo -e "\n${YELLOW}!${NC} tunacode command not found in PATH"
    echo -e "   Try running: ${GREEN}$BIN_DIR/tunacode${NC}"
fi

echo ""
echo -e "${BLUE}🔧 Next Steps:${NC}"
echo -e "1. ${BLUE}Configure API keys:${NC} Edit ${GREEN}~/.config/tunacode.json${NC}"
echo -e "   - Add your OpenAI, Anthropic, or other provider API keys"
echo -e "   - Or run ${BLUE}tunacode --setup${NC} for guided configuration"
echo -e ""
echo -e "2. ${BLUE}Get started:${NC}"
echo -e "   - Run ${BLUE}tunacode${NC} to start an interactive session"
echo -e "   - Run ${BLUE}tunacode --help${NC} for all available options"
echo -e ""
echo -e "📖 ${BLUE}Documentation:${NC} Visit the repo for guides and examples"
echo -e "🔑 ${BLUE}API Keys:${NC} You'll need keys from OpenAI, Anthropic, or OpenRouter to use TunaCode"
