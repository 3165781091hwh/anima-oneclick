# -*- coding: utf-8 -*-
"""生成结果复核：校验 PNG 完整性、尺寸与是否纯黑/纯白。

优先使用 Pillow 计算灰度均值与标准差；没有 Pillow 时退回 zlib 粗判。
除 Pillow 外仅使用 Python 标准库。
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS_BY_COLOR_TYPE = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def pillow_stats(path):
    """有 Pillow 时返回灰度均值与标准差，否则返回 None。"""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return None
    with Image.open(path) as image:
        image.load()
        stats = ImageStat.Stat(image.convert("L"))
        return float(stats.mean[0]), float(stats.stddev[0])


def iter_png_chunks(blob):
    """按 PNG 结构逐个产出 (类型, 数据) 块。"""
    position = 8
    size = len(blob)
    while position + 8 <= size:
        length = struct.unpack(">I", blob[position:position + 4])[0]
        chunk_type = blob[position + 4:position + 8]
        body_start = position + 8
        body_end = body_start + length
        if body_end > size:
            break
        yield chunk_type, blob[body_start:body_end]
        position = body_end + 4  # 跳过 CRC


def fallback_uniform(path, width, height, bit_depth, color_type):
    """无 Pillow 时解 IDAT 粗判是否所有像素同色。

    返回 True 表示同色，False 表示存在差异，None 表示无法解码。
    """
    try:
        blob = path.read_bytes()
    except OSError:
        return None
    idat = b"".join(body for chunk_type, body in iter_png_chunks(blob) if chunk_type == b"IDAT")
    if not idat:
        return None
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        return None
    if not raw:
        return None
    # 最直接的粗判：解压后所有字节相同
    if len(set(raw)) == 1:
        return True
    # 进一步按扫描行剥离 filter 字节，仅处理 8 位非隔行采样
    channels = CHANNELS_BY_COLOR_TYPE.get(color_type)
    if channels is None or bit_depth != 8:
        return False
    stride = width * channels
    row_size = stride + 1
    if stride <= 0 or len(raw) % row_size != 0:
        return False
    starts = range(0, len(raw), row_size)
    if any(raw[start] != 0 for start in starts):
        return False
    pixels = b"".join(raw[start + 1:start + row_size] for start in starts)
    return len(set(pixels)) == 1


def review_image(args):
    path = Path(args.image)
    failures = []
    notes = []
    width = height = None
    bit_depth = color_type = None

    if not path.is_file():
        failures.append("文件不存在")
        return width, height, failures, notes

    try:
        blob = path.read_bytes()
    except OSError as exc:
        failures.append(f"文件读取失败：{exc}")
        return width, height, failures, notes

    if not blob.startswith(PNG_SIGNATURE):
        failures.append("不是 PNG 文件（文件签名不匹配）")
        return width, height, failures, notes

    header = blob[:33]
    if len(header) < 33 or header[12:16] != b"IHDR":
        failures.append("PNG 缺少可解析的 IHDR 头")
        return width, height, failures, notes

    width, height = struct.unpack(">II", header[16:24])
    bit_depth = header[24]
    color_type = header[25]
    if width <= 0 or height <= 0:
        failures.append(f"宽高非法：{width}×{height}")

    if args.expect_w is not None and width != args.expect_w:
        failures.append(f"宽度不符：期望 {args.expect_w}，实际 {width}")
    if args.expect_h is not None and height != args.expect_h:
        failures.append(f"高度不符：期望 {args.expect_h}，实际 {height}")

    stats = None
    try:
        stats = pillow_stats(path)
    except Exception as exc:  # Pillow 解码失败即视为不可解码
        failures.append(f"图像解码失败：{exc}")

    if stats is not None:
        mean, stddev = stats
        if mean <= 1.0 and stddev <= 1.0:
            failures.append(f"图像接近纯黑（均值 {mean:.2f}，标准差 {stddev:.2f}）")
        elif mean >= 254.0 and stddev <= 1.0:
            failures.append(f"图像接近纯白（均值 {mean:.2f}，标准差 {stddev:.2f}）")
    elif not failures:
        uniform = fallback_uniform(path, width, height, bit_depth, color_type)
        notes.append("fallback：未安装 Pillow，已用 zlib 解 IDAT 做粗略判定")
        if uniform is None:
            failures.append("图像数据无法解码（IDAT 解压失败）")
        elif uniform:
            failures.append("图像为单一颜色（纯黑/纯白），判定不通过")

    return width, height, failures, notes


def main():
    parser = argparse.ArgumentParser(description="复核生成的 PNG 是否符合预期")
    parser.add_argument("--image", required=True, help="待检查图片路径")
    parser.add_argument("--expect-w", type=int, default=None, help="期望宽度")
    parser.add_argument("--expect-h", type=int, default=None, help="期望高度")
    parser.add_argument("--seed", type=int, default=None, help="本次生成使用的种子")
    parser.add_argument("--out", default="review.json", help="复核结果输出路径")
    args = parser.parse_args()

    width, height, failures, notes = review_image(args)
    passed = not failures
    result = {
        "image": str(Path(args.image)),
        "width": width,
        "height": height,
        "seed": args.seed,
        "passed": passed,
        "reasons": failures + notes,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if passed:
        print(f"复核通过：{args.image}（{width}×{height}），结果已写入 {out_path}")
        return 0
    print(f"复核未通过：{args.image}，原因：{'；'.join(failures)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
