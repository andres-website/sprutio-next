"""Генератор тестового «проекта» для замеров поиска: ~10k файлов, ~80 МБ."""
import os, random, sys
root = sys.argv[1]; random.seed(42)
words = "function return class public private static array string value config module theme render node field".split()
exts = ["php", "php", "js", "css", "inc", "txt", "json", "twig", "yml"]
n = 0
for m in range(25):
    for d in range(10):
        p = os.path.join(root, "modules", "mod%02d" % m, "src", "part%02d" % d)
        os.makedirs(p, exist_ok=True)
        for f in range(40):
            ext = random.choice(exts)
            lines = [" ".join(random.choice(words) for _ in range(12)) for _ in range(random.randint(60, 200))]
            if (m, d, f) in ((3, 4, 5), (17, 2, 30), (24, 9, 0)):
                lines.insert(len(lines) // 2, "$token = 'UNIQUE_NEEDLE_7731';  // Кириллица тоже: ёжик")
            with open(os.path.join(p, "file%02d.%s" % (f, ext)), "w") as fh:
                fh.write("\n".join(lines))
            n += 1
        with open(os.path.join(p, "img.png"), "wb") as fh:
            fh.write(os.urandom(30000)); n += 1
os.makedirs(os.path.join(root, "deep/a/b/c/d"), exist_ok=True)
open(os.path.join(root, "deep/a/b/c/d/needle-config.php"), "w").write("<?php return [];")
print("files:", n + 1)
