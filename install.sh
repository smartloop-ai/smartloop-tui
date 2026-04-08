#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0.1"
BASE_URL="https://github.com/smartloop-ai/smartloop/releases/download/v${VERSION}"
BASE_DIR="$HOME/.smartloop"
INSTALL_DIR="${BASE_DIR}/${VERSION}"

# Colors
MUTED='\033[0;2m'
PINK='\033[38;5;205m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# SHA256 checksums — fetched from release at install time
CHECKSUMS_FILE=""

# Framework cache directory
CACHE_DIR="${HOME}/.cache/smartloop"

error() { echo -e "${RED}Error:${NC} $1" >&2; exit 1; }

detect_platform() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"

    case "$os" in
        Darwin)          OS="darwin" ;;
        Linux)           OS="linux" ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
        *)               error "Unsupported OS: $os" ;;
    esac

    case "$arch" in
        arm64|aarch64) ARCH="arm64" ;;
        x86_64)        ARCH="amd64" ;;
        *)             error "Unsupported architecture: $arch" ;;
    esac

    if [ "$OS" = "darwin" ] && [ "$ARCH" != "arm64" ]; then
        error "Only Apple Silicon (arm64) is supported on macOS"
    fi

    if [ "$OS" = "linux" ] && [ "$ARCH" != "amd64" ]; then
        error "Only x86_64 (amd64) is supported on Linux"
    fi

    if [ "$OS" = "windows" ] && [ "$ARCH" != "amd64" ]; then
        error "Only x86_64 (amd64) is supported on Windows"
    fi
}

fetch_checksums() {
    local checksums_url="${BASE_URL}/checksums-sha256.txt"
    CHECKSUMS_FILE="$(mktemp)"
    curl -sfL "$checksums_url" -o "$CHECKSUMS_FILE" || error "Failed to download checksums"
}

get_expected_sha256() {
    local filename="$1"
    grep "  ${filename}\$" "$CHECKSUMS_FILE" 2>/dev/null | awk '{print $1}' || true
}

verify_checksum_quiet() {
    local file="$1" expected="$2" actual

    if command -v sha256sum &>/dev/null; then
        actual="$(sha256sum "$file" | awk '{print $1}')"
    elif command -v shasum &>/dev/null; then
        actual="$(shasum -a 256 "$file" | awk '{print $1}')"
    else
        return 1
    fi

    [ "$actual" = "$expected" ]
}

verify_checksum() {
    local file="$1" expected="$2"

    if ! verify_checksum_quiet "$file" "$2"; then
        error "Checksum verification failed."
    fi
}

format_bytes() {
    local n="$1"
    if [ "$n" -ge 1073741824 ]; then
        printf "%.1f GB" "$(echo "scale=1; $n / 1073741824" | bc)"
    elif [ "$n" -ge 1048576 ]; then
        printf "%.1f MB" "$(echo "scale=1; $n / 1048576" | bc)"
    else
        printf "%d KB" "$(( n / 1024 ))"
    fi
}

# progress_bar — adapted from progress-bar.sh by Édouard Lopez
# https://github.com/edouard-lopez/progress-bar.sh — MIT License
progress_bar() {
    local bytes="$1"
    local length="$2"
    local label="${3:-Downloading}"
    [ "$length" -gt 0 ] || return 0

    local columns
    local space_reserved=6

    columns=$(tput cols 2>/dev/null || echo 80)
    local space_available=$(( columns - space_reserved ))
    [ "$space_available" -lt 10 ] && space_available=10

    local percent=$(( bytes * 100 / length ))
    [ "$percent" -gt 100 ] && percent=100

    local filled=$(( percent * space_available / 100 ))

    local bar=""
    local i
    for (( i=0; i<filled; i++ )); do bar+="▇"; done
    for (( i=filled; i<space_available; i++ )); do bar+=" "; done

    local dl_str total_str
    dl_str="$(format_bytes "$bytes")"
    total_str="$(format_bytes "$length")"

    # Two-line display: label on line 1, bar on line 2
    printf "\r\033[K${MUTED}%s  %s / %s${NC}\n\r\033[K%s| %3d%%\033[1A\r" \
        "$label" "$dl_str" "$total_str" "$bar" "$percent"
}

end_progress() {
    # Move cursor past the two-line progress display and restore cursor visibility
    printf "\n\n\033[?25h"
}

download_with_progress() {
    local url="$1"
    local output="$2"
    local label="${3:-Downloading}"
    local length=0
    local bytes=0

    # Get content length
    length=$(curl -sI -L "$url" | grep -i content-length | tail -1 | awk '{print $2}' | tr -d '\r')
    length=${length:-0}

    if [ "$length" -gt 0 ] && [ -t 2 ]; then
        printf "\033[?25l\n"
        curl -sL "$url" -o "$output" --write-out "" 2>/dev/null &
        local curl_pid=$!

        while kill -0 "$curl_pid" 2>/dev/null; do
            if [ -f "$output" ]; then
                bytes=$(wc -c < "$output" 2>/dev/null | tr -d ' ')
                bytes=${bytes:-0}
                progress_bar "$bytes" "$length" "$label"
            fi
            sleep 0.1
        done
        wait "$curl_pid"
        local ret=$?
        progress_bar "$length" "$length" "$label"
        end_progress
        return $ret
    else
        curl -fL --progress-bar "$url" -o "$output"
    fi
}

add_to_path() {
    local config_file="$1"
    local command="$2"

    if grep -Fxq "$command" "$config_file" 2>/dev/null; then
        return 0
    fi

    if [[ -f "$config_file" ]] && [[ -w "$config_file" ]]; then
        echo -e "\n# smartloop" >> "$config_file"
        echo "$command" >> "$config_file"
        echo -e "${MUTED}Added ${NC}slp${MUTED} to \$PATH in ${NC}${config_file}"
    else
        echo -e "${MUTED}Manually add to ${NC}${config_file}${MUTED}:${NC}"
        echo -e "  $command"
    fi
}

setup_path() {
    local current_shell config_files config_file path_command
    current_shell="$(basename "$SHELL")"

    case "$current_shell" in
        fish)
            config_files="$HOME/.config/fish/config.fish"
            path_command="fish_add_path $BASE_DIR"
            ;;
        zsh)
            config_files="${ZDOTDIR:-$HOME}/.zshrc"
            path_command="export PATH=\"${BASE_DIR}:\$PATH\""
            ;;
        bash)
            config_files="$HOME/.bashrc $HOME/.bash_profile $HOME/.profile"
            path_command="export PATH=\"${BASE_DIR}:\$PATH\""
            ;;
        *)
            config_files="$HOME/.bashrc $HOME/.profile"
            path_command="export PATH=\"${BASE_DIR}:\$PATH\""
            ;;
    esac

    # Find the first existing config file for the detected shell
    config_file=""
    for f in $config_files; do
        if [[ -f "$f" ]]; then
            config_file="$f"
            break
        fi
    done

    if [[ -z "$config_file" ]]; then
        echo -e "${MUTED}No config file found for ${NC}${current_shell}${MUTED}. Manually add to your shell config:${NC}"
        echo -e "  $path_command"
        return 0
    fi

    add_to_path "$config_file" "$path_command"

    # Make slp available in the current session immediately
    export PATH="${BASE_DIR}:$PATH"
}

print_banner() {
    echo -e ""
    echo -e "${PINK}█▀ █▀▄▀█ ▄▀█ █▀█ ▀█▀ █   █▀█ █▀█ █▀█${NC}"
    echo -e "${PINK}▄█ █ ▀ █ █▀█ █▀▄  █  █▄▄ █▄█ █▄█ █▀▀${NC}"
    echo -e ""
    echo -e "${MUTED}Version: ${NC}${VERSION}"
    echo -e ""
    echo -e "${MUTED}To get started:${NC}"
    echo -e ""
    echo -e "  slp  ${MUTED}# Start the TUI${NC}"
    echo -e "  slp status  ${MUTED}# Check if the server is running${NC}"
    echo -e ""
    echo -e "${MUTED}For more information visit ${NC}https://smartloop.ai/docs/intro/"
    echo -e ""
}

download_archive() {
    mkdir -p "$CACHE_DIR"

    if [ "$OS" = "windows" ]; then
        CACHED_ARCHIVE="${CACHE_DIR}/slp-${VERSION}-${OS}-${ARCH}.zip"
    else
        CACHED_ARCHIVE="${CACHE_DIR}/slp-${VERSION}-${OS}-${ARCH}.tar.gz"
    fi

    # Use cached archive if it exists and checksum matches
    if [ -f "$CACHED_ARCHIVE" ]; then
        local archive_name="${OS}-${ARCH}-slp.tar.gz"
        [ "$OS" = "windows" ] && archive_name="${OS}-${ARCH}-slp.zip"
        local expected_sha256
        expected_sha256="$(get_expected_sha256 "$archive_name")"

        if [ -z "$expected_sha256" ] || verify_checksum_quiet "$CACHED_ARCHIVE" "$expected_sha256"; then
            echo -e "${MUTED}Hit:1 ${CACHE_DIR} smartloop ${VERSION}${NC}"
            return 0
        fi
    fi

    if [ "$OS" = "darwin" ]; then
        local archive_name="darwin-${ARCH}-slp.tar.gz"

        download_with_progress "${BASE_URL}/${archive_name}" "$CACHED_ARCHIVE" "Get:1 smartloop ${VERSION}"

        local expected_sha256
        expected_sha256="$(get_expected_sha256 "$archive_name")"
        if [ -n "$expected_sha256" ]; then
            verify_checksum "$CACHED_ARCHIVE" "$expected_sha256"
        fi

    elif [ "$OS" = "linux" ]; then
        # Linux archive is split into parts (GitHub Releases 2GB limit)
        local parts_dir
        parts_dir="$(mktemp -d)"
        local part_prefix="linux-${ARCH}-slp.tar.gz.part-"
        local dl_label="Get:1 smartloop ${VERSION}"

        # Discover available parts and compute total size
        local available_parts=()
        local total_size=0
        for suffix in aa ab ac ad ae af ag ah; do
            local part_url="${BASE_URL}/${part_prefix}${suffix}"
            if curl -sfI -L "$part_url" >/dev/null 2>&1; then
                available_parts+=("$suffix")
                local part_len
                part_len=$(curl -sI -L "$part_url" | grep -i content-length | tail -1 | awk '{print $2}' | tr -d '\r')
                total_size=$(( total_size + ${part_len:-0} ))
            else
                break
            fi
        done

        # Download all parts with a single combined progress bar
        local downloaded_so_far=0
        printf "\033[?25l\n"
        for suffix in "${available_parts[@]}"; do
            local part_url="${BASE_URL}/${part_prefix}${suffix}"
            local part_file="${parts_dir}/${part_prefix}${suffix}"
            local expected_part_sha256
            expected_part_sha256="$(get_expected_sha256 "${part_prefix}${suffix}")"

            curl -sL "$part_url" -o "$part_file" &
            local curl_pid=$!

            while kill -0 "$curl_pid" 2>/dev/null; do
                if [ -f "$part_file" ]; then
                    local current_bytes
                    current_bytes=$(wc -c < "$part_file" 2>/dev/null | tr -d ' ')
                    current_bytes=${current_bytes:-0}
                    progress_bar $(( downloaded_so_far + current_bytes )) "$total_size" "$dl_label"
                fi
                sleep 0.1
            done
            wait "$curl_pid" || error "Failed to download part ${suffix}"

            local part_size
            part_size=$(wc -c < "$part_file" | tr -d ' ')
            downloaded_so_far=$(( downloaded_so_far + part_size ))
            progress_bar "$downloaded_so_far" "$total_size" "$dl_label"

            if [ -n "$expected_part_sha256" ]; then
                verify_checksum "$part_file" "$expected_part_sha256"
            fi
        done
        progress_bar "$total_size" "$total_size" "$dl_label"
        end_progress

        cat "${parts_dir}/${part_prefix}"* > "$CACHED_ARCHIVE"
        rm -rf "$parts_dir"

    elif [ "$OS" = "windows" ]; then
        local archive_name="windows-${ARCH}-slp.zip"

        download_with_progress "${BASE_URL}/${archive_name}" "$CACHED_ARCHIVE" "Get:1 smartloop ${VERSION}"

        local expected_sha256
        expected_sha256="$(get_expected_sha256 "$archive_name")"
        if [ -n "$expected_sha256" ]; then
            verify_checksum "$CACHED_ARCHIVE" "$expected_sha256"
        fi
    fi
}

extract_archive() {
    local tmpdir="$1"
    echo -e "${MUTED}Unpacking smartloop (${VERSION}) ...${NC}"
    if [ "$OS" = "windows" ]; then
        unzip -qo "$CACHED_ARCHIVE" -d "$tmpdir"
    else
        tar -xzf "$CACHED_ARCHIVE" -C "$tmpdir"
    fi
}

bootstrap_model() {
    local port_file="${BASE_DIR}/server.port"
    local port=8000

    if [ -f "$port_file" ]; then
        port="$(cat "$port_file")"
    fi

    local base="http://127.0.0.1:${port}"
    local bootstrap_url="${base}/v1/bootstrap"

    # Wait for the server to be healthy before calling bootstrap
    echo -e "${MUTED}Waiting for smartloop to start ...${NC}"
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if curl -sf "${base}/health" >/dev/null 2>&1; then
            break
        fi
        # Re-read port file in case it was written after service start
        if [ -f "$port_file" ]; then
            port="$(cat "$port_file")"
            base="http://127.0.0.1:${port}"
            bootstrap_url="${base}/v1/bootstrap"
        fi
        sleep 1
        attempts=$((attempts + 1))
    done

    if [ $attempts -ge 30 ]; then
        echo -e "${RED}Server did not become healthy in time.${NC}"
        return 1
    fi

    echo -e "${MUTED}Fetching model for smartloop (${VERSION}) ...${NC}"

    # Stream SSE events from the bootstrap endpoint
    local showing_progress=false
    local line event_type=""

    printf "\033[?25l\n"

    curl -sN -X POST "$bootstrap_url" 2>/dev/null | while IFS= read -r line; do
        # Strip carriage return
        line="${line%$'\r'}"

        # Parse SSE event type
        if [[ "$line" == event:* ]]; then
            event_type="${line#event:}"
            event_type="${event_type# }"
            continue
        fi

        # Skip non-data lines
        if [[ "$line" != data:* ]]; then
            [ -z "$line" ] && event_type=""
            continue
        fi

        local data="${line#data:}"
        data="${data# }"

        # Extract JSON fields using lightweight parsing
        local downloaded total filename status message
        downloaded="$(echo "$data" | sed -n 's/.*"downloaded"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')"
        total="$(echo "$data" | sed -n 's/.*"total"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')"
        filename="$(echo "$data" | sed -n 's/.*"filename"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
        status="$(echo "$data" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
        message="$(echo "$data" | sed -n 's/.*"message"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

        # Progress event — download bytes
        if [ -n "$downloaded" ] && [ -n "$total" ] && [ "$total" -gt 0 ] 2>/dev/null; then
            showing_progress=true
            local friendly_name="${filename:-model}"
            progress_bar "$downloaded" "$total" "Downloading ${friendly_name}"

        # Complete event
        elif [ "$event_type" = "complete" ] || [ "$status" = "completed" ]; then
            if $showing_progress; then
                end_progress
                showing_progress=false
            fi

        # Error event
        elif [ "$event_type" = "error" ] || [ "$status" = "error" ]; then
            if $showing_progress; then
                end_progress
                showing_progress=false
            fi
            [ -n "$message" ] && echo -e "${RED}${message}${NC}"

        # Status messages (skip "Downloading..." since bar shows it)
        elif [ -n "$message" ]; then
            case "$message" in
                [Dd]ownloading*) ;;
                *)
                    if $showing_progress; then
                        end_progress
                        showing_progress=false
                    fi
                    echo -e "${MUTED}${message}${NC}"
                    ;;
            esac
        fi

        event_type=""
    done

    printf "\033[?25h"
}

install_smartloop() {
    echo -e "${MUTED}Reading package lists...${NC} "
    detect_platform
    echo -e "${MUTED}Reading package lists... Done${NC}"

    # Skip download + extract if this version is already installed
    local slp_existing="${INSTALL_DIR}/slp"
    [ "$OS" = "windows" ] && slp_existing="${INSTALL_DIR}/slp.exe"

    if [ -x "$slp_existing" ]; then
        echo -e "${MUTED}smartloop is already the newest version (${VERSION}).${NC}"
    else
        echo -e "${MUTED}The following NEW packages will be installed:${NC}"
        echo -e "  ${BOLD}smartloop${NC}"

        fetch_checksums

        download_archive

        local tmpdir
        tmpdir="$(mktemp -d)"
        trap 'rm -rf "${tmpdir:-}" "${CHECKSUMS_FILE:-}"' EXIT

        echo -e "${MUTED}Selecting previously unselected package smartloop.${NC}"

        extract_archive "$tmpdir"

        echo -e "${MUTED}Setting up smartloop (${VERSION}) ...${NC}"
        mkdir -p "$INSTALL_DIR"
        rm -rf "${INSTALL_DIR:?}/"*
        cp -r "${tmpdir}/slp/"* "$INSTALL_DIR/"
    fi

    # Track installed version
    local versions_file="${BASE_DIR}/version"
    echo "$VERSION" > "$versions_file"

    # Record in installed versions list
    local installed_file="${BASE_DIR}/installed"
    if [ ! -f "$installed_file" ] || ! grep -qx "$VERSION" "$installed_file"; then
        echo "$VERSION" >> "$installed_file"
    fi

    local slp_bin="${INSTALL_DIR}/slp"
    [ "$OS" = "windows" ] && slp_bin="${INSTALL_DIR}/slp.exe"

    if ! "$slp_bin" --help &>/dev/null; then
        error "Installation verification failed: 'slp --help' did not succeed"
    fi

    if [ "$OS" = "windows" ]; then
        echo ""
        echo -e "${GREEN}Add the following to your PATH:${NC}"
        echo -e "  ${BOLD}${BASE_DIR}${NC}"
        echo ""
    else
        setup_path

        # Symlink slp binary to base dir for PATH consistency
        ln -sf "${slp_bin}" "${BASE_DIR}/slp"

        if [ -d "$HOME/.local/bin" ] && [ -w "$HOME/.local/bin" ]; then
            ln -sf "${BASE_DIR}/slp" "$HOME/.local/bin/slp" 2>/dev/null || true
        elif [ -w /usr/local/bin ]; then
            ln -sf "${BASE_DIR}/slp" /usr/local/bin/slp 2>/dev/null || true
        else
            mkdir -p "$HOME/.local/bin"
            ln -sf "${BASE_DIR}/slp" "$HOME/.local/bin/slp" 2>/dev/null || true
            echo ""
            echo -e "${GREEN}To use slp immediately, add to your shell config:${NC}"
            echo -e "  ${BOLD}fish_add_path -g $HOME/.local/bin${NC}  # fish"
            echo -e "  ${BOLD}export PATH=\"$HOME/.local/bin:\$PATH\"${NC}  # bash/zsh"
            echo ""
        fi
    fi

    echo -e "${MUTED}Processing triggers for smartloop (${VERSION}) ...${NC}"
    if [ "$OS" = "linux" ]; then
        setup_systemd_service
    elif [ "$OS" = "darwin" ]; then
        setup_launchd_service
    fi

    # Bootstrap the model via the SSE API so we can show download progress
    bootstrap_model

    print_banner
}


setup_launchd_service() {
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist="${plist_dir}/com.smartloop.server.plist"
    local log_dir="$HOME/Library/Logs"
    local log_file="${log_dir}/smartloop.log"

    # Remove legacy system-level daemon if present
    local legacy_plist="/Library/LaunchDaemons/com.smartloop.server.plist"
    if [ -f "$legacy_plist" ]; then
        sudo launchctl unload "$legacy_plist" 2>/dev/null || true
        sudo rm -f "$legacy_plist"
    fi

    mkdir -p "$plist_dir" "$log_dir"

    cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smartloop.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>${BASE_DIR}/slp</string>
        <string>server</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${BASE_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${log_file}</string>
    <key>StandardErrorPath</key>
    <string>${log_file}</string>
</dict>
</plist>
EOF

    local domain="gui/$(id -u)"
    local service_target="${domain}/com.smartloop.server"

    # Fully stop and remove any existing service before loading the new plist.
    # Try the modern API first, fall back to legacy, and wait for clean teardown.
    if launchctl print "$service_target" &>/dev/null; then
        launchctl bootout "$service_target" 2>/dev/null || \
            launchctl unload "$plist" 2>/dev/null || true
        sleep 1
    fi

    # Remove quarantine attributes that can cause launchctl I/O errors
    xattr -dr com.apple.quarantine "$plist" 2>/dev/null || true
    xattr -dr com.apple.quarantine "${BASE_DIR}/slp" 2>/dev/null || true

    # Load the service with retry — transient I/O errors can occur right after
    # bootout or when the binary was just extracted.
    local attempts=0
    local max_attempts=3
    while [ $attempts -lt $max_attempts ]; do
        if launchctl bootstrap "$domain" "$plist" 2>/dev/null; then
            break
        fi
        attempts=$((attempts + 1))
        if [ $attempts -lt $max_attempts ]; then
            sleep 1
        fi
    done

    # If bootstrap never succeeded, try the legacy load as a last resort
    if ! launchctl print "$service_target" &>/dev/null; then
        launchctl load -w "$plist" 2>/dev/null || true
    fi

    # Verify the service is running (give it a moment to start)
    sleep 1
    if ! launchctl list com.smartloop.server 2>/dev/null | grep -q '"PID"'; then
        echo -e "${RED}Service failed to start.${NC} Check logs with: tail -50 ${log_file}"
    fi
}

setup_systemd_service() {
    local service_dir="$HOME/.config/systemd/user"
    local service_file="${service_dir}/smartloop.service"
    local log_dir="$HOME/.local/log"
    local log_file="${log_dir}/smartloop.log"

    # Remove legacy system-level service if present
    local legacy_service="/etc/systemd/system/smartloop.service"
    if [ -f "$legacy_service" ]; then
        sudo systemctl stop smartloop 2>/dev/null || true
        sudo systemctl disable smartloop 2>/dev/null || true
        sudo rm -f "$legacy_service"
        sudo systemctl daemon-reload
    fi

    mkdir -p "$service_dir" "$log_dir"

    cat > "$service_file" <<EOF
[Unit]
Description=Smartloop Server
After=network.target

[Service]
Type=simple
ExecStart=${BASE_DIR}/slp server start
Restart=on-failure
RestartSec=5
WorkingDirectory=${BASE_DIR}
StandardOutput=append:${log_file}
StandardError=append:${log_file}

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable smartloop
    systemctl --user restart smartloop

    # Enable lingering so the user service starts at boot without login
    loginctl enable-linger "$(whoami)" 2>/dev/null || true

    if ! systemctl --user is-active --quiet smartloop; then
        echo -e "${RED}Service failed to start.${NC} Check logs with: journalctl --user -u smartloop -n 50"
    fi
}

if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    install_smartloop
fi
