"""检查 / 执行 ComfyUI 与前端更新。--check 只读；--apply 需要先关掉出图服务。"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GH_LATEST = "https://api.github.com/repos/comfyanonymous/ComfyUI/releases/latest"
GH_VERSION = "https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master/comfyui_version.py"
PYPI_FRONTEND = "https://pypi.org/pypi/comfyui-frontend-package/json"


def http_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "anima-oneclick"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def http_json(url):
    return json.loads(http_text(url))


def ver_key(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4])


def candidates():
    appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    out = [appdata / "ComfyUI" / "ComfyUI", appdata / "ComfyUI", Path.home() / "ComfyUI"]
    best = None
    for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        p = Path(d + ":\\")
        try:
            if p.exists():
                free = shutil.disk_usage(p).free
                if best is None or free > best[0]:
                    best = (free, p)
        except OSError:
            pass
    if best:
        out.append(best[1] / "AnimaAssets" / "runtime-portable" / "ComfyUI")
    return out


def find_backend(root=None):
    if root:
        p = Path(root)
        return p if p.exists() else None
    for p in candidates():
        if (p / "comfyui_version.py").exists() or (p / "main.py").exists():
            return p
    return None


def local_backend(d):
    f = d / "comfyui_version.py"
    if f.exists():
        m = re.search(r"__version__\s*=\s*[\"']([^\"']+)", f.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return m.group(1)
    try:
        return subprocess.run(["git", "-C", str(d), "describe", "--tags", "--abbrev=0"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def local_python(d):
    for p in (d.parent / "python_embeded" / "python.exe", d.parent / ".venv" / "Scripts" / "python.exe",
              d / ".venv" / "Scripts" / "python.exe"):
        if p.exists():
            return str(p)
    return shutil.which("python") or sys.executable


def frontend_installed(py):
    code = "import importlib.metadata as m;print(m.version('comfyui-frontend-package'))"
    try:
        out = subprocess.run([py, "-c", code], capture_output=True, text=True, timeout=25)
        return out.stdout.strip() or None
    except Exception:
        return None


def frontend_pinned(d):
    f = d / "requirements.txt"
    if f.exists():
        m = re.search(r"comfyui-frontend-package[=~>]+([\d.]+)",
                      f.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return m.group(1)
    return None


def remote_latest():
    backend = None
    try:
        backend = str(http_json(GH_LATEST).get("tag_name", "")).lstrip("vV") or None
    except Exception:
        try:
            m = re.search(r"__version__\s*=\s*[\"']([^\"']+)", http_text(GH_VERSION))
            backend = m.group(1) if m else None
        except Exception:
            pass
    frontend = None
    try:
        frontend = http_json(PYPI_FRONTEND)["info"]["version"]
    except Exception:
        pass
    return backend, frontend


def server_up(url):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=3):
            return True
    except Exception:
        return False


def collect(d, py):
    local_b = local_backend(d)
    latest_b, latest_f = remote_latest()
    f_inst = frontend_installed(py)
    f_pin = frontend_pinned(d)
    return {
        "backend": {
            "path": str(d), "local": local_b, "latest": latest_b,
            "update_available": bool(ver_key(latest_b) > ver_key(local_b)),
        },
        "frontend": {
            "installed": f_inst, "pinned": f_pin, "latest": latest_f,
            "update_available": bool(ver_key(f_pin) > ver_key(f_inst) or ver_key(latest_f) > ver_key(f_inst)),
        },
        "git": (d / ".git").exists(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不修改")
    ap.add_argument("--apply", action="store_true", help="执行更新")
    ap.add_argument("--root", help="ComfyUI 目录（含 main.py）")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    a = ap.parse_args()
    d = find_backend(a.root)
    if not d:
        print(json.dumps({"error": "未找到 ComfyUI 目录，请用 --root 指定"}, ensure_ascii=False))
        return 1
    py = local_python(d)
    if a.apply:
        if server_up(a.server):
            print(json.dumps({"error": "出图服务仍在运行，请先关闭再更新"}, ensure_ascii=False))
            return 3
        if not (d / ".git").exists():
            print(json.dumps({"error": "非 git 安装，请用官方安装器 / 更新包"}, ensure_ascii=False))
            return 2
        before = collect(d, py)
        pull = subprocess.run(["git", "-C", str(d), "pull", "--ff-only"],
                              capture_output=True, text=True, timeout=600)
        pip = subprocess.run([py, "-m", "pip", "install", "-q", "-r", str(d / "requirements.txt")],
                             capture_output=True, text=True, timeout=1800)
        after = collect(d, py)
        print(json.dumps({
            "updated": pull.returncode == 0 and pip.returncode == 0,
            "git_pull": pull.stdout.strip()[-400:] or pull.stderr.strip()[-400:],
            "pip": pip.stderr.strip()[-400:] or "ok",
            "before": before, "after": after,
        }, ensure_ascii=False, indent=2))
        return 0 if pull.returncode == 0 and pip.returncode == 0 else 1
    print(json.dumps(collect(d, py), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
