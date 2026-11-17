"""将 demo-frames 下的帧截图合成为 docs/demo.gif。"""
import glob
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT.parent / "demo-frames"
OUT = ROOT / "docs" / "demo.gif"
WIDTH = 800


def main() -> int:
    frames = sorted(glob.glob(str(FRAMES_DIR / "*.png")))
    if not frames:
        print("未找到帧截图，请先运行 scripts/record_demo.mjs", file=sys.stderr)
        return 1
    images = []
    for path in frames:
        image = Image.open(path)
        height = int(image.height * WIDTH / image.width)
        images.append(image.resize((WIDTH, height), Image.LANCZOS))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(OUT, save_all=True, append_images=images[1:], duration=800, loop=0, optimize=True)
    print(f"已生成 {OUT}（{len(images)} 帧）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
