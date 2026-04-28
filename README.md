<p align="center">
  <a href="https://smartloop.ai">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://github.com/user-attachments/assets/9ced8d4f-3c5d-46e5-a1e8-0b7e9e70e4d9" />
      <source media="(prefers-color-scheme: light)" srcset="https://github.com/user-attachments/assets/c08ace32-92f9-4d50-849e-ee68c4ac1a48" />
      <img width="149" height="28" alt="Smartloop" src="https://github.com/user-attachments/assets/9ced8d4f-3c5d-46e5-a1e8-0b7e9e70e4d9" />
    </picture>
  </a>
</p>
<p align="center">AI orchestration on your device — connect tools, build custom skills, and get things done without sending your data anywhere.</p>
<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/smartloop-ai/smartloop-tui/release.yml"/>
</p>

<img alt="Smartloop TUI Demo" src="demo.gif" />

### Installation

Copy and paste the following script to your terminal to get started:

```bash
curl -fsSL https://smartloop.ai/install | bash
```

Optionally, on macos install using [Homebrew](https://brew.sh):

```bash
brew tap smartloop-ai/smartloop
brew install smartloop
```


> [!TIP]
> To upgrade: `brew update && brew upgrade smartloop`


**From source:**

> [!NOTE]
> Requires Python 3.11. For NVIDIA GPU acceleration on Linux/Windows, install [CUDA 12.4](https://developer.nvidia.com/cuda-12-4-0-download-archive) before proceeding. The build step auto-creates and activates a virtual environment, then detects your GPU backend — Metal on macOS, CUDA on Linux/Windows with NVIDIA.

```bash
git clone https://github.com/smartloop-ai/smartloop.git
cd smartloop
make build   # creates and activates .venv, installs dependencies, and configures GPU backend
make test    # verifies CLI and GPU offload support
```

### Uninstall

```bash
# If installed via curl
curl -fsSL https://smartloop.ai/uninstall | bash
```
If install using homebrew , pase the folllowing in your terminal:

```bash
brew uninstall smartloop
brew untap smartloop-ai/smartloop
```

### Usage

```bash
# View available commands
slp --help

# Initialize the workspace with a different model:
slp init -t <developer_token> --model=<llama3-1b>

# start the tui
slp 
```

> [!TIP]
> You can generate a developer token from the [Console](https://app.smartloop.ai/).


### Service Status

In order ensure that your service is running correctly, type the following command in your terminal:

```bash
slp status
```
This will print details like current GPU being detected, loaded project and context available based on the size of your VRAM or system memeory in case macos based systems

| Property | Value |
|----------|-------|
| Server | http://127.0.0.1:63838 |
| PID | 17320 |
| Model loaded | True |
| Model | gemma3-1b |
| Quantization | Q8_0 |
| Context window | 31232 |
| Flash attention | False |
| Model size | 1020 MB |
| Memory usage | 8% |
| GPU | Apple Silicon (MPS) |
| Active project | Personal (id=71db0b23-6d6d-401a-b04e-cbb64e7e9636) |
| Project model | gemma3-1b |

### Requirements

| Requirement | Description | Required |
|-------------|-------------|----------|
| OS | macOS (Apple Silicon) or Linux (x86_64) or WSL | Yes |
| Python | 3.11+ | Yes |
| CUDA | 12.6+ (NVIDIA GPU acceleration) Metal | No (defaults to CPU) |
| Metal| Bespoke on mac | yes |

### Troubleshooting

#### GPU not detected / Falls back to CPU

If the app falls back to CPU on a GPU-enabled system:

1. **Enable persistence mode:**
   ```bash
   sudo nvidia-smi -pm ENABLED
   ```

2. **Verify GPU detection:**
   ```bash
   nvidia-smi
   ```

If issues persist, ensure NVIDIA drivers are properly installed.

### License

© 2016 Smartloop Inc.

All code is licensed under Apache 2.0. See [LICENSE](LICENSE) file for details.
