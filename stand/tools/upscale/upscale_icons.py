#!/usr/bin/env python3
"""
Тест «Режима max retina»: увеличение оригинальных иконок sprutio в 2 раза разными способами.

Варианты:
  xbrz   — xBRZ ×2 (алгоритм для пиксель-арта, с альфой);
  esrgan — Real-ESRGAN x4plus_anime_6B (нейросеть) ×4 → уменьшение до ×2 (LANCZOS).

Что увеличивается:
  - спрайт типов файлов icons_16.png → images/retina-max/<вариант>/icons_16@2x.png (раскладка ×2);
  - 16-px иконки действий images/actions/16/*.png → images/retina-max/<вариант>/actions/<имя>.png (32×32).

Запуск (в контейнере, см. Dockerfile рядом):
  docker run --rm -v "$PWD":/w -w /w sprutio-upscale python stand/tools/upscale/upscale_icons.py
Потом CSS: venv/bin/python stand/tools/upscale/make_test_css.py
"""
import os
import re

import numpy as np
from PIL import Image

RES = 'sprutio/app/public/fm/resources'
IMG = os.path.join(RES, 'images')
OUT = os.path.join(IMG, 'retina-max')
PAD = 8   # поле вокруг иконки: нейросети нужен контекст, края не обрезаются


def sprite_offsets():
    css = open(os.path.join(RES, 'style.css'), encoding='utf-8').read()
    return {m.group(1): 6 - int(m.group(2)) for m in re.finditer(
        r'\.fm-file-list-panel td\.icon-16-([\w-]+) div,[^{]*\{\s*background-position:\s*6px\s+(-?\d+)px', css)}


def bleed(rgba):
    """Цвет прозрачных пикселей ← ближайших непрозрачных (иначе на краях ореолы)."""
    a = np.array(rgba).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3:4] / 255.0
    known = (alpha[..., 0] > 0.02)
    out = rgb.copy()
    filled = known.copy()
    for _ in range(PAD + 16):
        if filled.all():
            break
        acc = np.zeros_like(out)
        cnt = np.zeros(filled.shape, np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            sh = np.roll(np.roll(out, dy, 0), dx, 1)
            sf = np.roll(np.roll(filled, dy, 0), dx, 1)
            acc += sh * sf[..., None]
            cnt += sf
        new = (~filled) & (cnt > 0)
        out[new] = acc[new] / cnt[new][..., None]
        filled |= new
    return out


# --- xBRZ -------------------------------------------------------------------------------------------
def up_xbrz(icon):
    import xbrz
    return xbrz.scale_pillow(icon.convert('RGBA'), 2)


# --- Real-ESRGAN ------------------------------------------------------------------------------------
_model = None


def esrgan(arr_rgb):
    import torch
    from spandrel import ModelLoader
    global _model
    if _model is None:
        _model = ModelLoader().load_from_file('/models/RealESRGAN_x4plus_anime_6B.pth').eval()
    t = torch.from_numpy(arr_rgb / 255.0).permute(2, 0, 1)[None].float()
    with torch.no_grad():
        out = _model(t)[0].clamp(0, 1).permute(1, 2, 0).numpy()
    return out * 255.0


def up_esrgan(icon):
    w, h = icon.size
    big = Image.new('RGBA', (w + 2 * PAD, h + 2 * PAD), (0, 0, 0, 0))
    big.paste(icon, (PAD, PAD))
    rgb = bleed(big)
    alpha = np.array(big)[..., 3].astype(np.float32)
    rgb4 = esrgan(rgb)
    a4 = esrgan(np.repeat(alpha[..., None], 3, axis=2)).mean(axis=2)
    img = np.dstack([rgb4, a4]).clip(0, 255).astype(np.uint8)
    out = Image.fromarray(img, 'RGBA')
    s = 4
    out = out.crop((PAD * s, PAD * s, (PAD + w) * s, (PAD + h) * s))
    return out.resize((w * 2, h * 2), Image.LANCZOS)


VARIANTS = {'xbrz': up_xbrz, 'esrgan': up_esrgan}


def main():
    sprite = Image.open(os.path.join(IMG, 'sprites', 'icons_16.png')).convert('RGBA')
    offsets = sprite_offsets()
    actions = sorted(f for f in os.listdir(os.path.join(IMG, 'actions', '16')) if f.endswith('.png'))
    for name, fn in VARIANTS.items():
        os.makedirs(os.path.join(OUT, name, 'actions'), exist_ok=True)
        out = Image.new('RGBA', (sprite.width * 2, sprite.height * 2), (0, 0, 0, 0))
        for icon_name, y in offsets.items():
            cell = sprite.crop((0, y, 16, y + 16))
            out.paste(fn(cell), (0, y * 2))
        out.save(os.path.join(OUT, name, 'icons_16@2x.png'), optimize=True)
        for f in actions:
            icon = Image.open(os.path.join(IMG, 'actions', '16', f)).convert('RGBA')
            if icon.size != (16, 16):
                continue
            fn(icon).save(os.path.join(OUT, name, 'actions', f), optimize=True)
        print(name, 'sprite', len(offsets), 'actions', len(actions))


if __name__ == '__main__':
    main()
