"""The still frames of a Short. A frame is: a header (series + day + progress), the picture for the
beat (meme / code / output / takeaway) and the caption chunk being spoken."""

from __future__ import annotations

from PIL import Image, ImageDraw
from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.token import Comment, Keyword, Name, Number, Operator, String

from .fonts import font
from .memecards import INK, meme_image, wrap

BG = (13, 14, 22)
CARD = (24, 26, 40)
ACCENT = (255, 196, 61)
DIM = (110, 114, 140)
LEXERS = {"c++": "cpp", "js": "javascript"}


def _color(tok) -> tuple[int, int, int]:
    if tok in Comment:
        return (112, 122, 150)
    if tok in Keyword:
        return (255, 123, 114)
    if tok in String:
        return (165, 214, 120)
    if tok in Number:
        return (121, 192, 255)
    if tok in Name.Function or tok in Name.Class or tok in Name.Decorator:
        return (210, 168, 255)
    if tok in Name.Builtin:
        return (255, 196, 61)
    if tok in Operator:
        return (255, 166, 87)
    return (230, 232, 245)


def _tokens_by_line(source: str, language: str) -> list[list[tuple]]:
    name = LEXERS.get(language.lower(), language.lower())
    try:
        lexer = get_lexer_by_name(name)
    except Exception:
        lexer = guess_lexer(source)
    lines: list[list[tuple]] = [[]]
    for tok, text in lex(source, lexer):
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append((tok, part.expandtabs(4)))
    return lines


def _header(d: ImageDraw.ImageDraw, w: int, series: str, n: int, total: int) -> None:
    d.text((60, 70), series.upper(), font=font("bold", 40), fill=DIM)
    label = f"DAY {n}/{total}"
    d.text((w - 60 - d.textlength(label, font=font("bold", 56)), 56), label, font=font("bold", 56), fill=ACCENT)
    d.rounded_rectangle([60, 150, w - 60, 164], radius=7, fill=(40, 42, 62))
    d.rounded_rectangle([60, 150, 60 + max(14, int((w - 120) * n / total)), 164], radius=7, fill=ACCENT)


def _caption(d, w: int, h: int, text: str) -> None:
    fnt = font("bold", 76)
    lines = wrap(d, text, fnt, w - 140)[:3]
    y = h - 130 - len(lines) * 92
    for ln in lines:
        x = (w - d.textlength(ln, font=fnt)) / 2
        d.text((x, y), ln, font=fnt, fill=INK, stroke_width=9, stroke_fill=(0, 0, 0))
        y += 92


def _code_card(img, d, w, lesson, focus):
    code = lesson["code"]
    lines = _tokens_by_line(code["source"], lesson["_language"])
    n = max(len(lines), 1)
    widest = max((sum(len(t[1]) for t in ln) for ln in lines), default=10)
    size = max(30, min(66, int((w - 200) / (0.6 * max(widest, 12)))))
    fnt, step = font("mono", size), int(size * 1.55)
    height = n * step + 120
    top = 250 + max(0, (1250 - height) // 2)
    d.rounded_rectangle([40, top, w - 40, top + height], radius=28, fill=CARD)
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse([80 + i * 46, top + 34, 104 + i * 46, top + 58], fill=c)
    y = top + 100
    for i, ln in enumerate(lines, 1):
        lit = focus is None or focus[0] <= i <= focus[1]
        if focus and lit:
            d.rounded_rectangle([56, y - 6, w - 56, y + step - 10], radius=12, fill=(48, 52, 82))
        x = 90
        for tok, text in ln:
            col = _color(tok)
            if not lit:
                col = tuple(int(c * 0.38 + 20) for c in col)
            d.text((x, y), text, font=fnt, fill=col)
            x += d.textlength(text, font=fnt)
        y += step
    return top + height


def _output_card(d, w, lesson):
    out = str(lesson["code"].get("expected_output", "")).strip() or "(no output)"
    err = lesson["code"].get("expect") == "error"
    rows = sum(len(wrap(d, ln, font("mono", 48), w - 200)) or 1 for ln in out.splitlines()[:9])
    height = min(760, 190 + rows * 70)
    top = 250 + (1250 - height) // 2
    d.rounded_rectangle([40, top, w - 40, top + height], radius=28, fill=(8, 9, 14), outline=(255, 95, 86) if err else (39, 201, 63), width=4)
    d.text((90, top + 36), "$ run" if not err else "$ run  (error!)", font=font("monobold", 44), fill=ACCENT)
    fnt = font("mono", 48)
    y = top + 130
    for ln in out.splitlines()[:9]:
        for part in wrap(d, ln, fnt, w - 200) or [""]:
            d.text((90, y), part, font=fnt, fill=(255, 130, 120) if err else (165, 214, 120))
            y += 70


def _takeaway_card(d, w, text):
    top = 480
    d.rounded_rectangle([40, top, w - 40, top + 700], radius=36, fill=CARD, outline=ACCENT, width=6)
    d.text((90, top + 40), "REMEMBER", font=font("bold", 48), fill=ACCENT)
    fnt = font("bold", 78)
    y = top + 150
    for ln in wrap(d, text, fnt, w - 200)[:6]:
        d.text((90, y), ln, font=fnt, fill=INK)
        y += 100


def render_frame(lesson: dict, beat: dict, caption: str, series: str, total: int, w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    _header(d, w, series, lesson["n"], total)
    show = beat["show"]
    if show == "meme":
        card = meme_image(lesson["meme"], w - 120, 1120)
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.width, card.height], radius=36, fill=255)
        img.paste(card, (60, 250), mask)
        y = 1400
        for ln in wrap(d, lesson["hook"].upper(), font("bold", 54), w - 120)[:2]:
            d.text((60, y), ln, font=font("bold", 54), fill=ACCENT)
            y += 66
    elif show == "code":
        _code_card(img, d, w, lesson, beat.get("focus"))
    elif show == "output":
        _output_card(d, w, lesson)
    else:
        _takeaway_card(d, w, lesson["takeaway"])
    _caption(d, w, h, caption)
    return img
