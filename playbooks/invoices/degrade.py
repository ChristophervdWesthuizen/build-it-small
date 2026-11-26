"""Turn clean renders into 'scans' (grey, slightly skewed, speckled) and 'phone photos'
(rotated, uneven light, soft focus). No text layer survives, as with the real thing."""
import json
import random
from pathlib import Path

from PIL import Image, ImageFilter, ImageEnhance, ImageOps

CASES = Path(__file__).parent / "cases"


def scan(img, r):
    g = ImageOps.grayscale(img)
    g = g.rotate(r.uniform(-1.8, 1.8), resample=Image.BICUBIC, expand=True, fillcolor=255)
    px = g.load()
    w, h = g.size
    for _ in range(w * h // 400):  # speckle
        x, y = r.randrange(w), r.randrange(h)
        px[x, y] = r.choice([0, 60, 200])
    g = g.filter(ImageFilter.GaussianBlur(0.6))
    return ImageEnhance.Contrast(g).enhance(r.uniform(0.8, 1.3)).convert("RGB")


def photo(img, r):
    im = img.convert("RGB").rotate(r.uniform(-7, 7), resample=Image.BICUBIC, expand=True, fillcolor=(120, 110, 95))
    w, h = im.size
    shade = Image.linear_gradient("L").resize((w, h)).rotate(r.choice([0, 90, 180, 270]), expand=False)
    im = Image.composite(im, ImageEnhance.Brightness(im).enhance(0.62), ImageOps.invert(shade).point(lambda v: 255 - v // 2))
    im = im.filter(ImageFilter.GaussianBlur(r.uniform(0.8, 1.4)))
    im = im.resize((int(w * 0.8), int(h * 0.8)))
    return ImageEnhance.Color(im).enhance(0.85)


def main():
    r = random.Random(7)
    n = 0
    for t in sorted(CASES.glob("*.truth.json")):
        c = json.loads(t.read_text())
        if c["format"] == "pdf":
            continue
        src = CASES / f"{c['id']}.clean.png"
        img = Image.open(src)
        out = scan(img, r) if c["format"] == "scan" else photo(img, r)
        out.save(CASES / f"{c['id']}.jpg", quality=78)
        src.unlink()
        n += 1
    print("degraded", n)


if __name__ == "__main__":
    main()
