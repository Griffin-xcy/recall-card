"""生成打包用的应用图标 build/icon.ico（不依赖外部素材）。"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
BG = (37, 99, 235)      # 蓝
CARD = (255, 255, 255)
ACCENT = (251, 191, 36)  # 琥珀色对勾
OUT = Path(__file__).resolve().parent.parent / "build" / "icon.ico"


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def build() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    rounded(draw, (0, 0, SIZE, SIZE), 110, BG)

    # 后面那张卡片（略微倾斜的感觉用偏移和浅色模拟）
    rounded(draw, (120, 150, 392, 400), 28, (191, 219, 254))
    # 前面那张卡片
    rounded(draw, (150, 110, 362, 360), 28, CARD)

    # 卡片上的三条内容线
    for index, width in enumerate((150, 170, 110)):
        top = 160 + index * 56
        rounded(draw, (186, top, 186 + width, top + 18), 9, (203, 213, 225))

    # 右下角对勾徽章
    draw.ellipse((250, 268, 400, 418), fill=ACCENT)
    draw.line([(292, 344), (322, 374), (364, 316)], fill=(17, 24, 39), width=22, joint="curve")

    return image


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image = build()
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    image.save(OUT, format="ICO", sizes=sizes)
    print(f"图标已生成：{OUT}")


if __name__ == "__main__":
    main()
