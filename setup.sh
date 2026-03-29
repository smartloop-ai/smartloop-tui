#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source dependencies
# shellcheck source=install.sh
source "${SCRIPT_DIR}/install.sh"
# shellcheck source=uninstall.sh
source "${SCRIPT_DIR}/uninstall.sh"

usage() {
    printf "Usage: %s [--uninstall]\n" "$(basename "$0")"
    printf "\n"
    printf "Options:\n"
    printf "  (none)       Install Smartloop (default)\n"
    printf "  --uninstall  Remove Smartloop from this system\n"
    printf "  --help       Show this help message\n"
    exit 0
}

main() {
    local action="install"

    for arg in "$@"; do
        case "$arg" in
            --uninstall) action="uninstall" ;;
            --help|-h)   usage ;;
            *) printf "Unknown option: %s\n" "$arg" >&2; usage ;;
        esac
    done

    if [ "$action" = "uninstall" ]; then
        uninstall_smartloop
    else
        install_smartloop
        printf "\n\033[1;32mSmartloop v%s installed successfully!\033[0m\n" "$VERSION"
        printf "Run \033[1mslp\033[0m to get started.\n"

        if [[ "$(uname -s)" == "Linux" ]]; then
            printf "\n"
            if systemctl --user is-active --quiet smartloop; then
                printf "\033[1;32m✔ smartloop service is running\033[0m\n"
            else
                printf "\033[1;31m✘ smartloop service is NOT running\033[0m\n"
                printf "  Check logs with: journalctl --user -u smartloop -n 50\n"
            fi
        elif [[ "$(uname -s)" == "Darwin" ]]; then
            printf "\n"
            if launchctl list com.smartloop.server 2>/dev/null | grep -q '"PID"'; then
                printf "\033[1;32m✔ smartloop service is running\033[0m\n"
            else
                printf "\033[1;31m✘ smartloop service is NOT running\033[0m\n"
                printf "  Check logs with: tail -50 ~/Library/Logs/smartloop.log\n"
            fi
        fi
    fi
}

main "$@"
