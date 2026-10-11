#!/usr/bin/env python3
"""Create auditable old-photo candidates with Pillow and optional GFPGAN."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Source JPG/PNG/TIFF image")
    parser.add_argument("--output-dir", required=True, type=Path, help="New or empty output directory")
    parser.add_argument("--gfpgan-root", type=Path, help="Existing GFPGAN checkout with installed dependencies")
    parser.add_argument("--model-python", default=sys.executable, help="Python executable for GFPGAN")
    parser.add_argument(
        "--allow-upstream-downloads",
        action="store_true",
        help="Allow GFPGAN to download missing auxiliary weights from its upstream sources",
    )
    return parser.parse_args()


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def adjust_luminance(image, contrast: float, radius: float, percent: int):
    from PIL import ImageEnhance, ImageFilter

    if image.mode == "L":
        luminance = image
        color = None
    else:
        y, cb, cr = image.convert("YCbCr").split()
        luminance = y
        color = (cb, cr)
    luminance = ImageEnhance.Contrast(luminance).enhance(contrast)
    luminance = luminance.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=4))
    if color is None:
        return luminance
    from PIL import Image

    return Image.merge("YCbCr", (luminance, *color)).convert("RGB")


def comparison(source, faithful, enhanced, destination: Path) -> None:
    from PIL import Image

    previews = []
    for picture in (source, faithful, enhanced):
        preview = picture.convert("RGB")
        preview.thumbnail((700, 700), Image.Resampling.LANCZOS)
        previews.append(preview)
    height = max(p.height for p in previews)
    canvas = Image.new("RGB", (sum(p.width for p in previews), height), "white")
    offset = 0
    for preview in previews:
        canvas.paste(preview, (offset, 0))
        offset += preview.width
    canvas.save(destination)


def try_gfpgan(args: argparse.Namespace, faithful_path: Path, output: Path) -> tuple[bool, str]:
    if args.gfpgan_root is None:
        return False, "未提供 GFPGAN 环境；增强版仅做插值放大与锐化，未重建人脸。"
    root = args.gfpgan_root.expanduser().resolve()
    entry = root / "inference_gfpgan.py"
    if not entry.is_file():
        return False, "GFPGAN 入口不存在；使用轻量增强版。"
    model = "GFPGANv1.4.pth"
    weights = [root / "experiments" / "pretrained_models" / model, root / "gfpgan" / "weights" / model]
    if not any(path.is_file() for path in weights):
        return False, "GFPGANv1.4 权重不存在；为避免自动下载，使用轻量增强版。"
    if not args.allow_upstream_downloads:
        return False, "未允许上游辅助权重下载；GFPGAN 未运行，使用轻量增强版。"
    model_output = output / "gfpgan"
    command = [
        args.model_python,
        str(entry),
        "-i", str(faithful_path),
        "-o", str(model_output),
        "-v", "1.4",
        "-s", "2",
        "--bg_upsampler", "none",
        "--ext", "png",
    ]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=1800, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"GFPGAN 未完成：{error}"
    (output / "gfpgan-log.txt").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    restored = model_output / "restored_imgs" / f"{faithful_path.stem}.png"
    if result.returncode or not restored.is_file():
        return False, f"GFPGAN 退出码 {result.returncode} 或未生成整图；查看 gfpgan-log.txt。"
    shutil.copy2(restored, output / "enhanced.png")
    face_count = len(list((model_output / "restored_faces").glob("*.png")))
    return True, f"GFPGAN v1.4 已运行；检测到 {face_count} 张脸。生成式细节仍需人工核对。"


def main() -> int:
    args = arguments()
    try:
        from PIL import Image, ImageOps
    except ImportError:
        print("缺少 Pillow。可按照片情况提供人工修复方案，或在获准后安装 Pillow。", file=sys.stderr)
        return 2

    source_path = args.input.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    if not source_path.is_file():
        print(f"原图不存在：{source_path}", file=sys.stderr)
        return 2
    if output.exists() and not output.is_dir():
        print(f"输出位置不是目录：{output}", file=sys.stderr)
        return 2
    if output.exists() and any(output.iterdir()):
        print(f"输出目录必须为空：{output}", file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)

    original_copy = output / f"original{source_path.suffix.lower()}"
    shutil.copy2(source_path, original_copy)
    with Image.open(source_path) as opened:
        oriented = ImageOps.exif_transpose(opened)
        original_mode = oriented.mode
        if original_mode == "L":
            image = oriented.copy()
            mode_note = "保留灰度"
        elif original_mode in ("RGB", "P"):
            image = oriented.convert("RGB")
            mode_note = "保留彩色"
        elif original_mode == "RGBA":
            background = Image.new("RGBA", oriented.size, "white")
            image = Image.alpha_composite(background, oriented).convert("RGB")
            mode_note = "透明区域合成白底"
        else:
            image = oriented.convert("RGB")
            mode_note = f"由 {original_mode} 转为 RGB"

    faithful = adjust_luminance(image, contrast=1.035, radius=1.0, percent=55)
    faithful_path = output / "faithful.png"
    faithful.save(faithful_path)
    enhanced = faithful.resize((faithful.width * 2, faithful.height * 2), Image.Resampling.LANCZOS)
    enhanced = adjust_luminance(enhanced, contrast=1.025, radius=1.2, percent=95)
    enhanced_path = output / "enhanced.png"
    enhanced.save(enhanced_path)

    model_used, model_note = try_gfpgan(args, faithful_path, output)
    with Image.open(enhanced_path) as model_image:
        comparison(image, faithful, model_image, output / "comparison.png")

    report = {
        "source": str(source_path),
        "source_sha256": digest(source_path),
        "source_size": list(image.size),
        "source_mode": original_mode,
        "mode_note": mode_note,
        "outputs": {
            "original": original_copy.name,
            "faithful": faithful_path.name,
            "enhanced": enhanced_path.name,
            "comparison": "comparison.png",
        },
        "faithful_process": "Luminance contrast 1.035; unsharp radius 1.0, percent 55; original size",
        "enhanced_process": "GFPGAN v1.4 face restoration at 2x" if model_used else "Pillow Lanczos 2x and unsharp; no face reconstruction",
        "model_note": model_note,
        "review": "Compare eyes, nose, mouth, face outline, age cues, hair, glasses and text against original. No generated detail is verified history.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output), "model_used": model_used, "note": model_note}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
