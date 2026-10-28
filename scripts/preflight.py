# -*- coding: utf-8 -*-
"""部署前环境预检：采集显卡、内存、磁盘、端口与 Python 版本，并给出可运行档位。

仅使用 Python 标准库。预检结果本身不代表失败，退出码固定为 0。
"""

import argparse
import ctypes
import json
import os
import platform
import shutil
import socket
import string
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COMFY_PORT = 8188


class _MEMORYSTATUSEX(ctypes.Structure):
    """Windows GlobalMemoryStatusEx 所需结构体。"""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def find_nvidia_smi():
    """优先从 PATH 查找 nvidia-smi，失败时再试常见安装位置。"""
    exe = shutil.which("nvidia-smi")
    if exe:
        return exe
    candidates = (
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "NVIDIA Corporation"
        / "NVSMI"
        / "nvidia-smi.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def probe_gpu():
    """读取第一张 NVIDIA 显卡的型号、显存与驱动版本；不可用时返回 None。"""
    exe = find_nvidia_smi()
    if not exe:
        return None
    command = [
        exe,
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ]
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0 or not lines:
        return None
    # 显卡名称本身可能带逗号，因此从右侧切分容量与驱动
    parts = [part.strip() for part in lines[0].rsplit(",", 2)]
    if len(parts) != 3:
        return None
    name, total_mib, driver = parts
    try:
        vram_gb = round(float(total_mib) / 1024.0, 1)
    except ValueError:
        return None
    return {"name": name, "vram_gb": vram_gb, "driver": driver}


def probe_ram_gb():
    """通过 GlobalMemoryStatusEx 读取物理内存总量（GB）。"""
    try:
        status = _MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return round(status.ullTotalPhys / 1024 ** 3, 1)
    except (AttributeError, OSError):
        return None


def probe_disks():
    """遍历 A-Z 中真实存在的盘符，记录剩余空间。"""
    disks = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        try:
            usage = shutil.disk_usage(root)
        except OSError:
            continue
        disks.append(
            {
                "drive": f"{letter}:",
                "free_gb": round(usage.free / 1024 ** 3, 1),
            }
        )
    return disks


def probe_port(port=COMFY_PORT):
    """尝试连接本机端口，能连上说明已被占用。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.6)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def decide_tier(gpu):
    """按显存划分档位并给出中文原因。"""
    if gpu is None:
        return "below", ["未检测到 NVIDIA 显卡，无法使用 CUDA 加速"]
    vram = gpu.get("vram_gb") or 0.0
    name = gpu.get("name") or "未知显卡"
    if vram >= 8:
        return "ok", [f"{name} 显存 {vram:.1f}GB，达到 8GB 推荐线"]
    if vram >= 6:
        return "marginal", [f"{name} 显存 {vram:.1f}GB，处于 6–8GB 区间，可出图但大尺寸偏慢"]
    return "below", [f"{name} 显存 {vram:.1f}GB，低于 6GB 下限"]


def main():
    parser = argparse.ArgumentParser(description="采集运行环境并判断可运行档位")
    parser.add_argument("--out", default="preflight.json", help="预检结果输出路径")
    args = parser.parse_args()

    gpu = probe_gpu()
    ram_gb = probe_ram_gb()
    disks = probe_disks()
    port_busy = probe_port()
    tier, reasons = decide_tier(gpu)

    # 补充与部署体验直接相关的提醒，不改变档位判定
    if ram_gb is not None and ram_gb < 16:
        reasons.append(f"系统内存 {ram_gb:.1f}GB，建议 16GB 以上")
    if disks and all(disk["free_gb"] < 30 for disk in disks):
        reasons.append("所有磁盘剩余空间均不足 30GB，可能放不下模型")

    result = {
        "gpu": gpu,
        "ram_gb": ram_gb,
        "disks": disks,
        "port_8188_busy": port_busy,
        "tier": tier,
        "reasons": reasons,
        "checkedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "python": platform.python_version(),
    }

    out_path = Path(args.out)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"预检完成：档位 {tier}，结果已写入 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
