"""
python generate.py [--input-dir TMP] [--output-dir TARGET] [--pixel-size N] [--quantize] [--colors C] [--yes]
"""
from __future__ import annotations
import argparse
import os
import shutil
import json
from typing import Optional
from PIL import Image
def ask_int(prompt: str, default: int) -> int:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        if v <= 0:
            raise ValueError()
        return v
    except ValueError:
        print("请输入正整数。")
        return ask_int(prompt, default)

def ask_bool(prompt: str, default: bool) -> bool:
    raw = input(f"{prompt} [{'Y' if default else 'N'}]: ").strip().lower()
    if not raw:
        return default
    return raw[0] in ("y", "1", "t")

def pixelate_image(img: Image.Image, pixel_size: int) -> Image.Image:
    """将图片像素化：先缩小再用 NEAREST 放大，形成像素块。"""
    w, h = img.size
    small_w = max(1, w // pixel_size)
    small_h = max(1, h // pixel_size)
    bilinear = getattr(Image, "BILINEAR", 2)
    nearest = getattr(Image, "NEAREST", 0)
    small = img.resize((small_w, small_h), bilinear)
    result = small.resize((small_w * pixel_size, small_h * pixel_size), nearest)
    return result

def process_file(in_path: str, out_path: str, pixel_size: int, quantize: bool, colors: int) -> None:
    with Image.open(in_path) as im:
        im = im.convert("RGBA")
        pixel = pixelate_image(im, pixel_size)
        if quantize:
            method_mediancut = getattr(Image, "MEDIANCUT", 0)
            pixel = pixel.convert("RGB").quantize(colors=colors, method=method_mediancut)
            pixel = pixel.convert("RGBA")
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        pixel.save(out_path, format="PNG")

def gather_pngs(input_dir: str) -> list[str]:
    names = [f for f in os.listdir(input_dir) if f.lower().endswith(".png")]
    return sorted(names)

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="批量将 tmp/ 下 PNG 转为像素画并保存到 target/（文件名保持原名）")
    parser.add_argument("--input-dir", default="tmp", help="源图片目录，默认 tmp")
    parser.add_argument("--output-dir", default="target", help="目标输出目录，默认 target")
    parser.add_argument("--pixel-size", type=int, help="像素块大小（正整数），例如 8 表示每个像素块为 8x8")
    parser.add_argument("--quantize", action="store_true", help="启用颜色减量化")
    parser.add_argument("--no-clean", action="store_true", help="生成前不清空目标目录（保留已有文件）")
    parser.add_argument("--colors", type=int, default=32, help="减色后颜色数量（仅在 --quantize 时生效），默认 32")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过交互式确认，使用参数或默认值")
    args = parser.parse_args(argv)
    input_dir = args.input_dir
    output_dir = args.output_dir
    pixel_size = None
    quantize = args.quantize
    colors = args.colors
    cfg_dir = "cfg"
    cfg_path = os.path.join(cfg_dir, "last_config.json")
    last_cfg: dict | None = None
    used_last_cfg = False
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                last_cfg = json.load(fh)
        except Exception:
            last_cfg = None
    if last_cfg:
        print("发现上次使用的配置:")
        for k, v in last_cfg.items():
            print(f"  {k}: {v}")
        if args.yes:
            use_last = True
        else:
            use_last = ask_bool("是否直接使用上次配置并开始处理（不修改）?", True)
        if use_last:
            used_last_cfg = True
            input_dir = last_cfg.get("input_dir", input_dir)
            output_dir = last_cfg.get("output_dir", output_dir)
            pixel_size = last_cfg.get("pixel_size")
            quantize = last_cfg.get("quantize", False)
            colors = last_cfg.get("colors", 32)
            args.no_clean = last_cfg.get("no_clean", False)
    else:
        pixel_size = None
    if 'pixel_size' not in locals():
        pixel_size = None
    if 'quantize' not in locals():
        quantize = args.quantize
    if 'colors' not in locals():
        colors = args.colors
    if not os.path.isdir(input_dir):
        print(f"输入目录不存在: {input_dir}")
        return 2
    files = gather_pngs(input_dir)
    if not files:
        print("未在输入目录找到 PNG 文件。")
        return 0
    skip_prompts = args.yes or used_last_cfg

    if used_last_cfg:
        pixel_size = pixel_size or 8
    else:
        if args.pixel_size is None and not skip_prompts:
            pixel_size = ask_int("像素块大小 (正整数, 值越大块越大，默认 8)", 8)
        else:
            pixel_size = args.pixel_size or 8

    if used_last_cfg:
        quantize = bool(quantize)
    else:
        quantize = args.quantize
        if not skip_prompts and not args.quantize:
            quantize = ask_bool("是否启用颜色减量（可减少颜色使像素画更平面）?", False)

    if used_last_cfg:
        colors = int(colors or 32)
    else:
        colors = args.colors
        if quantize and not skip_prompts:
            colors = ask_int("颜色数量 (用于减色，建议 8-64)", colors or 32)
    print(f"找到 {len(files)} 个 PNG 文件，将从 '{input_dir}' -> '{output_dir}' 进行处理")
    print(f"像素块大小: {pixel_size}, 减色: {quantize}, 颜色数: {colors}")
    if not skip_prompts:
        cont = ask_bool("确认开始处理吗?", True)
        if not cont:
            print("已取消")
            return 0

    if not getattr(args, "no_clean", False):
        if os.path.exists(output_dir):
            abs_out = os.path.abspath(output_dir)
            if abs_out == os.path.abspath(os.sep):
                print("拒绝清空根目录。")
                return 2
            if not skip_prompts:
                clean_confirm = ask_bool(f"将清空目录 '{output_dir}' 中的所有内容，继续吗?", False)
                if not clean_confirm:
                    print("取消清空目标目录，已退出。")
                    return 0
            for child in os.listdir(output_dir):
                child_path = os.path.join(output_dir, child)
                try:
                    if os.path.isdir(child_path) and not os.path.islink(child_path):
                        shutil.rmtree(child_path)
                    else:
                        os.remove(child_path)
                except Exception as e:
                    print(f"无法删除 {child_path}: {e}")
        else:
            os.makedirs(output_dir, exist_ok=True)
    else:
        os.makedirs(output_dir, exist_ok=True)
    processed = 0
    for name in files:
        in_path = os.path.join(input_dir, name)
        out_path = os.path.join(output_dir, name)  # 按要求：不在文件名加 _pixel，使用原名
        try:
            process_file(in_path, out_path, pixel_size, quantize, colors)
            processed += 1
            print(f"已生成: {out_path}")
        except Exception as e:
            print(f"处理 {name} 时出错: {e}")
    print(f"完成。成功处理 {processed}/{len(files)} 张图片。 输出目录: {output_dir}")

    try:
        os.makedirs(cfg_dir, exist_ok=True)
        save_cfg = {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "pixel_size": pixel_size,
            "quantize": bool(quantize),
            "colors": int(colors),
            "no_clean": bool(getattr(args, "no_clean", False)),
        }
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(save_cfg, fh, ensure_ascii=False, indent=2)
        print(f"已保存配置到 {cfg_path}")
    except Exception as e:
        print(f"保存配置失败: {e}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
