#!/usr/bin/env python3
"""
img2code.py - превращает картинку в код для загрузки через веб-страницу Supermini-Reader.

Результат - текст из ровно 1024 значений вида 0x3C, (128x64 пикселя, 1 бит на пиксель,
по строкам, старший бит слева, 1 = светящийся пиксель). Его нужно вставить целиком в поле
"код картинки" на веб-странице устройства.

Нужен Pillow:  pip install pillow

Примеры:
  python img2code.py photo.jpg
  python img2code.py photo.jpg --mode fill --gamma 0.7
  python img2code.py photo.jpg --crop 60,380,1179,940 --mode stretch --gamma 0.7 --contrast 1.3
  python img2code.py logo.png --threshold 128 --invert
"""
import argparse
import sys

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    sys.exit("Нужна библиотека Pillow: pip install pillow")

W, H = 128, 64


def convert(path, crop=None, mode="fit", gamma=1.0, contrast=1.0,
            threshold=None, invert=False):
    im = Image.open(path).convert("L")
    if crop:
        im = im.crop(crop)
    im = ImageOps.autocontrast(im, cutoff=1)
    if gamma != 1.0:  # gamma < 1 - светлее, gamma > 1 - темнее
        im = im.point(lambda v: int(255 * ((v / 255) ** gamma)))
    if contrast != 1.0:
        im = ImageEnhance.Contrast(im).enhance(contrast)

    if mode == "stretch":      # растянуть на весь экран (пропорции могут исказиться)
        im = im.resize((W, H), Image.LANCZOS)
    elif mode == "fill":       # заполнить экран, лишнее обрезать по центру
        im = ImageOps.fit(im, (W, H), Image.LANCZOS, centering=(0.5, 0.5))
    else:                      # fit: вписать целиком, пустое место - чёрные поля
        r = min(W / im.width, H / im.height)
        nw, nh = max(1, round(im.width * r)), max(1, round(im.height * r))
        small = im.resize((nw, nh), Image.LANCZOS)
        im = Image.new("L", (W, H), 0)
        im.paste(small, ((W - nw) // 2, (H - nh) // 2))

    im = im.filter(ImageFilter.UnsharpMask(1.0, 100, 2))
    if threshold is not None:
        bw = im.point(lambda v: 255 if v >= threshold else 0).convert("1", dither=Image.NONE)
    else:
        bw = im.convert("1", dither=Image.FLOYDSTEINBERG)
    if invert:
        bw = ImageOps.invert(bw.convert("L")).convert("1", dither=Image.NONE)
    return bw


def to_code(bw):
    px = bw.load()
    lines = []
    for y in range(H):
        row = []
        for xb in range(W // 8):
            v = 0
            for b in range(8):
                if px[xb * 8 + b, y]:
                    v |= 0x80 >> b
            row.append("0x%02X," % v)
        lines.append(" ".join(row))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Картинка -> код 128x64 для Supermini-Reader")
    ap.add_argument("input", help="исходная картинка (jpg, png, ...)")
    ap.add_argument("-o", "--output", help="файл с кодом (по умолчанию <input>.txt)")
    ap.add_argument("--preview", help="файл PNG с предпросмотром (по умолчанию <input>_preview.png)")
    ap.add_argument("--crop", help="область X0,Y0,X1,Y1 в пикселях исходника")
    ap.add_argument("--mode", choices=["fit", "fill", "stretch"], default="fit",
                    help="fit - вписать с полями (по умолчанию), fill - заполнить с обрезкой, stretch - растянуть")
    ap.add_argument("--gamma", type=float, default=1.0, help="<1 светлее, >1 темнее")
    ap.add_argument("--contrast", type=float, default=1.0, help="контраст (1.0 - без изменений)")
    ap.add_argument("--threshold", type=int, help="порог 0-255 вместо растрирования (чёткий текст и логотипы)")
    ap.add_argument("--invert", action="store_true", help="поменять чёрное и белое местами")
    a = ap.parse_args()

    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    if crop and len(crop) != 4:
        sys.exit("--crop: нужно четыре числа X0,Y0,X1,Y1")

    bw = convert(a.input, crop, a.mode, a.gamma, a.contrast, a.threshold, a.invert)
    code = to_code(bw)
    base = a.input.rsplit(".", 1)[0]
    out = a.output or base + ".txt"
    prev = a.preview or base + "_preview.png"
    open(out, "w", encoding="utf-8").write(code)
    bw.resize((W * 4, H * 4), Image.NEAREST).save(prev)
    n = code.count("0x")
    print(f"Готово: {n} байт -> {out}; предпросмотр -> {prev}")
    if n != 1024:
        sys.exit("Ошибка: должно получиться ровно 1024 байта")


if __name__ == "__main__":
    main()
