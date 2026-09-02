"""Build the 1200x630 Open Graph / social share image.

Source is the homepage hero: an aerial shot of the site team around a drawing.
It is distinctive and still readable at thumbnail size, which matters more for
a social card than resolution does.

No text is burned in - the platforms render the og:title and og:description
alongside the image, and baking in type risks looking off-brand at the sizes
LinkedIn and X actually display.
"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "uploads",
                   "on-site-team-ensuring-ground-works-are-within-water-industry-regulations.jpg")
OUT = os.path.join(ROOT, "assets", "uploads", "aquamain-social-1200x630.jpg")

TARGET_W, TARGET_H = 1200, 630

im = Image.open(SRC).convert("RGB")
sw, sh = im.size

# Cover-crop to the 1.905:1 OG ratio, anchored slightly above centre so the
# group of workers (upper-left of frame) stays in shot.
target_ratio = TARGET_W / TARGET_H
src_ratio = sw / sh

if src_ratio > target_ratio:
    new_w = int(sh * target_ratio)
    left = (sw - new_w) // 2
    im = im.crop((left, 0, left + new_w, sh))
else:
    new_h = int(sw / target_ratio)
    top = int((sh - new_h) * 0.35)          # bias upward
    im = im.crop((0, top, sw, top + new_h))

im = im.resize((TARGET_W, TARGET_H), Image.LANCZOS)
im.save(OUT, "JPEG", quality=86, optimize=True, progressive=True)

print(f"source : {sw}x{sh}")
print(f"output : {im.width}x{im.height}  {os.path.getsize(OUT)/1024:.0f} KB")
print(f"path   : assets/uploads/{os.path.basename(OUT)}")
