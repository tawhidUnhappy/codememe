"""The meme picture, drawn from a lesson's meme spec. Three layouts that need no template image
(choice, brain, classic on a plain card) and classic over any picture the user put in assets/memes/."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .fonts import font
from .paths import MEMES

INK = (245, 245, 250)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _fit_text(draw, text, box, start=84, stroke=0, fill=INK, anchor_center=True):
    """Largest size (down from `start`) at which the wrapped text fits the box; draws it centred."""
    x0, y0, x1, y1 = box
    size = start
    while size > 26:
        fnt = font("bold", size)
        lines = wrap(draw, text, fnt, x1 - x0)
        height = len(lines) * int(size * 1.2)
        if height <= y1 - y0 and all(draw.textlength(ln, font=fnt) <= x1 - x0 for ln in lines):
            break
        size -= 4
    y = y0 + ((y1 - y0) - height) // 2 if anchor_center else y0
    for ln in lines:
        w = draw.textlength(ln, font=fnt)
        draw.text((x0 + (x1 - x0 - w) / 2, y), ln, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += int(size * 1.2)


def _choice(captions, w, h):
    img = Image.new("RGB", (w, h), (20, 20, 28))
    d = ImageDraw.Draw(img)
    half = h // 2
    for i, (bg, mark) in enumerate((((120, 40, 50), "x"), ((30, 105, 70), "v"))):
        top = i * half
        d.rectangle([0, top, w, top + half - 6], fill=bg)
        cx, cy, r = 150, top + half // 2, 70
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 245, 250))
        pen = (200, 40, 50) if mark == "x" else (30, 150, 80)
        if mark == "x":
            d.line([cx - 36, cy - 36, cx + 36, cy + 36], fill=pen, width=18)
            d.line([cx - 36, cy + 36, cx + 36, cy - 36], fill=pen, width=18)
        else:
            d.line([cx - 40, cy + 2, cx - 10, cy + 34, cx + 42, cy - 34], fill=pen, width=18, joint="curve")
        _fit_text(d, str(captions[i]), (270, top + 30, w - 40, top + half - 36), start=70)
    return img


def _brain(captions, w, h):
    img = Image.new("RGB", (w, h), (16, 16, 26))
    d = ImageDraw.Draw(img)
    row = h // 4
    glow = [(90, 90, 110), (80, 130, 200), (120, 90, 210), (255, 215, 90)]
    for i in range(4):
        top = i * row
        d.rectangle([0, top, w, top + row - 6], fill=(28 + i * 4, 28 + i * 4, 44 + i * 6))
        cx, cy = 130, top + row // 2
        r = 28 + i * 14
        for k in range(3 if i else 0):
            rr = r + (k + 1) * 12
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=glow[i], width=3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=glow[i])
        _fit_text(d, str(captions[i]), (260, top + 16, w - 30, top + row - 22), start=64)
    return img


def _classic(captions, w, h, image_name):
    base = Image.new("RGB", (w, h), (40, 36, 70))
    d = ImageDraw.Draw(base)
    for y in range(h):  # plain vertical gradient when there is no template picture
        t = y / h
        d.line([0, y, w, y], fill=(int(60 + 80 * t), int(40 + 30 * t), int(110 - 40 * t)))
    if image_name and (MEMES / image_name).exists():
        pic = Image.open(MEMES / image_name).convert("RGB")
        scale = max(w / pic.width, h / pic.height)
        pic = pic.resize((int(pic.width * scale), int(pic.height * scale)))
        base = pic.crop(((pic.width - w) // 2, (pic.height - h) // 2, (pic.width + w) // 2, (pic.height + h) // 2))
    d = ImageDraw.Draw(base)
    _fit_text(d, str(captions[0]).upper(), (30, 20, w - 30, h // 2 - 20), start=96, stroke=8)
    if len(captions) > 1:
        _fit_text(d, str(captions[1]).upper(), (30, h // 2 + 20, w - 30, h - 20), start=96, stroke=8)
    return base


def meme_image(meme: dict, w: int, h: int) -> Image.Image:
    template, caps = meme["template"], meme["captions"]
    if template == "choice":
        return _choice(caps, w, h)
    if template == "brain":
        return _brain(caps, w, h)
    return _classic(caps, w, h, meme.get("image"))
