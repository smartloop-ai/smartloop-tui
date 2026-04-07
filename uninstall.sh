#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.smartloop"
CACHE_DIR="$HOME/.cache/smartloop"
LEGACY_INSTALL_DIR="$HOME/.slp"
SERVICE_FILE="$HOME/.config/systemd/user/smartloop.service"
LEGACY_SERVICE_FILE="/etc/systemd/system/smartloop.service"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/com.smartloop.server.plist"
LEGACY_LAUNCHD_PLIST="/Library/LaunchDaemons/com.smartloop.server.plist"
LOG_FILE="$HOME/Library/Logs/smartloop.log"
LINUX_LOG_FILE="$HOME/.local/log/smartloop.log"
LEGACY_LOG_FILE="/var/log/smartloop.log"

info()  { printf "\033[1;34m==>\033[0m %s\n" "$1"; }
error() { printf "\033[1;31mError:\033[0m %s\n" "$1" >&2; exit 1; }

uninstall_smartloop() {
    # Stop and disable systemd user service (Linux)
    if [ -f "$SERVICE_FILE" ]; then
        info "Stopping and disabling smartloop user service..."
        systemctl --user stop smartloop   2>/dev/null || true
        systemctl --user disable smartloop 2>/dev/null || true
        rm -f "$SERVICE_FILE"
        systemctl --user daemon-reload
        info "Systemd user service removed"
    fi

    # Remove legacy system-level systemd service if present (Linux)
    if [ -f "$LEGACY_SERVICE_FILE" ]; then
        info "Removing legacy system service..."
        sudo systemctl stop smartloop 2>/dev/null || true
        sudo systemctl disable smartloop 2>/dev/null || true
        sudo rm -f "$LEGACY_SERVICE_FILE"
        sudo systemctl daemon-reload
        info "Legacy systemd service removed"
    fi

    # Unload launchd user agent (macOS)
    if [ -f "$LAUNCHD_PLIST" ]; then
        info "Unloading smartloop launchd user agent..."
        launchctl bootout "gui/$(id -u)" "$LAUNCHD_PLIST" 2>/dev/null || \
            launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
        rm -f "$LAUNCHD_PLIST"
        info "Launchd user agent removed"
    fi

    # Remove legacy system daemon if present (macOS)
    if [ -f "$LEGACY_LAUNCHD_PLIST" ]; then
        info "Removing legacy system daemon..."
        sudo launchctl bootout "system" "$LEGACY_LAUNCHD_PLIST" 2>/dev/null || \
            sudo launchctl unload "$LEGACY_LAUNCHD_PLIST" 2>/dev/null || true
        sudo rm -f "$LEGACY_LAUNCHD_PLIST"
        info "Legacy launchd daemon removed"
    fi

    # Kill any remaining slp processes
    if pkill -f "${INSTALL_DIR}/slp" 2>/dev/null; then
        info "Stopped running slp processes"
        sleep 1
        # Force kill if still running
        pkill -9 -f "${INSTALL_DIR}/slp" 2>/dev/null || true
    fi

    # Remove symlinks
    for link in "$HOME/.local/bin/slp" /usr/local/bin/slp; do
        if [ -L "$link" ]; then
            rm -f "$link"
            info "Removed symlink ${link}"
        fi
    done

    # Remove install directory
    if [ -d "$INSTALL_DIR" ]; then
        info "Removing ${INSTALL_DIR}..."
        rm -rf "$INSTALL_DIR"
    fi

    # Remove cache directory
    if [ -d "$CACHE_DIR" ]; then
        info "Removing cache ${CACHE_DIR}..."
        rm -rf "$CACHE_DIR"
    fi

    # Remove legacy .slp folder
    if [ -d "$LEGACY_INSTALL_DIR" ]; then
        info "Removing legacy ${LEGACY_INSTALL_DIR}..."
        rm -rf "$LEGACY_INSTALL_DIR"
    fi

    # Remove log files
    if [ -f "$LOG_FILE" ]; then
        info "Removing log file ${LOG_FILE}..."
        rm -f "$LOG_FILE"
    fi
    if [ -f "$LINUX_LOG_FILE" ]; then
        info "Removing log file ${LINUX_LOG_FILE}..."
        rm -f "$LINUX_LOG_FILE"
    fi
    if [ -f "$LEGACY_LOG_FILE" ]; then
        info "Removing legacy log file ${LEGACY_LOG_FILE}..."
        sudo rm -f "$LEGACY_LOG_FILE"
    fi

    # Remove PATH entries from shell config files
    local config_files=(
        "$HOME/.bashrc"
        "$HOME/.bash_profile"
        "$HOME/.profile"
        "${ZDOTDIR:-$HOME}/.zshrc"
        "$HOME/.config/fish/config.fish"
    )

    for config_file in "${config_files[@]}"; do
        if [ -f "$config_file" ]; then
            if grep -q "$INSTALL_DIR" "$config_file" 2>/dev/null || grep -q "$LEGACY_INSTALL_DIR" "$config_file" 2>/dev/null; then
                info "Cleaning PATH from ${config_file}..."
                sed -i.bak '/# smartloop/d' "$config_file"
                sed -i.bak "\|${INSTALL_DIR}|d" "$config_file"
                sed -i.bak "\|${LEGACY_INSTALL_DIR}|d" "$config_file"
                rm -f "${config_file}.bak"
            fi
        fi
    done

    printf "\n\033[1;32mSmartloop uninstalled successfully.\033[0m\n"
}

if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    uninstall_smartloop
fi
