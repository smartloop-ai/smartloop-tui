.PHONY: help venv install-sycl install test start build sign notarize archive release clean

VENV := .venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python

# Detect platform: linux, darwin, or windows
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    PLATFORM := linux
else ifeq ($(UNAME_S),Darwin)
    PLATFORM := darwin
else
    PLATFORM := windows
endif

# Detect architecture: arm64 or amd64
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_M),arm64)
    ARCH := arm64
else ifeq ($(UNAME_M),aarch64)
    ARCH := arm64
else
    ARCH := amd64
endif

# Read version from installed smartloop package
VERSION := $(shell $(PYTHON) -c "from smartloop import __version__; print(__version__)" 2>/dev/null)
DIST_DIR := dist/slp
ARCHIVE_NAME := slp.tar.gz

help:
	@echo "Available targets:"
	@echo "  install   - Install dependencies with GPU-accelerated llama-cpp-python"
	@echo "  build     - Build binary with PyInstaller"
	@echo "  sign      - Code sign the binary (macOS only)"
	@echo "  notarize  - Notarize the binary with Apple (macOS only)"
	@echo "  archive   - Create slp.tar.gz from dist/slp"
	@echo "  release   - Full release: build + sign + notarize + archive"
	@echo "  clean     - Clean all build artifacts"

# Detect GPU backend for llama-cpp-python
ifeq ($(PLATFORM),darwin)
    LLAMA_CMAKE_ARGS := -DGGML_METAL=ON
    LLAMA_INSTALL_CMD = CMAKE_ARGS="$(LLAMA_CMAKE_ARGS)" $(PIP) install llama-cpp-python --index-url=https://pypi.org/simple --force-reinstall --no-cache-dir
else ifeq ($(PLATFORM),linux)
    HAS_NVIDIA := $(shell command -v nvidia-smi >/dev/null 2>&1 && echo yes || echo no)
    ifeq ($(HAS_NVIDIA),yes)
        LLAMA_INSTALL_CMD = $(PIP) install llama-cpp-python --prefer-binary --index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --extra-index-url=https://pypi.org/simple --force-reinstall --no-cache-dir
    else
        # No NVIDIA GPU — fall back to CPU-only build
        LLAMA_INSTALL_CMD = $(PIP) install llama-cpp-python --index-url=https://pypi.org/simple --force-reinstall --no-cache-dir
    endif
else ifeq ($(PLATFORM),windows)
    HAS_NVIDIA := $(shell command -v nvidia-smi >/dev/null 2>&1 && echo yes || echo no)
    ifeq ($(HAS_NVIDIA),yes)
        LLAMA_INSTALL_CMD = $(PIP) install llama-cpp-python --prefer-binary --index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --extra-index-url=https://pypi.org/simple --force-reinstall --no-cache-dir
    else
        # No NVIDIA GPU — fall back to CPU-only build
        LLAMA_INSTALL_CMD = $(PIP) install llama-cpp-python --index-url=https://pypi.org/simple --force-reinstall --no-cache-dir
    endif
endif

venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv $(VENV); \
	fi

build: venv
	@echo "=== Installing dependencies ==="
	$(PIP) install -r requirements.txt --index-url=https://pypi.org/simple
	@echo "=== Installing llama-cpp-python ==="
	$(LLAMA_INSTALL_CMD)
	$(PIP) install pyinstaller --index-url=https://pypi.org/simple --force-reinstall --no-cache-dir
	@echo "=== Building binary ==="
	$(PYTHON) -m PyInstaller smartloop.spec
	@echo "Build complete: $(DIST_DIR)/slp"

test:
	@echo "=== Running tests ==="
	@echo "Checking slp --help..."
	@$(PYTHON) main.py --help
	@echo ""
	@echo "Checking llama-cpp-python GPU support..."
	@$(PYTHON) -c "from llama_cpp import llama_cpp; gpu=llama_cpp.llama_supports_gpu_offload(); print('GPU offload:', 'yes' if gpu else 'no (CPU-only)')"
	@echo ""
	@echo "=== Tests passed ==="

clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache
	@rm -rf .ruff_cache
	@rm -rf *.egg-info
	@rm -rf build dist $(ARCHIVE_NAME) slp-notarize.zip
	@rm -rf $(VENV)
	@echo "Cleaned"

build-binary: venv
	@echo "=== Building v$(VERSION) for $(PLATFORM)/$(ARCH) ==="
	@$(PYTHON) -m PyInstaller smartloop.spec
	@echo "Build complete: $(DIST_DIR)/slp"

sign:
ifeq ($(PLATFORM),darwin)
	@echo "=== Signing binary ==="
	@find $(DIST_DIR) -name "*.so" -o -name "*.dylib" | xargs -I {} \
		codesign --force --options runtime \
			--entitlements packaging/macos/entitlements.mac.plist \
			--sign "$(APPLE_DEVELOPER_ID)" {}
	codesign --force --options runtime \
		--entitlements packaging/macos/entitlements.mac.plist \
		--sign "$(APPLE_DEVELOPER_ID)" \
		$(DIST_DIR)/slp
	@echo "Signing complete"
	codesign -v $(DIST_DIR)/slp
else
	@echo "Skipping code signing (not macOS)"
endif

notarize:
ifeq ($(PLATFORM),darwin)
	@echo "=== Notarizing binary ==="
	ditto -c -k --keepParent $(DIST_DIR) slp-notarize.zip
	xcrun notarytool submit slp-notarize.zip \
		--apple-id "$(APPLE_ID)" \
		--password "$(APPLE_APP_PASSWORD)" \
		--team-id "$(APPLE_TEAM_ID)" \
		--wait
	@rm -f slp-notarize.zip
	@echo "Notarization complete"
else
	@echo "Skipping notarization (not macOS)"
endif

archive:
	@echo "=== Creating archive ==="
	tar -czf $(ARCHIVE_NAME) -C dist slp
	@echo "Archive created: $(ARCHIVE_NAME)"

release: build sign notarize archive
	@echo "=== Release v$(VERSION) complete ==="

.DEFAULT_GOAL := help
