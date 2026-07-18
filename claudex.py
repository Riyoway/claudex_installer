#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable


def ensure_rich() -> None:
    try:
        import rich  # noqa: F401
    except ImportError:
        print("Installing Rich...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])


ensure_rich()

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme({
    "accent": "bold #ff8c00",
    "success": "bold green",
    "error": "bold red",
    "warning": "bold yellow",
    "muted": "dim",
})
console = Console(theme=THEME)


def ok(msg: str) -> None:
    console.print(f"[success]✓[/success] {msg}")


def err(msg: str) -> None:
    console.print(f"[error]✗[/error] {msg}")


def warn(msg: str) -> None:
    console.print(f"[warning]![/warning] {msg}")

GITHUB_REPO = "router-for-me/CLIProxyAPI"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"
USER_AGENT = "Claudex/1.0"
APP_DIR = Path.home() / ".claudex"
CONFIG_FILE = APP_DIR / "config.json"
CURRENT_FILE = APP_DIR / "current.json"
DOWNLOAD_DIR = APP_DIR / "downloads"
VERSIONS_DIR = APP_DIR / "cliproxyapi"
DEFAULT_PORT = 8317
DEFAULT_API_KEY = "sk-local"
LOGO = '''              ,,                           ,,
  .g8"""bgd `7MM                         `7MM
.dP'     `M   MM                           MM
dM'       `   MM   ,6"Yb.`7MM  `7MM   ,M""bMM  .gP"Ya `7M'   `MF'
MM            MM  8)   MM  MM    MM ,AP    MM ,M'   Yb  `VA ,V'
MM.           MM   ,pm9MM  MM    MM 8MI    MM 8M""""""    XMX
`Mb.     ,'   MM  8M   MM  MM    MM `Mb    MM YM.    ,  ,V' VA.
  `"bmmmd'  .JMML.`Moo9^Yo.`Mbod"YML.`Wbmd"MML.`Mbmmd'.AM.   .MA.'''


def gradient_text(art: str, start: str = "#ff8c00", end: str = "#ffffff") -> Text:
    lines = art.split("\n")
    width = max(len(line) for line in lines) or 1
    sr, sg, sb = int(start[1:3], 16), int(start[3:5], 16), int(start[5:7], 16)
    er, eg, eb = int(end[1:3], 16), int(end[3:5], 16), int(end[5:7], 16)
    result = Text()
    for i, line in enumerate(lines):
        for col, ch in enumerate(line):
            t = col / max(width - 1, 1)
            r, g, b = round(sr + (er - sr) * t), round(sg + (eg - sg) * t), round(sb + (eb - sb) * t)
            result.append(ch, style=f"bold #{r:02x}{g:02x}{b:02x}")
        if i < len(lines) - 1:
            result.append("\n")
    return result


class ClaudexError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize_system() -> str:
    value = platform.system().lower()
    mapping = {"windows": "windows", "darwin": "darwin", "linux": "linux", "freebsd": "freebsd"}
    if value not in mapping:
        raise ClaudexError(f"Unsupported operating system: {platform.system()}")
    return mapping[value]


def normalize_arch() -> str:
    value = platform.machine().lower()
    mapping = {
        "x86_64": "amd64", "amd64": "amd64", "x64": "amd64",
        "aarch64": "arm64", "arm64": "arm64", "armv8": "arm64",
        "i386": "386", "i686": "386", "x86": "386",
    }
    if value not in mapping:
        raise ClaudexError(f"Unsupported CPU architecture: {platform.machine()}")
    return mapping[value]


def http_request(url: str, accept: str = "application/vnd.github+json") -> urllib.request.Request:
    headers = {"Accept": accept, "User-Agent": USER_AGENT, "X-GitHub-Api-Version": "2022-11-28"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def http_json(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(http_request(url), timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise ClaudexError("GitHub API rate limit reached. Set GITHUB_TOKEN and retry.") from exc
        raise ClaudexError(f"GitHub API request failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ClaudexError(f"Network request failed: {exc}") from exc


def latest_release() -> dict[str, Any]:
    with console.status("Checking the latest CLIProxyAPI release..."):
        release = http_json(f"{GITHUB_API}/releases/latest")
    if not release.get("tag_name"):
        raise ClaudexError("Latest release has no tag name.")
    return release


def os_tokens(system: str) -> tuple[str, ...]:
    return {"windows": ("windows", "win"), "darwin": ("darwin", "macos", "osx"), "linux": ("linux",), "freebsd": ("freebsd",)}[system]


def arch_tokens(arch: str) -> tuple[str, ...]:
    return {"amd64": ("amd64", "x86_64", "x64"), "arm64": ("arm64", "aarch64"), "386": ("386", "i386", "x86")}[arch]


def select_asset(release: dict[str, Any], system: str, arch: str) -> dict[str, Any]:
    assets = release.get("assets") or []
    matches: list[tuple[int, dict[str, Any]]] = []
    for asset in assets:
        name = str(asset.get("name", ""))
        lower = name.lower()
        if not lower.endswith((".zip", ".tar.gz", ".tgz")):
            continue
        if any(x in lower for x in ("source", "checksum", "sha256")):
            continue
        if not any(token in lower for token in os_tokens(system)):
            continue
        if not any(token in lower for token in arch_tokens(arch)):
            continue
        score = 0
        if lower.startswith("cliproxyapi"): score += 5
        if f"_{system}_" in lower: score += 10
        if f"_{arch}" in lower: score += 10
        if system == "windows" and lower.endswith(".zip"): score += 3
        if system != "windows" and lower.endswith((".tar.gz", ".tgz")): score += 3
        matches.append((score, asset))
    if not matches:
        available = "\n".join(f"  {a.get('name')}" for a in assets)
        raise ClaudexError(f"No release asset matched {system}/{arch}.\nAvailable assets:\n{available}")
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_asset(asset: dict[str, Any], tag: str) -> Path:
    destination_dir = DOWNLOAD_DIR / tag
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / str(asset["name"])
    expected_size = int(asset.get("size") or 0)
    if destination.exists() and (not expected_size or destination.stat().st_size == expected_size):
        ok(f"Using cached download: {destination.name}")
        return destination
    request = http_request(str(asset["browser_download_url"]), "application/octet-stream")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or expected_size or 0)
            with Progress(TextColumn("[accent]{task.description}"), BarColumn(complete_style="accent", finished_style="success"), TaskProgressColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(), console=console) as progress:
                task = progress.add_task(destination.name, total=total or None)
                with destination.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk: break
                        output.write(chunk)
                        progress.update(task, advance=len(chunk))
    except (urllib.error.URLError, OSError) as exc:
        destination.unlink(missing_ok=True)
        raise ClaudexError(f"Download failed: {exc}") from exc
    digest = asset.get("digest")
    if isinstance(digest, str) and digest.lower().startswith("sha256:"):
        expected = digest.split(":", 1)[1].strip().lower()
        with console.status("Verifying SHA-256..."):
            actual = sha256_file(destination)
        if actual != expected:
            destination.unlink(missing_ok=True)
            raise ClaudexError(f"SHA-256 mismatch.\nExpected: {expected}\nActual:   {actual}")
        ok("SHA-256 verified.")
    return destination


def safe_extract_zip(path: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise ClaudexError("Unsafe path detected in ZIP archive.")
        archive.extractall(destination)


def safe_extract_tar(path: Path, destination: Path) -> None:
    root = destination.resolve()
    with tarfile.open(path, "r:*") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise ClaudexError("Unsafe path detected in TAR archive.")
        kwargs = {"filter": "data"} if sys.version_info >= (3, 12) else {}
        archive.extractall(destination, **kwargs)


def find_proxy_executable(directory: Path, system: str) -> Path | None:
    preferred = ("CLIProxyAPI.exe", "cli-proxy-api.exe", "cliproxyapi.exe") if system == "windows" else ("CLIProxyAPI", "cli-proxy-api", "cliproxyapi")
    for name in preferred:
        for path in directory.rglob(name):
            if path.is_file(): return path.resolve()
    for path in directory.rglob("*"):
        if not path.is_file(): continue
        lower = path.name.lower()
        if "cliproxy" not in lower and not ("cli" in lower and "proxy" in lower): continue
        if system == "windows" and path.suffix.lower() != ".exe": continue
        return path.resolve()
    return None


def extract_archive(archive: Path, tag: str, system: str) -> Path:
    destination = VERSIONS_DIR / tag
    temp = VERSIONS_DIR / f".{tag}.extracting"
    if destination.exists():
        existing = find_proxy_executable(destination, system)
        if existing: return existing
        shutil.rmtree(destination)
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir(parents=True, exist_ok=True)
    with console.status(f"Extracting {archive.name}..."):
        if archive.name.lower().endswith(".zip"):
            safe_extract_zip(archive, temp)
        elif archive.name.lower().endswith((".tar.gz", ".tgz")):
            safe_extract_tar(archive, temp)
        else:
            raise ClaudexError(f"Unsupported archive format: {archive.name}")
    temp.replace(destination)
    executable = find_proxy_executable(destination, system)
    if not executable:
        raise ClaudexError("CLIProxyAPI executable was not found after extraction.")
    if system != "windows":
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return executable


def install_or_update(force: bool = False) -> Path:
    system, arch = normalize_system(), normalize_arch()
    release = latest_release()
    tag = str(release["tag_name"])
    current = load_json(CURRENT_FILE)
    current_exe = Path(current.get("executable", ""))
    if not force and current.get("tag") == tag and current.get("system") == system and current.get("arch") == arch and current_exe.exists():
        return current_exe
    asset = select_asset(release, system, arch)
    console.print(Panel(f"Release: [bold]{tag}[/bold]\nPlatform: [bold]{system}/{arch}[/bold]\nAsset: [bold]{asset['name']}[/bold]", title="CLIProxyAPI installation", border_style="accent", box=box.ROUNDED, padding=(1, 2)))
    archive = download_asset(asset, tag)
    executable = extract_archive(archive, tag, system)
    save_json(CURRENT_FILE, {"tag": tag, "system": system, "arch": arch, "asset": asset["name"], "executable": str(executable), "installed_at": int(time.time())})
    config = load_json(CONFIG_FILE)
    config["proxy_exe"] = str(executable)
    save_json(CONFIG_FILE, config)
    return executable


def prompt_manual_path() -> Path:
    system = normalize_system()
    console.print(Panel("Enter the path to a CLIProxyAPI executable, extracted folder, ZIP, or TAR.GZ archive.", title="Manual CLIProxyAPI path", border_style="warning", box=box.ROUNDED, padding=(1, 2)))
    while True:
        raw = Prompt.ask("[accent]Path[/accent]").strip().strip('"')
        path = Path(raw).expanduser()
        if not path.exists():
            err("Path does not exist.")
            continue
        if path.is_dir():
            exe = find_proxy_executable(path, system)
            if exe: return exe
            err("No CLIProxyAPI executable found in that folder.")
            continue
        if path.suffix.lower() == ".exe" or (system != "windows" and os.access(path, os.X_OK)):
            return path.resolve()
        if path.name.lower().endswith((".zip", ".tar.gz", ".tgz")):
            return extract_archive(path.resolve(), f"manual-{int(time.time())}", system)
        err("Unsupported path.")


def resolve_proxy_executable() -> Path:
    config = load_json(CONFIG_FILE)
    configured = config.get("proxy_exe")
    if configured and Path(configured).exists():
        return Path(configured).resolve()
    current = load_json(CURRENT_FILE)
    current_exe = current.get("executable")
    if current_exe and Path(current_exe).exists():
        return Path(current_exe).resolve()
    for directory in (Path.cwd(), Path(__file__).resolve().parent):
        exe = find_proxy_executable(directory, normalize_system())
        if exe:
            config["proxy_exe"] = str(exe)
            save_json(CONFIG_FILE, config)
            return exe
    warn("CLIProxyAPI was not found locally.")
    if Confirm.ask("[accent]Download and install the latest compatible release automatically?[/accent]", default=True):
        return install_or_update()
    exe = prompt_manual_path()
    config["proxy_exe"] = str(exe)
    save_json(CONFIG_FILE, config)
    return exe


def ensure_proxy_config(proxy_exe: Path, port: int, api_key: str) -> Path:
    config_path = APP_DIR / "config.yaml"
    auth_dir = APP_DIR / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text("\n".join(['host: "127.0.0.1"', f"port: {port}", "", f'auth-dir: "{auth_dir.as_posix()}"', "", "api-keys:", f'  - "{api_key}"', ""]), encoding="utf-8")
    return config_path


def is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5): return True
    except OSError: return False


def start_proxy(exe: Path, config_path: Path, port: int) -> None:
    if is_port_open(port): return
    kwargs: dict[str, Any] = {"cwd": str(exe.parent), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([str(exe), "--config", str(config_path)], **kwargs)
    with console.status("Starting CLIProxyAPI..."):
        deadline = time.time() + 20
        while time.time() < deadline:
            if is_port_open(port): return
            time.sleep(0.4)
    raise ClaudexError("CLIProxyAPI failed to start.")


def fetch_models(base_url: str, api_key: str) -> list[str]:
    request = urllib.request.Request(f"{base_url}/v1/models", headers={"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except urllib.error.URLError as exc:
        raise ClaudexError(f"Failed to fetch models: {exc}") from exc
    return sorted({item["id"] for item in payload.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)})


def prepare_runtime() -> tuple[dict[str, Any], Path, Path, list[str]]:
    exe = resolve_proxy_executable()
    config = load_json(CONFIG_FILE)
    port = int(config.get("port", DEFAULT_PORT)); api_key = str(config.get("api_key", DEFAULT_API_KEY))
    base_url = f"http://127.0.0.1:{port}"
    config_path = ensure_proxy_config(exe, port, api_key)
    start_proxy(exe, config_path, port)
    models = fetch_models(base_url, api_key)
    config.update({"proxy_exe": str(exe), "proxy_config": str(config_path), "port": port, "api_key": api_key, "base_url": base_url})
    save_json(CONFIG_FILE, config)
    return config, exe, config_path, models


def text_models(models: Iterable[str]) -> list[str]:
    return [m for m in models if not any(x in m.lower() for x in ("image", "auto-review"))]


def new_table(title: str) -> Table:
    return Table(box=box.ROUNDED, title=title, title_style="accent", header_style="accent", border_style="muted", row_styles=["", "on grey11"])


def assignment_table(assignments: dict[str, str]) -> Table:
    table = new_table("Model assignments")
    table.add_column("Claude alias", style="accent"); table.add_column("CLIProxyAPI model", style="bold")
    for alias in ("opus", "sonnet", "haiku", "subagent"):
        table.add_row(alias.capitalize(), assignments.get(alias, "-"))
    return table


def choose_model(label: str, models: list[str], current: str | None) -> str:
    table = new_table(f"Select {label}")
    table.add_column("#", justify="right", style="accent"); table.add_column("Model", style="bold"); table.add_column("")
    for i, model in enumerate(models, 1): table.add_row(str(i), model, "[success]Current[/success]" if model == current else "")
    console.print(table)
    default = models.index(current) + 1 if current in models else 1
    while True:
        choice = IntPrompt.ask(f"[accent]{label} model[/accent]", default=default)
        if 1 <= choice <= len(models): return models[choice - 1]
        err("Invalid selection.")


def configure_models() -> None:
    config, _, _, models = prepare_runtime()
    available = text_models(models)
    if not available: raise ClaudexError("No text models are available.")
    assignments = dict(config.get("aliases", {}))
    for alias in ("opus", "sonnet", "haiku", "subagent"):
        current = assignments.get(alias) or (assignments.get("sonnet") if alias == "subagent" else None)
        assignments[alias] = choose_model(alias.capitalize(), available, current)
        console.print()
    config["aliases"] = assignments; save_json(CONFIG_FILE, config)
    console.print(assignment_table(assignments))


def install_shell_command() -> None:
    system = normalize_system()
    script = str(Path(__file__).resolve()); python_exe = str(Path(sys.executable).resolve())
    if system == "windows":
        profile = Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        start, end = "# >>> claudex python >>>", "# <<< claudex python <<<"
        current = profile.read_text(encoding="utf-8") if profile.exists() else ""
        current = re.sub(rf"(?s){re.escape(start)}.*?{re.escape(end)}", "", current).rstrip()
        profile.parent.mkdir(parents=True, exist_ok=True)
        block = "\n".join([start, "function global:claudex {", f"    & '{python_exe.replace(chr(39), chr(39)*2)}' '{script.replace(chr(39), chr(39)*2)}' @args", "}", end])
    else:
        shell = Path(os.getenv("SHELL", "")).name
        if shell == "zsh": profile = Path.home() / ".zshrc"
        elif shell == "fish": profile = Path.home() / ".config" / "fish" / "config.fish"
        else: profile = Path.home() / ".bashrc"
        profile.parent.mkdir(parents=True, exist_ok=True)
        current = profile.read_text(encoding="utf-8") if profile.exists() else ""
        start, end = "# >>> claudex python >>>", "# <<< claudex python <<<"
        current = re.sub(rf"(?s){re.escape(start)}.*?{re.escape(end)}", "", current).rstrip()
        if shell == "fish": block = "\n".join([start, "function claudex", f"    '{python_exe}' '{script}' $argv", "end", end])
        else: block = "\n".join([start, f"claudex() {{ '{python_exe}' '{script}' \"$@\"; }}", end])
    profile.write_text(current + "\n\n" + block + "\n", encoding="utf-8")
    console.print(Panel(f"Installed in:\n[bold]{profile}[/bold]\n\nRestart or reload the shell.", title="Shell command", border_style="success", box=box.ROUNDED, padding=(1, 2)))


def codex_login() -> None:
    exe = resolve_proxy_executable(); config = load_json(CONFIG_FILE)
    config_path = ensure_proxy_config(exe, int(config.get("port", DEFAULT_PORT)), str(config.get("api_key", DEFAULT_API_KEY)))
    result = subprocess.run([str(exe), "--config", str(config_path), "--codex-login"])
    if result.returncode != 0: raise ClaudexError("Codex OAuth login failed.")


def launch_claude(extra_args: list[str], explicit_model: str | None = None) -> int:
    config, _, _, models = prepare_runtime(); assignments = dict(config.get("aliases", {}))
    if not all(assignments.get(k) for k in ("opus", "sonnet", "haiku")):
        configure_models(); config = load_json(CONFIG_FILE); assignments = config["aliases"]
    if explicit_model and explicit_model not in models: raise ClaudexError(f"Model is not available: {explicit_model}")
    env = os.environ.copy(); env.update({"ANTHROPIC_BASE_URL": config["base_url"], "ANTHROPIC_AUTH_TOKEN": config["api_key"], "ANTHROPIC_API_KEY": config["api_key"], "ANTHROPIC_DEFAULT_OPUS_MODEL": assignments["opus"], "ANTHROPIC_DEFAULT_SONNET_MODEL": assignments["sonnet"], "ANTHROPIC_DEFAULT_HAIKU_MODEL": assignments["haiku"], "CLAUDE_CODE_SUBAGENT_MODEL": assignments.get("subagent", assignments["sonnet"]), "CLAUDE_CODE_ALWAYS_ENABLE_EFFORT": "1", "CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY": "3", "ENABLE_TOOL_SEARCH": "false"})
    command = ["claude"] + (["--model", explicit_model] if explicit_model else []) + extra_args
    console.print(assignment_table(assignments)); console.print()
    try: return subprocess.call(command, env=env)
    except FileNotFoundError as exc: raise ClaudexError("Claude Code was not found in PATH.") from exc


def show_models() -> None:
    config, _, _, models = prepare_runtime(); assignments = dict(config.get("aliases", {}))
    table = new_table("Available models")
    table.add_column("#", justify="right", style="accent"); table.add_column("Model", style="bold"); table.add_column("Assigned to", style="magenta")
    for i, model in enumerate(models, 1):
        assigned = ", ".join(k.capitalize() for k, v in assignments.items() if v == model)
        table.add_row(str(i), model, assigned)
    console.print(table)


def status() -> None:
    config, current = load_json(CONFIG_FILE), load_json(CURRENT_FILE)
    table = new_table("Claudex status")
    table.add_column("Item", style="accent"); table.add_column("Value", style="bold")
    table.add_row("Platform", f"{normalize_system()}/{normalize_arch()}"); table.add_row("CLIProxyAPI", current.get("tag", "Not installed")); table.add_row("Executable", config.get("proxy_exe", "-")); table.add_row("Base URL", config.get("base_url", "-"))
    console.print(table)
    if config.get("aliases"): console.print(); console.print(assignment_table(config["aliases"]))


def first_run_setup() -> None:
    console.print(Panel("Claudex will detect your OS and CPU, download the latest compatible CLIProxyAPI release, run Codex OAuth, discover models, and configure aliases.", title="Automatic setup", border_style="accent", box=box.ROUNDED, padding=(1, 2)))
    install_or_update(); codex_login(); prepare_runtime(); configure_models(); install_shell_command()
    console.print(Panel("Setup complete. Restart your shell and run [accent]claudex[/accent].", title="Ready", border_style="success", box=box.ROUNDED, padding=(1, 2)))


def main_menu() -> int:
    while True:
        console.clear()
        console.print(gradient_text(LOGO))
        console.print(f"[muted]{normalize_system()} / {normalize_arch()}[/muted]\n")
        menu = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 2, 0, 0))
        menu.add_column(style="accent", width=3, justify="right"); menu.add_column()
        for num, label in ((1,"Launch Claude Code"),(2,"Automatic first-run setup"),(3,"Configure model assignments"),(4,"Show available models"),(5,"Install or update CLIProxyAPI"),(6,"Run Codex OAuth login"),(7,"Install shell command"),(8,"Show status"),(9,"Exit")): menu.add_row(f"{num}", label)
        console.print(Panel(menu, title="Menu", border_style="muted", box=box.ROUNDED, padding=(1, 2)))
        choice = IntPrompt.ask("[accent]Select[/accent]", choices=[str(i) for i in range(1,10)])
        try:
            if choice == 1: return launch_claude([])
            if choice == 2: first_run_setup()
            elif choice == 3: configure_models()
            elif choice == 4: show_models()
            elif choice == 5: install_or_update(force=True)
            elif choice == 6: codex_login()
            elif choice == 7: install_shell_command()
            elif choice == 8: status()
            elif choice == 9: return 0
        except ClaudexError as exc: err(str(exc))
        console.print(); Prompt.ask("[muted]Press Enter to continue[/muted]", default="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="claudex")
    sub = parser.add_subparsers(dest="command")
    for name in ("setup","update","login","configure","models","install-shell","status"): sub.add_parser(name)
    run = sub.add_parser("run"); run.add_argument("--model"); run.add_argument("claude_args", nargs=argparse.REMAINDER)
    args, unknown = parser.parse_known_args()
    if args.command is None:
        args.model = None; args.claude_args = unknown
        if unknown[:1] == ["--model"]:
            if len(unknown) < 2: parser.error("--model requires a value")
            args.model = unknown[1]; args.claude_args = unknown[2:]
    else:
        if not hasattr(args, "model"): args.model = None
        if not hasattr(args, "claude_args"): args.claude_args = []
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.command == "setup": first_run_setup(); return 0
        if args.command == "update": install_or_update(force=True); return 0
        if args.command == "login": codex_login(); return 0
        if args.command == "configure": configure_models(); return 0
        if args.command == "models": show_models(); return 0
        if args.command == "install-shell": install_shell_command(); return 0
        if args.command == "status": status(); return 0
        if args.command == "run": return launch_claude(args.claude_args, args.model)
        if args.model is not None or args.claude_args: return launch_claude(args.claude_args, args.model)
        return main_menu()
    except KeyboardInterrupt:
        console.print(); warn("Cancelled."); return 130
    except ClaudexError as exc:
        err(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
