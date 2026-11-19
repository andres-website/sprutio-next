#!/usr/bin/env python3
"""
Промо-картинка для README «как у оригинала» (sprutio/promo/slider_ui.png), но с интерфейсом форка.

Шаблон — оригинальная картинка: рамки окон, кнопки и тени остаются родными, заменяется только содержимое:
  переднее окно — x 197..1700, y 53..859 (1504×807, масштаб 1:1);
  заднее окно   — x 0..1899,  y 111..837 (тот же интерфейс в широком окне, масштаб ~0.743, затемнён).
Снимки делаются Playwright'ом на запущенном стенде (демо-сайты example.com / example.org в песочнице fmtest).

Запуск: venv/bin/python stand/tools/promo/make_promo.py  → promo/sprutio-next-ui.png
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'e2e'))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'api'))
from fmclient import FMClient, BASE  # noqa: E402
from conftest import _env  # noqa: E402
from uihelpers import login  # noqa: E402

TEMPLATE = os.path.join(ROOT, 'sprutio', 'promo', 'slider_ui.png')
OUT = os.path.join(ROOT, 'promo', 'sprutio-next-ui.png')
FRONT = (197, 53, 1504, 807)                 # x, y, w, h
BACK = (0, 111, 1900, 727)
BACK_SCALE = 26 / 35                         # высота меню: 26 px в заднем окне против 35 в переднем
BACK_TINT = (0.592, 0.596, 0.635)            # затемнение заднего окна (белый → 151,152,162 как в оригинале)

WP = [('wp-admin/', 0), ('wp-content/', 0), ('wp-includes/', 0), ('.htaccess', 296), ('index.php', 418),
      ('license.txt', 19935), ('readme.html', 7413), ('wp-activate.php', 4915), ('wp-blog-header.php', 271),
      ('wp-comments-post.php', 5002), ('wp-config-sample.php', 2853), ('wp-config.php', 3071),
      ('wp-cron.php', 3284), ('wp-links-opml.php', 2502), ('wp-load.php', 3507), ('wp-login.php', 33939),
      ('wp-mail.php', 8078), ('wp-settings.php', 10475), ('wp-signup.php', 29984), ('xmlrpc.php', 3064)]
SITE = [('cgi-bin/', 0), ('css/', 0), ('img/', 0), ('js/', 0), ('contacts@2x.png', 58411),
        ('favicon.ico', 1150), ('index.php', 6342), ('robots.txt', 68), ('sitemap.xml', 2210)]


def demo_data(api):
    sites = {'example.com/public_html': WP, 'example.org/public_html': SITE}
    for top in ('example.com', 'example.org'):
        try:
            api.remove(['%s/%s' % (api.home, top)])
        except Exception:
            pass
    for path, entries in sites.items():
        parts = path.split('/')
        for i in range(1, len(parts) + 1):
            try:
                api.mkdir('%s/%s' % (api.home, '/'.join(parts[:i])))
            except Exception:
                pass
        base = '%s/%s' % (api.home, path)
        for name, size in entries:
            if name.endswith('/'):
                api.mkdir(base + '/' + name.rstrip('/'))
            else:
                body = (b'<?php\n// demo\n' * (size // 14 + 1))[:size]
                api.upload(base, name, body)
    return ['%s/%s' % (api.home, p) for p in sites]


def shot(browser, creds, left, right, viewport, dpr):
    ctx = browser.new_context(ignore_https_errors=True, viewport=viewport, device_scale_factor=dpr, locale='ru-RU')
    p = ctx.new_page()
    login(p, creds)
    p.goto(BASE + '/?language=ru')
    p.wait_for_selector('.fm-file-list-panel .x-grid-item', timeout=45000)
    p.wait_for_function("document.getElementById('fm-fork-path-Left')", timeout=30000)
    for side, path in (('Right', right), ('Left', left)):
        p.evaluate('([s, d]) => FM.Actions.Open.execute(FM[s], d)', [side, path])
        p.wait_for_function('([s, d]) => FM[s].session.path === d', arg=[side, path], timeout=15000)
    p.evaluate('FM.helpers.SetActivePanel(FM.Left)')
    p.locator('.fm-file-list-panel >> nth=0').locator('.x-grid-item td:first-child', has_text='wp-content').first.click()
    p.mouse.move(5, viewport['height'] - 5)      # без hover-подсветки
    p.wait_for_timeout(1200)
    img = p.screenshot()
    ctx.close()
    path = os.path.join('/tmp', 'promo-%dx%d.png' % (viewport['width'], viewport['height']))
    open(path, 'wb').write(img)
    return Image.open(path).convert('RGBA')


def main():
    e = _env()
    creds = (e['FM_TEST_USER'], e['FM_TEST_PASS'])
    api = FMClient()
    api.login(*creds)
    api.init_session()
    left, right = demo_data(api)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        front = shot(browser, creds, left, right, {'width': FRONT[2], 'height': FRONT[3]}, 2)
        bw, bh = round(BACK[2] / BACK_SCALE), round(BACK[3] / BACK_SCALE)
        back = shot(browser, creds, left, right, {'width': bw, 'height': bh}, 1)
        browser.close()

    tpl = Image.open(TEMPLATE).convert('RGBA')
    out = tpl.copy()
    # заднее окно: уменьшить и затемнить
    back = back.resize((BACK[2], BACK[3]), Image.LANCZOS)
    r, g, b, a = back.split()
    r = r.point(lambda v: int(v * BACK_TINT[0]))
    g = g.point(lambda v: int(v * BACK_TINT[1]))
    b = b.point(lambda v: int(v * BACK_TINT[2]))
    back = Image.merge('RGBA', (r, g, b, a))
    out.paste(back, (BACK[0], BACK[1]))
    # мягкая тень переднего окна на заднем (в шаблоне она была «впечатана» в старое содержимое)
    shadow = Image.new('L', out.size, 0)
    ImageDraw.Draw(shadow).rectangle((196, 4, 1701, 900), fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    region = Image.new('L', out.size, 0)
    ImageDraw.Draw(region).rectangle((BACK[0], BACK[1], BACK[0] + BACK[2] - 1, BACK[1] + BACK[3] - 1), fill=255)
    from PIL import ImageChops
    shadow = ImageChops.multiply(shadow, region)
    black = Image.new('RGBA', out.size, (0, 0, 0, 255))
    out = Image.composite(black, out, shadow).convert('RGBA')
    out.putalpha(tpl.getchannel('A'))
    # переднее окно поверх (вместе с его рамкой из шаблона)
    frame = tpl.crop((196, 0, 1702, 860))
    out.paste(frame, (196, 0), frame)
    front = front.resize((FRONT[2], FRONT[3]), Image.LANCZOS)
    out.paste(front, (FRONT[0], FRONT[1]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, optimize=True)
    print('saved', OUT, out.size)


if __name__ == '__main__':
    main()
