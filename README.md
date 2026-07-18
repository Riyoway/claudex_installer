<div align="center">

# Claudex

**Run Claude Code with models exposed through CLIProxyAPI — with automatic setup, model discovery, and a Rich-powered terminal UI.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#requirements)
[![Windows](https://img.shields.io/badge/Windows-supported-0078D6?logo=windows)](#supported-platforms)
[![macOS](https://img.shields.io/badge/macOS-supported-000000?logo=apple)](#supported-platforms)
[![Linux](https://img.shields.io/badge/Linux-supported-FCC624?logo=linux&logoColor=black)](#supported-platforms)
[![CLIProxyAPI](https://img.shields.io/badge/Powered%20by-CLIProxyAPI-orange)](https://github.com/router-for-me/CLIProxyAPI)

</div>

Claudex is an unofficial launcher and setup tool for using [Claude Code](https://docs.anthropic.com/en/docs/claude-code) through [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI).

It detects your operating system and CPU architecture, downloads the correct CLIProxyAPI release, runs Codex OAuth login, discovers available models, and lets you assign them to Claude Code's Opus, Sonnet, Haiku, and subagent slots.

> [!IMPORTANT]
> Claudex is not affiliated with Anthropic, OpenAI, or the CLIProxyAPI project.

## Features

- Rich-powered interactive terminal UI
- Automatic OS and CPU detection
- Automatic download of the latest compatible CLIProxyAPI release
- Windows, macOS, Linux, and FreeBSD support
- amd64, arm64, and x86/386 architecture detection
- Safe ZIP and TAR.GZ extraction
- SHA-256 verification when GitHub release metadata provides a digest
- Automatic CLIProxyAPI configuration and startup
- Codex OAuth login flow
- Automatic model discovery through `/v1/models`
- Custom model assignment for:
  - Opus
  - Sonnet
  - Haiku
  - Subagent
- Direct launch with any available model
- PowerShell, Bash, Zsh, and Fish integration
- Versioned CLIProxyAPI installation under `~/.claudex`

## Requirements

- Python 3.10 or newer
- Claude Code installed and available as `claude` in your `PATH`
- Internet access for the initial setup and updates
- A supported account for the provider you authenticate with

Rich is installed automatically on first launch if it is missing.

## Quick start

Clone the repository:

```bash
git clone https://github.com/riyoway/claudex_installer.git
cd claudex
```

Run the interactive UI:

```bash
python claudex.py
```

On systems where Python is invoked as `python3`:

```bash
python3 claudex.py
```

Choose:

```text
2  Automatic first-run setup
```

The setup process will:

1. Detect your OS and CPU architecture
2. Find the latest CLIProxyAPI release
3. Download the matching archive
4. Verify its SHA-256 digest when available
5. Extract it under `~/.claudex/cliproxyapi`
6. Create the local CLIProxyAPI configuration
7. Start Codex OAuth login
8. Discover available models
9. Ask you to assign models to Claude Code aliases
10. Install the `claudex` shell command

Restart your terminal after setup, then run:

```bash
claudex
```

## Terminal UI

```text
╭────────────────────╮
│ Claudex            │
│ windows / amd64    │
╰────────────────────╯

  1  Launch Claude Code
  2  Automatic first-run setup
  3  Configure model assignments
  4  Show available models
  5  Install or update CLIProxyAPI
  6  Run Codex OAuth login
  7  Install shell command
  8  Show status
  9  Exit
```

## Model assignment

Claude Code exposes three main model aliases plus a separate subagent model. Claudex lets you map any compatible text model returned by CLIProxyAPI to each slot.

Example:

```text
Opus      → gpt-5.6-sol
Sonnet    → gpt-5.6-luna
Haiku     → gpt-5.4-mini
Subagent  → gpt-5.6-terra
```

Image models and auto-review-only models are hidden from the alias selector because they are not normal Claude Code chat models.

To change the assignments later:

```bash
claudex configure
```

To list every model currently exposed by CLIProxyAPI:

```bash
claudex models
```

To launch Claude Code with a specific model without changing the saved aliases:

```bash
claudex --model gpt-5.5
```

Claude Code arguments are forwarded as-is:

```bash
claudex --dangerously-skip-permissions
```

You can also use the explicit `run` subcommand:

```bash
claudex run --model gpt-5.6-terra --dangerously-skip-permissions
```

## Commands

| Command | Description |
|---|---|
| `claudex` | Open the interactive terminal UI |
| `claudex setup` | Run the complete first-run setup |
| `claudex update` | Download and install the latest compatible CLIProxyAPI release |
| `claudex login` | Start Codex OAuth login |
| `claudex configure` | Reassign models to Opus, Sonnet, Haiku, and Subagent |
| `claudex models` | Show available models and current assignments |
| `claudex install-shell` | Install the `claudex` command into the current shell profile |
| `claudex status` | Show the detected platform, CLIProxyAPI version, executable, and endpoint |
| `claudex --model <id>` | Launch Claude Code with a specific available model |

Before installing the shell command, use the Python form:

```bash
python claudex.py setup
python claudex.py models
python claudex.py configure
```

## Supported platforms

Claudex currently recognizes:

| Operating system | Architectures |
|---|---|
| Windows | amd64, arm64, x86/386 |
| macOS | amd64, arm64 |
| Linux | amd64, arm64, x86/386 |
| FreeBSD | Depends on the assets published by CLIProxyAPI |

Actual availability depends on whether the current CLIProxyAPI release contains a matching asset for your OS and CPU.

## Shell integration

Claudex can install a small wrapper into your shell profile.

### PowerShell

```text
~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1
```

### Bash

```text
~/.bashrc
```

### Zsh

```text
~/.zshrc
```

### Fish

```text
~/.config/fish/config.fish
```

Run the installer manually with:

```bash
python claudex.py install-shell
```

Restart the shell or reload its profile afterward.

## Storage layout

Claudex stores its data in:

```text
~/.claudex/
├── auth/                 # CLIProxyAPI OAuth data
├── cliproxyapi/          # Versioned CLIProxyAPI installations
├── downloads/            # Downloaded release archives
├── config.json           # Claudex settings and model assignments
├── config.yaml           # CLIProxyAPI local server configuration
└── current.json          # Currently installed CLIProxyAPI release
```

The local proxy listens on:

```text
http://127.0.0.1:8317
```

The generated configuration binds to `127.0.0.1`, so it is not intentionally exposed to other devices on your network.

## Updating CLIProxyAPI

Use the menu or run:

```bash
claudex update
```

Claudex checks the latest GitHub release, chooses the matching asset for the current OS and CPU, downloads it, and installs it alongside older versions.

Saved model assignments and authentication data are kept separately and are not removed during an update.

## Using an existing CLIProxyAPI installation

When CLIProxyAPI is not found, Claudex asks whether it should download the latest compatible release automatically.

Decline the automatic download to enter a path manually. Supported inputs include:

- A CLIProxyAPI executable
- An extracted CLIProxyAPI directory
- A ZIP archive
- A TAR.GZ or TGZ archive

The selected path is saved in `~/.claudex/config.json`.

## GitHub API rate limits

Claudex uses the public GitHub Releases API. Unauthenticated requests may be rate-limited.

You can provide a GitHub token through the `GITHUB_TOKEN` environment variable:

### PowerShell

```powershell
$env:GITHUB_TOKEN = "github_pat_..."
python .\claudex.py update
```

### Bash / Zsh

```bash
export GITHUB_TOKEN="github_pat_..."
python3 ./claudex.py update
```

The token only needs permission to read public repository metadata.

## Security notes

- Review scripts before running them.
- Claudex downloads CLIProxyAPI only from the official GitHub Releases page for `router-for-me/CLIProxyAPI`.
- Downloaded archives are extracted with path traversal checks.
- SHA-256 is verified when the GitHub release asset provides a digest.
- OAuth credentials remain under your local `~/.claudex/auth` directory.
- Do not expose port `8317` publicly unless you fully understand and secure the configuration.
- `--dangerously-skip-permissions` disables Claude Code permission prompts. Use it only in trusted directories.

## Troubleshooting

### `Claude Code was not found in PATH`

Verify that this works:

```bash
claude --version
```

Install or repair Claude Code before launching it through Claudex.

### CLIProxyAPI cannot start

Check whether another process is already using port `8317`.

PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 8317 -ErrorAction SilentlyContinue
```

Linux/macOS:

```bash
lsof -i :8317
```

### GitHub API rate limit reached

Set `GITHUB_TOKEN` and retry the update or setup command.

### A matching release asset cannot be found

The latest CLIProxyAPI release may not publish a build for your platform. Claudex will print the available asset names to help diagnose the mismatch.

### Models do not appear

Run OAuth login again, restart the proxy, and inspect the model list:

```bash
claudex login
claudex models
```

## Development

Run a syntax check:

```bash
python -m py_compile claudex.py
```

Run without installing the shell wrapper:

```bash
python claudex.py
```

Project structure:

```text
claudex/
├── claudex.py
├── README.md
└── LICENSE
```

## Roadmap

- Automatic Claude Code installation checks and guided setup
- Built-in self-update for Claudex
- Provider selection beyond Codex OAuth
- Model presets such as balanced, fast, and maximum quality
- Better process management and proxy shutdown controls
- Release packaging as standalone executables
- Automated tests across Windows, macOS, and Linux

## License

Choose and add a license before publishing the repository. MIT is a common option for a small open-source utility.

CLIProxyAPI and Claude Code remain subject to their own licenses and terms.

## Acknowledgements

- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
- [Rich](https://github.com/Textualize/rich)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

---

<div align="center">

Made for people who want a simpler way to use CLIProxyAPI with Claude Code.

</div>
