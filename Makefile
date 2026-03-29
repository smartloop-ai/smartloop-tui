.PHONY: help build sign notarize archive release clean

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
VERSION := $(shell python3 -c "from smartloop import __version__; print(__version__)")
DIST_DIR := dist/slp
ARCHIVE_NAME := slp.tar.gz

help:
	@echo "Available targets:"
	@echo "  build     - Build binary with PyInstaller"
	@echo "  sign      - Code sign the binary (macOS only)"
	@echo "  notarize  - Notarize the binary with Apple (macOS only)"
	@echo "  archive   - Create slp.tar.gz from dist/slp"
	@echo "  release   - Full release: build + sign + notarize + archive"
	@echo "  clean     - Clean all build artifacts"

clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache
	@rm -rf .ruff_cache
	@rm -rf *.egg-info
	@rm -rf build dist $(ARCHIVE_NAME) slp-notarize.zip
	@echo "Cleaned"

build:
	@echo "=== Building v$(VERSION) for $(PLATFORM)/$(ARCH) ==="
	pyinstaller smartloop.spec
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
