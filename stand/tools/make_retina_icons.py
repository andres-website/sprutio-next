#!/usr/bin/env python3
"""
Форк sprutio: базовая retina-поддержка без смены рисунка иконок.

Генерирует resources/css/fm-retina.css (всегда, под @media ≥1.5dppx): 16-px иконка действия заменяется
её 32-px версией из того же sprutio, ТОЛЬКО если рисунок совпадает (32 px, уменьшенная до 16, почти
не отличается от оригинала: средняя разница < THRESHOLD). Остальные остаются оригинальными.

Проверено 2026-11-19: спрайт типов файлов icons_16.png — уникальный набор, ни icons/128, ни icons/48,
ни даже icons/16/*.png его рисунок не повторяют (жёлтые папки и т.п.) → для типов файлов чётких версий нет.

Свои иконки — вручную в resources/css/fm-retina-max.css (галочка «Режим max retina»).

Запуск: venv/bin/python stand/tools/make_retina_icons.py
"""
import os
import re

from PIL import Image, ImageChops, ImageStat

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'sprutio', 'app', 'public', 'fm',
                                     'resources'))
IMG = os.path.join(ROOT, 'images')
CSS_SRC = os.path.join(ROOT, 'style.css')
CSS_OUT = os.path.join(ROOT, 'css', 'fm-retina.css')
URL = '/fm/resources/images'
THRESHOLD = 30  # средняя по каналам разница 0..255 на белом фоне; тот же рисунок — 7..26, другой — 42+


def flat(im):
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert('RGB')


def difference(small_path, big_path):
    a = flat(Image.open(small_path).convert('RGBA'))
    b = flat(Image.open(big_path).convert('RGBA').resize(a.size, Image.LANCZOS))
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def main():
    css = open(CSS_SRC, encoding='utf-8').read()
    rules = [
        '/* Сгенерировано stand/tools/make_retina_icons.py — не править руками.',
        '   Базовая retina (всегда): только иконки, у которых есть 32-px версия того же рисунка.',
        '   Свои замены — в fm-retina-max.css (галочка «Режим max retina»). */',
        '@media (-webkit-min-device-pixel-ratio: 1.5), (min-resolution: 1.5dppx) {',
    ]
    used, skipped = [], []
    for m in re.finditer(r'([^{}]+)\{\s*background-image:\s*url\(\'/fm/resources/images/actions/16/([\w-]+)\.png\'\);\s*\}',
                         css):
        selector, name = m.group(1).strip(), m.group(2)
        small = os.path.join(IMG, 'actions', '16', name + '.png')
        big = os.path.join(IMG, 'actions', '32', name + '.png')
        if not os.path.exists(big):
            continue
        d = difference(small, big)
        if d >= THRESHOLD:
            skipped.append('%s(%.0f)' % (name, d))
            continue
        used.append('%s(%.0f)' % (name, d))
        # 'html ' поднимает специфичность над style.css, который может загрузиться позже нас
        selector = ', '.join('html ' + s.strip() for s in selector.split(','))
        rules += ['  %s {' % selector,
                  "    background-image: url('%s/actions/32/%s.png');" % (URL, name),
                  '    background-size: 16px 16px;',
                  '  }']
    # большие кнопки главной панели уже 32 px — размер фона не трогаем
    rules += ['  html #fm-main-buttons-toolbar .x-btn-icon-el { background-size: auto; }', '}']
    os.makedirs(os.path.dirname(CSS_OUT), exist_ok=True)
    open(CSS_OUT, 'w', encoding='utf-8').write('\n'.join(rules) + '\n')
    print('used:', ' '.join(sorted(set(used))))
    print('skipped (другой рисунок):', ' '.join(sorted(set(skipped))) or '-')


if __name__ == '__main__':
    main()
