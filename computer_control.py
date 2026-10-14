"""Explicitly constrained Windows actions for the Jarvis web interface."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import webbrowser
from urllib.parse import urlsplit

ALLOWED_APPS = {
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
}
ALLOWED_FOLDERS = {"desktop", "documents", "downloads"}
WORKSPACE = Path.home() / "Documents" / "Jarvis"
MAX_FILE_CONTENT_LENGTH = 20_000


def _make_action(kind: str, **values: str | int | bool) -> dict[str, object]:
    return {"kind": kind, **values}


def prepare_action(prompt: str) -> dict[str, object] | None:
    """Recognize only the small, documented set of computer actions."""
    text = " ".join(prompt.strip().split())
    text = re.sub(r"^(?:hey\s+)?jarvis[, ]+\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    app_match = re.fullmatch(
        r"(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?"
        r"(calculator|calc|notepad|paint|mspaint|file explorer|explorer)[?!]?",
        text,
        re.IGNORECASE,
    )
    if app_match:
        alias = app_match.group(1).lower()
        app = {
            "calc": "calculator",
            "mspaint": "paint",
            "explorer": "file explorer",
        }.get(alias, alias)
        return _make_action("launch_app", app=app)

    folder_match = re.fullmatch(
        r"(?:please\s+)?open\s+(?:my\s+)?"
        r"(desktop|documents|downloads)(?:\s+folder)?[?!]?",
        text,
        re.IGNORECASE,
    )
    if folder_match:
        return _make_action("open_folder", folder=folder_match.group(1).lower())

    url_match = re.fullmatch(
        r"(?:please\s+)?(?:open|visit|go to)\s+(.+)", text, re.IGNORECASE
    )
    if url_match:
        target = url_match.group(1).strip().rstrip(".,!?")
        if re.fullmatch(r"(?:https?://)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/\S*)?", target):
            url = target if "://" in target else f"https://{target}"
            parsed = urlsplit(url)
            if parsed.scheme in {"http", "https"} and parsed.hostname:
                return _make_action("open_url", url=url)

    file_match = re.fullmatch(
        r"(?:please\s+)?(?:create|write|save|edit)\s+(?:a\s+)?"
        r"(?:text\s+)?(?:file|note)\s+(?:named|called)\s+"
        r"([A-Za-z0-9 _.-]+?)(?:\s+(?:containing|that says|with text)\s+(.+))?",
        text,
        re.IGNORECASE,
    )
    if file_match:
        filename = file_match.group(1).strip().rstrip(". ")
        if not Path(filename).suffix:
            filename += ".txt"
        if Path(filename).suffix.lower() not in {".txt", ".md"}:
            return None
        content = file_match.group(2) or ""
        if len(content) > MAX_FILE_CONTENT_LENGTH:
            raise ValueError(
                f"Jarvis workspace text files are limited to "
                f"{MAX_FILE_CONTENT_LENGTH} characters."
            )
        path = WORKSPACE / filename
        return _make_action(
            "write_file",
            filename=filename,
            content=content,
            overwrite=path.exists(),
        )

    setting_match = re.fullmatch(
        r"(?:please\s+)?(?:set|change)\s+(?:the\s+)?"
        r"(volume|brightness)\s+to\s+(\d{1,3})\s*%?[?!]?",
        text,
        re.IGNORECASE,
    )
    if setting_match:
        name = setting_match.group(1).lower()
        value = int(setting_match.group(2))
        if not 0 <= value <= 100:
            raise ValueError(f"{name.title()} must be between 0 and 100.")
        return _make_action(f"set_{name}", value=value)

    return None


def validate_action(action: object) -> dict[str, object]:
    """Validate an action again at execution time; never accept commands."""
    if not isinstance(action, dict) or not isinstance(action.get("kind"), str):
        raise ValueError("Invalid computer action.")
    kind = action["kind"]
    if kind == "launch_app":
        app = action.get("app")
        if not isinstance(app, str) or app not in ALLOWED_APPS:
            raise ValueError("That app is not on Jarvis's allowed-app list.")
        return {"kind": kind, "app": app}
    if kind == "open_folder":
        folder = action.get("folder")
        if not isinstance(folder, str) or folder not in ALLOWED_FOLDERS:
            raise ValueError("Jarvis can only open Desktop, Documents, or Downloads.")
        return {"kind": kind, "folder": folder}
    if kind == "open_url":
        url = action.get("url")
        if not isinstance(url, str) or len(url) > 2048:
            raise ValueError("Invalid web address.")
        try:
            parsed = urlsplit(url)
        except ValueError as exc:
            raise ValueError("Invalid web address.") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Only normal HTTP or HTTPS web addresses are allowed.")
        return {"kind": kind, "url": url}
    if kind == "write_file":
        filename = action.get("filename")
        content = action.get("content")
        overwrite = action.get("overwrite")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or Path(filename).suffix.lower() not in {".txt", ".md"}
            or not isinstance(content, str)
            or len(content) > MAX_FILE_CONTENT_LENGTH
            or not isinstance(overwrite, bool)
        ):
            raise ValueError("Only short .txt and .md files in the Jarvis workspace are allowed.")
        return {
            "kind": kind,
            "filename": filename,
            "content": content,
            "overwrite": overwrite,
        }
    if kind in {"set_volume", "set_brightness"}:
        value = action.get("value")
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError("The setting must be a whole number from 0 to 100.")
        return {"kind": kind, "value": value}
    raise ValueError("That computer action is not supported.")


def execute_action(action: object) -> str:
    """Perform one validated action after the browser obtains user approval."""
    approved = validate_action(action)
    kind = approved["kind"]
    if kind == "launch_app":
        app = str(approved["app"])
        executable = ALLOWED_APPS[app]
        subprocess.Popen([executable], shell=False)
        return f"Opened {app}."
    if kind == "open_folder":
        folder = str(approved["folder"])
        path = Path.home() / folder.title()
        if not path.is_dir():
            raise FileNotFoundError(f"Your {folder} folder was not found.")
        subprocess.Popen(["explorer.exe", str(path)], shell=False)
        return f"Opened your {folder} folder."
    if kind == "open_url":
        url = str(approved["url"])
        if not webbrowser.open(url, new=2):
            raise OSError("The default browser did not open the requested page.")
        return "Opened the web address in your browser."
    if kind == "write_file":
        filename = str(approved["filename"])
        content = str(approved["content"])
        target = WORKSPACE / filename
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        mode = "w" if approved["overwrite"] else "x"
        try:
            with target.open(mode, encoding="utf-8", newline="\n") as output:
                output.write(content)
        except FileExistsError as exc:
            raise ValueError(
                "That file now exists. Ask Jarvis to prepare the action again "
                "so the overwrite can be reviewed."
            ) from exc
        return f"Saved {filename} in the Jarvis workspace."
    if kind == "set_volume":
        try:
            from comtypes import CLSCTX_ALL, COMError
            from ctypes import POINTER, cast
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        except ImportError as exc:
            raise RuntimeError(
                "Volume control is unavailable. Install the optional Windows "
                "computer-control dependencies with `pip install -r requirements.txt`."
            ) from exc
        try:
            speakers = AudioUtilities.GetSpeakers()
            if hasattr(speakers, "EndpointVolume"):
                volume = speakers.EndpointVolume
            else:
                interface = speakers.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
                volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(int(approved["value"]) / 100, None)
        except COMError as exc:
            raise OSError(f"Could not adjust system volume: {exc}") from exc
        return f"Set system volume to {approved['value']}%."
    if kind == "set_brightness":
        level = int(approved["value"])
        script = (
            "$monitors = Get-CimInstance -Namespace root/WMI "
            "-ClassName WmiMonitorBrightnessMethods; "
            "if (-not $monitors) { throw 'No adjustable display found.' }; "
            f"foreach ($monitor in $monitors) {{ "
            f"Invoke-CimMethod -InputObject $monitor -MethodName WmiSetBrightness "
            f"-Arguments @{{Timeout=1; Brightness={level}}} | Out-Null }}"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("Windows took too long to adjust display brightness.") from exc
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise OSError(detail or "Windows could not adjust display brightness.")
        return f"Set brightness to {level}% on supported displays."
    raise ValueError("That computer action is not supported.")


def action_summary(action: object) -> str:
    approved = validate_action(action)
    kind = approved["kind"]
    if kind == "launch_app":
        return f"Open {approved['app']}"
    if kind == "open_folder":
        return f"Open your {approved['folder']} folder"
    if kind == "open_url":
        return f"Open {approved['url']}"
    if kind == "write_file":
        verb = "Replace" if approved["overwrite"] else "Create"
        return f"{verb} {approved['filename']} in Documents\\Jarvis"
    if kind == "set_volume":
        return f"Set system volume to {approved['value']}%"
    if kind == "set_brightness":
        return f"Set brightness to {approved['value']}% on supported displays"
    raise ValueError("That computer action is not supported.")
