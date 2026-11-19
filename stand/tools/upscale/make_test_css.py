#!/usr/bin/env python3
"""
CSS теста увеличенных иконок → resources/css/fm-retina-test.css.
Действует только в «Режиме max retina» (html.fm-retina-max) и на экранах высокой плотности;
вариант выбирается в Настройках → Интерфейс (класс html.fm-rv-<вариант>).
Иконки, у которых есть родная 32-px версия того же рисунка (fm-retina.css), не трогаем — они лучше.

Запуск: venv/bin/python stand/tools/upscale/make_test_css.py  (после upscale_icons.py)
"""
import os
import re

RES = 'sprutio/app/public/fm/resources'
IMG = os.path.join(RES, 'images')
URL = '/fm/resources/images/retina-max'
VARIANTS = ('xbrz', 'esrgan')


def main():
    css = open(os.path.join(RES, 'style.css'), encoding='utf-8').read()
    native = set(re.findall(r"actions/32/([\w-]+)\.png", open(os.path.join(RES, 'css', 'fm-retina.css')).read()))
    sprite_h = 4108
    rules = ['/* Сгенерировано stand/tools/upscale/make_test_css.py — тест увеличенных иконок, не править руками. */',
             '@media (-webkit-min-device-pixel-ratio: 1.5), (min-resolution: 1.5dppx) {']
    for v in VARIANTS:
        base = os.path.join(IMG, 'retina-max', v)
        if not os.path.exists(os.path.join(base, 'icons_16@2x.png')):
            continue
        p = 'html.fm-retina-max.fm-rv-%s' % v
        rules += ['  %s .fm-file-list-panel .cell-icon > div, %s .fm-file-search-list .cell-icon > div,' % (p, p),
                  '  %s .fm-file-size-list .cell-icon > div, %s .fm-site-list .cell-icon > div {' % (p, p),
                  "    background-image: url('%s/%s/icons_16@2x.png?v=1') !important;" % (URL, v),
                  '    background-size: 16px %dpx !important;' % sprite_h,
                  '  }']
        for m in re.finditer(r"([^{}]+)\{\s*background-image:\s*url\('/fm/resources/images/actions/16/([\w-]+)\.png'\);\s*\}",
                             css):
            selector, name = m.group(1).strip(), m.group(2)
            if name in native or not os.path.exists(os.path.join(base, 'actions', name + '.png')):
                continue
            selector = ', '.join('%s %s' % (p, s.strip()) for s in selector.split(','))
            rules += ['  %s {' % selector,
                      "    background-image: url('%s/%s/actions/%s.png?v=1');" % (URL, v, name),
                      '    background-size: 16px 16px;',
                      '  }']
    rules += ['  html.fm-retina-max #fm-main-buttons-toolbar .x-btn-icon-el { background-size: auto; }', '}']
    open(os.path.join(RES, 'css', 'fm-retina-test.css'), 'w', encoding='utf-8').write('\n'.join(rules) + '\n')
    print('rules:', sum(1 for r in rules if r.endswith('{')))


if __name__ == '__main__':
    main()
