import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path

from utils.weather import get_weather


ROOT_DIR = Path(__file__).resolve().parent.parent
EXCLUDED_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}
SENSITIVE_FILENAMES = {
    ".env",
    "credentials.json",
    "token.json",
    "token_calendar.json",
}


def _run_readonly_command(args: list[str], timeout: int = 10) -> str:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (completed.stdout or completed.stderr or "").strip()
        return output[:8000]
    except Exception as exc:
        return f"Unavailable: {exc}"


def get_system_snapshot() -> dict:
    """Return read-only local machine health details."""
    total, used, free = shutil.disk_usage(str(ROOT_DIR.anchor or ROOT_DIR))
    boot_time = _run_readonly_command(
        ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"],
        timeout=5,
    )
    services = _run_readonly_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Service | Where-Object {$_.Status -eq 'Stopped'} | "
            "Select-Object -First 12 Name,DisplayName,Status | Format-Table -AutoSize | Out-String",
        ],
        timeout=8,
    )
    recent_errors = _run_readonly_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; StartTime=(Get-Date).AddDays(-1)} "
            "-MaxEvents 8 | Select-Object TimeCreated,ProviderName,Id,Message | "
            "Format-List | Out-String",
        ],
        timeout=12,
    )
    processes = _run_readonly_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 "
            "ProcessName,Id,CPU,WorkingSet64 | Format-Table -AutoSize | Out-String",
        ],
        timeout=8,
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "disk": {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "used_pct": round((used / total) * 100, 1) if total else None,
        },
        "boot_time": boot_time,
        "top_processes": processes,
        "stopped_services_sample": services,
        "recent_system_errors": recent_errors or "No System log errors found in the last 24 hours.",
    }


def scan_project(path: str | None = None) -> dict:
    """Scan a local project without reading sensitive files."""
    root = Path(path or ROOT_DIR).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return {"error": f"Directory not found: {root}"}

    files: list[Path] = []
    todos: list[dict] = []
    counts: dict[str, int] = {}
    total_bytes = 0
    max_files = 1200

    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES]
        for name in names:
            if name in SENSITIVE_FILENAMES:
                continue
            p = Path(current) / name
            try:
                rel = p.relative_to(root)
                suffix = p.suffix.lower() or "[none]"
                counts[suffix] = counts.get(suffix, 0) + 1
                total_bytes += p.stat().st_size
                files.append(rel)
                if len(files) <= max_files and suffix in {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml"}:
                    try:
                        text = p.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        text = ""
                    for line_no, line in enumerate(text.splitlines(), start=1):
                        upper = line.upper()
                        if "TODO" in upper or "FIXME" in upper:
                            todos.append({
                                "file": str(rel).replace("\\", "/"),
                                "line": line_no,
                                "text": line.strip()[:180],
                            })
                            if len(todos) >= 25:
                                break
                if len(files) >= max_files:
                    break
            except Exception:
                continue
        if len(files) >= max_files:
            break

    return {
        "root": str(root),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "file_count_sampled": len(files),
        "estimated_size_mb": round(total_bytes / (1024**2), 2),
        "top_extensions": sorted(counts.items(), key=lambda item: item[1], reverse=True)[:12],
        "todo_count_sampled": len(todos),
        "todos": todos[:25],
        "notable_files": [str(p).replace("\\", "/") for p in files[:80]],
    }


def get_golf_weather(city: str) -> dict:
    """Score current golf conditions from the weather feed."""
    weather = get_weather(city)
    if not weather:
        return {"error": "Weather unavailable."}

    def num(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    temp = num(weather.get("temp_f"))
    feels = num(weather.get("feels_like_f"), temp)
    wind = num(weather.get("wind_mph"))
    humidity = num(weather.get("humidity"))
    uv = num(weather.get("uv_index"))
    desc = (weather.get("description") or "").lower()

    score = 100
    if feels < 45 or feels > 94:
        score -= 28
    elif feels < 55 or feels > 88:
        score -= 15
    if wind > 22:
        score -= 25
    elif wind > 14:
        score -= 12
    if humidity > 82:
        score -= 10
    if uv >= 8:
        score -= 8
    if any(word in desc for word in ["rain", "storm", "thunder", "snow", "sleet"]):
        score -= 35

    score = max(0, min(100, int(score)))
    if score >= 82:
        rating = "Excellent"
    elif score >= 65:
        rating = "Playable"
    elif score >= 45:
        rating = "Marginal"
    else:
        rating = "Skip it"

    notes = []
    if wind > 14:
        notes.append("Wind will affect club selection.")
    if uv >= 8:
        notes.append("High UV. Bring sunscreen and water.")
    if humidity > 82:
        notes.append("Humidity may make the round feel slower.")
    if any(word in desc for word in ["rain", "storm", "thunder"]):
        notes.append("Precipitation or storms are in the current conditions.")
    if not notes:
        notes.append("Conditions look straightforward.")

    return {
        "city": city,
        "score": score,
        "rating": rating,
        "weather": weather,
        "notes": notes,
    }


def build_daily_context(city: str | None = None, project_path: str | None = None) -> dict:
    context = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "system": get_system_snapshot(),
        "project": scan_project(project_path or str(ROOT_DIR)),
    }
    if city:
        context["golf_weather"] = get_golf_weather(city)
    return context


def context_as_json(context: dict) -> str:
    return json.dumps(context, indent=2, default=str)
