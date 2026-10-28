# -*- coding: utf-8 -*-
"""把 API 格式工作流提交到 ComfyUI，等待出图并保存结果。

仅使用 Python 标准库。--dry-run 时不联网，只把改好的 prompt 落盘。
"""

import argparse
import json
import random
import sys
import time
import uuid
from pathlib import Path
from urllib import error, parse, request

# scripts 目录的上一级即 skill 根目录，presets.json 位于此处
SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVER = "http://127.0.0.1:8188"
HTTP_TIMEOUT = 30
WAIT_SECONDS = 300


def load_default_negative():
    """读取 presets.json 里约定的负向词；读取失败时返回空串。"""
    try:
        data = json.loads((SKILL_ROOT / "presets.json").read_text(encoding="utf-8"))
        return str(data["internal"]["negative"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def resolve_workflow(raw_path):
    """支持相对当前目录或相对 skill 根目录的工作流路径。"""
    path = Path(raw_path)
    if path.is_file():
        return path.resolve()
    fallback = SKILL_ROOT / raw_path
    if fallback.is_file():
        return fallback.resolve()
    raise FileNotFoundError(f"找不到工作流文件：{raw_path}")


def build_prompt(workflow, positive, negative, seed, width, height):
    """按节点约定写入提示词、尺寸与随机种子。"""
    if "5" not in workflow:
        raise KeyError('工作流缺少正向提示词节点 "5"')
    if "8" not in workflow:
        raise KeyError('工作流缺少空 latent 节点 "8"')
    if "4" not in workflow:
        raise KeyError('工作流缺少采样器节点 "4"')

    workflow["5"].setdefault("inputs", {})["text"] = positive
    if "7" in workflow:
        workflow["7"].setdefault("inputs", {})["text"] = negative
    latent_inputs = workflow["8"].setdefault("inputs", {})
    if width is not None:
        latent_inputs["width"] = width
    if height is not None:
        latent_inputs["height"] = height
    workflow["4"].setdefault("inputs", {})["seed"] = seed
    return workflow


def request_json(url, payload=None):
    """发送 GET/POST 请求并解析 JSON，出错时抛出带原始信息的异常。"""
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} {url}：{body[:800]}") from exc
    except (error.URLError, OSError) as exc:
        raise RuntimeError(f"网络错误 {url}：{exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"返回内容不是合法 JSON {url}：{exc}") from exc


def submit_prompt(server, workflow):
    """POST /prompt 并返回 prompt_id。"""
    body = {"prompt": workflow, "client_id": str(uuid.uuid4())}
    response = request_json(f"{server}/prompt", body)
    if not isinstance(response, dict):
        raise RuntimeError(f"提交响应格式异常：{response!r}")
    if response.get("error") or response.get("node_errors"):
        raise RuntimeError("提交被拒绝：" + json.dumps(response, ensure_ascii=False)[:800])
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise RuntimeError("提交响应缺少 prompt_id：" + json.dumps(response, ensure_ascii=False)[:800])
    return prompt_id


def wait_for_history(server, prompt_id):
    """每秒轮询一次历史记录，直到出现 outputs 或超时。"""
    deadline = time.monotonic() + WAIT_SECONDS
    url = f"{server}/history/{prompt_id}"
    while time.monotonic() < deadline:
        data = request_json(url)
        entry = data.get(prompt_id) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            status = entry.get("status") or {}
            if status.get("status_str") == "error":
                raise RuntimeError(
                    "生成失败：" + json.dumps(status, ensure_ascii=False)[:800]
                )
            if entry.get("outputs"):
                return entry
        time.sleep(1)
    raise TimeoutError(f"等待生成超时（{WAIT_SECONDS} 秒）")


def pick_output_image(entry):
    """从 outputs 中挑出 type=output 的图片。"""
    candidates = []
    for node_output in (entry.get("outputs") or {}).values():
        if not isinstance(node_output, dict):
            continue
        for image in node_output.get("images") or []:
            if isinstance(image, dict) and image.get("filename"):
                candidates.append(image)
    for image in candidates:
        if (image.get("type") or "output") == "output":
            return image
    return candidates[0] if candidates else None


def download_image(server, image, destination):
    """从 /view 下载图片并写入目标路径。"""
    query = parse.urlencode(
        {
            "filename": image.get("filename", ""),
            "subfolder": image.get("subfolder", ""),
            "type": image.get("type") or "output",
        }
    )
    url = f"{server}/view?{query}"
    try:
        with request.urlopen(url, timeout=HTTP_TIMEOUT) as response:
            blob = response.read()
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"下载失败 HTTP {exc.code} {url}：{body[:800]}") from exc
    except (error.URLError, OSError) as exc:
        raise RuntimeError(f"下载失败 {url}：{exc}") from exc
    if not blob:
        raise RuntimeError(f"下载到空文件：{url}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(blob)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def recipe_name(workflow_path):
    """由工作流文件名推断配方名，如 anima-quality -> quality。"""
    stem = workflow_path.stem
    return stem[len("anima-"):] if stem.startswith("anima-") else stem


def main():
    parser = argparse.ArgumentParser(description="提交 Anima 工作流到 ComfyUI 并取回图片")
    parser.add_argument("--workflow", required=True, help="API 格式工作流 JSON 路径")
    parser.add_argument("--positive", required=True, help="正向提示词")
    parser.add_argument("--negative", default=None, help="负向提示词，默认取 presets.json")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，默认随机 15 位整数")
    parser.add_argument("--width", type=int, default=None, help="图片宽度，默认沿用工作流")
    parser.add_argument("--height", type=int, default=None, help="图片高度，默认沿用工作流")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="ComfyUI 服务地址")
    parser.add_argument("--out", default="result.json", help="结果 JSON 输出路径")
    parser.add_argument("--dry-run", action="store_true", help="不联网，只输出改好的 prompt")
    args = parser.parse_args()

    server = args.server.rstrip("/")
    out_path = Path(args.out)
    negative = args.negative if args.negative is not None else load_default_negative()
    seed = args.seed if args.seed is not None else random.randint(10 ** 14, 10 ** 15 - 1)
    recipe = recipe_name(Path(args.workflow))
    prompt_id = None
    started = time.monotonic()

    try:
        workflow_path = resolve_workflow(args.workflow)
        recipe = recipe_name(workflow_path)

        try:
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"读取工作流失败：{exc}") from exc
        if not isinstance(workflow, dict):
            raise RuntimeError("工作流内容不是 JSON 对象")

        build_prompt(workflow, args.positive, negative, seed, args.width, args.height)

        if args.dry_run:
            write_json(out_path, workflow)
            print(f"dry-run：宽 {args.width or '沿用'} × 高 {args.height or '沿用'}，seed {seed}，已写入 {out_path}")
            return 0

        prompt_id = submit_prompt(server, workflow)
        entry = wait_for_history(server, prompt_id)
        image = pick_output_image(entry)
        if image is None:
            raise RuntimeError("任务输出中没有找到图片")

        image_path = out_path.parent / f"Anima_{seed}.png"
        download_image(server, image, image_path)

        result = {
            "image": str(image_path),
            "width": args.width,
            "height": args.height,
            "seed": seed,
            "recipe": recipe,
            "elapsed_s": round(time.monotonic() - started, 2),
            "prompt_id": prompt_id,
        }
        write_json(out_path, result)
        print(f"出图完成：{image_path}（seed {seed}，耗时 {result['elapsed_s']} 秒）")
        return 0
    except Exception as exc:  # 统一落盘原始错误，避免静默失败
        result = {
            "image": None,
            "width": args.width,
            "height": args.height,
            "seed": seed,
            "recipe": recipe,
            "elapsed_s": round(time.monotonic() - started, 2),
            "prompt_id": prompt_id,
            "error": str(exc),
        }
        write_json(out_path, result)
        print(f"提交失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
