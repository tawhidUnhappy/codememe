"""Full-screen, animated scenes - every one fills the 1080x1920 frame and moves. A scene is built once
(`prepare`), then asked for frames in order: frame(t) for t seconds into the scene.

meme      a memegen template, full-bleed (blurred copy behind, sharp one punching in)
clip      a GIF / video clip, cover-cropped, with overlay text (falls back to a `text` scene when not found)
terminal  a Windows / macOS / Linux terminal; the commands are typed live, the output appears after them
code      an editor with the lesson's code, typed live, with the explained lines lit
text      big kinetic text on a moving gradient
takeaway  the closing card"""

from __future__ import annotations

import math
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageOps
from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.token import Comment, Keyword, Name, Number, Operator, String

from .fonts import font
from .memecards import INK, _fit_text, meme_image, wrap

W, H = 1080, 1920
LEXERS = {"c++": "cpp", "js": "javascript"}
PALETTES = [((255, 94, 98), (255, 195, 113)), ((106, 17, 203), (37, 117, 252)), ((17, 153, 142), (56, 239, 125)),
            ((252, 70, 107), (63, 94, 251)), ((247, 151, 30), (255, 210, 0)), ((0, 198, 255), (0, 114, 255))]


def ease_out(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return 1 - (1 - u) ** 3


def _cover(img: Image.Image, w: int = W, h: int = H) -> Image.Image:
    s = max(w / img.width, h / img.height)
    img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)))
    return img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))


def _contain(img: Image.Image, w: int, h: int, scale: float = 1.0) -> Image.Image:
    s = min(w / img.width, h / img.height) * scale
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))))


_GRAD = None


def gradient(t: float, palette: int) -> Image.Image:
    """A slowly drifting two-colour gradient filling the frame."""
    global _GRAD
    if _GRAD is None:
        _GRAD = Image.linear_gradient("L").resize((W, H * 2))
    off = int((math.sin(t * 0.9) * 0.5 + 0.5) * H)
    dark, light = PALETTES[palette % len(PALETTES)]
    return ImageOps.colorize(_GRAD.crop((0, off, W, off + H)), dark, light)


def _paste_center(base: Image.Image, fg: Image.Image, cy: float = 0.5, shadow: bool = True) -> None:
    x, y = (W - fg.width) // 2, int(H * cy - fg.height / 2)
    if shadow:
        sh = Image.new("RGBA", (fg.width + 60, fg.height + 60), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle([30, 40, fg.width + 30, fg.height + 40], fill=(0, 0, 0, 150))
        base.paste(sh.filter(ImageFilter.GaussianBlur(22)), (x - 30, y - 30), sh.filter(ImageFilter.GaussianBlur(22)))
    base.paste(fg, (x, y))


def window(img: Image.Image, top: int, height: int, bg, bar, bar_h: int = 100) -> ImageDraw.ImageDraw:
    """A rounded app window with a drop shadow, centred on the gradient 'desktop'; returns a Draw for its body."""
    x0, x1 = 30, W - 30
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0 + 8, top + 22, x1 + 8, top + height + 22], radius=26, fill=(0, 0, 0, 170))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(24)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(24)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, top, x1, top + height], radius=26, fill=bg)
    d.rounded_rectangle([x0, top, x1, top + bar_h], radius=26, fill=bar, corners=(True, True, False, False))
    return d


class Scene:
    def __init__(self, spec: dict, ctx: dict):
        self.spec, self.ctx = spec, ctx
        self.duration = 2.0

    def prepare(self, duration: float) -> None:
        self.duration = duration

    def frame(self, t: float) -> Image.Image:
        raise NotImplementedError

    def close(self) -> None:
        pass


class MemeScene(Scene):
    def prepare(self, duration):
        super().prepare(duration)
        spec = self.spec
        try:
            from .memegen import render_meme
            pic = render_meme(spec["id"], spec["captions"], 1080)
        except Exception as e:
            print(f"warning: meme {spec.get('id')} unavailable ({e}); built-in layout")
            caps = spec["captions"]
            pic = meme_image({"template": "choice" if len(caps) == 2 else "brain" if len(caps) == 4 else "classic", "captions": caps}, 1000, 1000)
        self.pic = pic.convert("RGB")
        self.bg = ImageEnhance_darken(_cover(self.pic).filter(ImageFilter.GaussianBlur(36)))

    def frame(self, t):
        u = t / self.duration
        pop = 0.86 + 0.14 * ease_out(t / 0.18)
        fg = _contain(self.pic, W - 40, 1060, pop * (1 + 0.05 * u))
        img = self.bg.copy()
        _paste_center(img, fg, 0.37)
        return img


def ImageEnhance_darken(img: Image.Image, factor: float = 0.45) -> Image.Image:
    return Image.eval(img, lambda v: int(v * factor))


class TextScene(Scene):
    def prepare(self, duration):
        super().prepare(duration)
        self.palette = hash(self.spec.get("text", "")) % len(PALETTES)

    def frame(self, t):
        img = gradient(t, self.palette)
        d = ImageDraw.Draw(img)
        text = self.spec.get("text", "")
        k = 0.7 + 0.3 * ease_out(t / 0.22)
        layer = Image.new("RGBA", (W, 900), (0, 0, 0, 0))
        _fit_text(ImageDraw.Draw(layer), text.upper(), (50, 0, W - 50, 900), start=150, stroke=10)
        layer = layer.resize((int(W * k), int(900 * k)))
        img.paste(layer, ((W - layer.width) // 2, int(H * 0.40 - layer.height / 2)), layer)
        if self.spec.get("sub"):
            _fit_text(d, self.spec["sub"], (80, int(H * 0.56), W - 80, int(H * 0.56) + 260), start=62, stroke=0)
        return img


class ClipScene(Scene):
    def prepare(self, duration):
        super().prepare(duration)
        from .clips import resolve
        self.path = resolve(self.spec["query"], self.spec.get("source", "auto"))
        self.proc = None
        self.last = None
        if self.path:
            self.proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(self.path), "-t", f"{duration + 0.5:.2f}", "-an",
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={self.ctx['fps']}",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        else:
            self.fallback = TextScene({"text": self.spec.get("text") or self.spec["query"]}, self.ctx)
            self.fallback.prepare(duration)

    def frame(self, t):
        if not self.proc:
            return self.fallback.frame(t)
        raw = self.proc.stdout.read(W * H * 3)
        if len(raw) == W * H * 3:
            self.last = Image.frombytes("RGB", (W, H), raw)
        img = (self.last or Image.new("RGB", (W, H))).copy()
        if self.spec.get("text"):
            layer = Image.new("RGBA", (W, 520), (0, 0, 0, 0))
            _fit_text(ImageDraw.Draw(layer), self.spec["text"].upper(), (40, 0, W - 40, 520), start=110, stroke=9)
            img.paste(layer, (0, int(H * 0.16)), layer)
        return img

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc.wait()


def _color(tok):
    if tok in Comment:
        return (112, 130, 160)
    if tok in Keyword:
        return (255, 123, 114)
    if tok in String:
        return (165, 214, 120)
    if tok in Number:
        return (121, 192, 255)
    if tok in Name.Function or tok in Name.Class:
        return (210, 168, 255)
    if tok in Name.Builtin:
        return (255, 196, 61)
    if tok in Operator:
        return (255, 166, 87)
    return (230, 232, 245)


def _tokens(source: str, language: str) -> list[list[tuple]]:
    name = LEXERS.get(language.lower(), language.lower())
    try:
        lexer = get_lexer_by_name(name)
    except Exception:
        lexer = guess_lexer(source)
    lines: list[list[tuple]] = [[]]
    for tok, text in lex(source, lexer):
        for i, part in enumerate(text.split("\n")):
            if i:
                lines.append([])
            if part:
                lines[-1].append((tok, part.expandtabs(4)))
    return lines


class CodeScene(Scene):
    """An editor: tab, line numbers, the code typed live (typing: true) or shown whole with `focus` lines lit."""

    def prepare(self, duration):
        super().prepare(duration)
        code = self.ctx["lesson"]["code"]
        self.lines = _tokens(code["source"], self.ctx["language"])
        self.name = code.get("filename") or "main"
        widest = max((sum(len(x[1]) for x in ln) for ln in self.lines), default=10)
        self.size = max(30, min(66, int((W - 240) / (0.6 * max(widest, 12)))))
        self.total = sum(len(x[1]) for ln in self.lines for x in ln)

    def frame(self, t):
        img = gradient(t, 1)
        step = int(self.size * 1.6)
        height = 120 + len(self.lines) * step + 50
        top = int(H * 0.40 - height / 2)
        d = window(img, top, height, (22, 24, 36), (36, 39, 58))
        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse([62 + i * 46, top + 36, 88 + i * 46, top + 62], fill=c)
        d.text((260, top + 28), self.name, font=font("mono", 38), fill=(230, 232, 245))
        focus = self.spec.get("focus")
        shown = self.total if not self.spec.get("typing") else int(self.total * min(1, t / (self.duration * 0.72)))
        left, y = shown, top + 130
        fnt = font("mono", self.size)
        for i, ln in enumerate(self.lines, 1):
            lit = focus is None or focus[0] <= i <= focus[1] or self.spec.get("typing")
            if focus and focus[0] <= i <= focus[1]:
                d.rectangle([30, y - 8, W - 30, y + step - 14], fill=(46, 52, 84))
            d.text((64, y), str(i), font=fnt, fill=(90, 96, 128))
            x = 150
            for tok, text in ln:
                text = text[:max(0, left)]
                left -= len(text)
                col = _color(tok) if lit else tuple(int(c * 0.4 + 18) for c in _color(tok))
                d.text((x, y), text, font=fnt, fill=col)
                x += d.textlength(text, font=fnt)
                if left <= 0:
                    break
            if left <= 0 and shown < self.total:
                if int(t * 2.2) % 2 == 0:
                    d.rectangle([x + 2, y + 4, x + 6 + self.size // 4, y + self.size], fill=(255, 196, 61))
                break
            y += step
        return img


OS_STYLE = {
    "windows": {"bg": (12, 12, 12), "bar": (32, 32, 32), "title": "Windows Terminal", "prompt": "C:\\Users\\you> ", "pcol": (204, 204, 204)},
    "mac": {"bg": (30, 30, 30), "bar": (52, 52, 52), "title": "Terminal - zsh", "prompt": "you@mac ~ % ", "pcol": (130, 220, 130)},
    "linux": {"bg": (48, 10, 36), "bar": (70, 30, 56), "title": "you@pc: ~", "prompt": "you@pc:~$ ", "pcol": (140, 230, 120)},
}


class TerminalScene(Scene):
    """lines: [{"cmd": "python --version", "prompt": "optional"}, {"out": "Python 3.14.4"}] - commands typed, output after."""

    def prepare(self, duration):
        super().prepare(duration)
        self.style = OS_STYLE[self.spec.get("os", "linux")]
        self.rows = self.spec["lines"]
        self.cmd_chars = sum(len(r["cmd"]) for r in self.rows if "cmd" in r)
        self.palette = {"windows": 5, "mac": 3, "linux": 0}[self.spec.get("os", "linux")]

    def frame(self, t):
        st = self.style
        img = gradient(t, self.palette)
        longest = max(len(r.get("prompt", st["prompt"])) + len(r["cmd"]) if "cmd" in r else len(r["out"]) for r in self.rows)
        size = max(34, min(54, int((W - 62 * 2 - 30) / (0.6 * max(longest, 8)))))
        fnt, step = font("mono", size), int(size * 1.5)
        height = 110 + (len(self.rows) + 2) * step + 40
        top = int(H * 0.40 - height / 2)
        d = window(img, top, height, st["bg"], st["bar"])
        cy = top + 50
        if self.spec.get("os") == "mac":
            for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
                d.ellipse([62 + i * 52, cy - 15, 92 + i * 52, cy + 15], fill=c)
            d.text((W / 2 - d.textlength(st["title"], font=font("bold", 36)) / 2, cy - 22), st["title"], font=font("bold", 36), fill=(205, 205, 205))
        else:
            d.text((70, cy - 22), st["title"], font=font("bold", 36), fill=(225, 225, 225))
            bx = W - 70
            d.line([bx - 190, cy, bx - 160, cy], fill=(225, 225, 225), width=4)          # minimise
            d.rectangle([bx - 110, cy - 14, bx - 82, cy + 14], outline=(225, 225, 225), width=4)  # maximise
            d.line([bx - 32, cy - 14, bx - 4, cy + 14], fill=(225, 225, 225), width=4)   # close
            d.line([bx - 32, cy + 14, bx - 4, cy - 14], fill=(225, 225, 225), width=4)
        typed = int(self.cmd_chars * min(1, t / (self.duration * 0.62))) if self.cmd_chars else 0
        y, remaining = top + 130, typed
        pad = 62
        for r in self.rows:
            if "cmd" in r:
                prompt = r.get("prompt", st["prompt"])
                d.text((pad, y), prompt, font=fnt, fill=st["pcol"])
                x = pad + d.textlength(prompt, font=fnt)
                shown = r["cmd"][:max(0, remaining)]
                d.text((x, y), shown, font=fnt, fill=(240, 240, 240))
                x += d.textlength(shown, font=fnt)
                remaining -= len(r["cmd"])
                if remaining < 0:  # still typing this one: stop here
                    if int(t * 2.4) % 2 == 0:
                        d.rectangle([x + 2, y + 6, x + size // 2, y + size + 4], fill=(240, 240, 240))
                    return img
                y += step
            else:
                for part in wrap(d, r["out"], fnt, W - 2 * pad - 30) or [""]:
                    d.text((pad, y), part, font=fnt, fill=(205, 205, 205))
                    y += step
        prompt = st["prompt"]
        for r in reversed(self.rows):
            if "cmd" in r:
                prompt = r.get("prompt", st["prompt"])
                break
        if int(t * 2.4) % 2 == 0:
            d.text((pad, y), prompt, font=fnt, fill=st["pcol"])
            x = pad + d.textlength(prompt, font=fnt)
            d.rectangle([x + 2, y + 6, x + size // 2, y + size + 4], fill=(240, 240, 240))
        return img


class TakeawayScene(Scene):
    def frame(self, t):
        img = gradient(t, 2)
        k = ease_out(t / 0.25)
        card = Image.new("RGBA", (W - 120, 760), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, card.width, 760], radius=44, fill=(14, 16, 26, 235))
        cd.text((60, 50), "REMEMBER", font=font("bold", 54), fill=(255, 196, 61))
        _fit_text(cd, self.ctx["lesson"]["takeaway"], (60, 150, card.width - 60, 720), start=84, stroke=0)
        card = card.resize((int(card.width * (0.8 + 0.2 * k)), int(760 * (0.8 + 0.2 * k))))
        img.paste(card, ((W - card.width) // 2, int(H * 0.40 - card.height / 2)), card)
        return img


KINDS = {"meme": MemeScene, "clip": ClipScene, "terminal": TerminalScene, "code": CodeScene, "text": TextScene, "takeaway": TakeawayScene}


def make(spec: dict, ctx: dict) -> Scene:
    return KINDS[spec["type"]](spec, ctx)


def overlay(img: Image.Image, ctx: dict, caption: str, progress: float) -> Image.Image:
    """Header (series, day, progress) and the spoken caption - on every frame."""
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([40, 56, W - 40, 150], radius=30, fill=(0, 0, 0, 120))
    d.text((70, 78), ctx["series"].upper(), font=font("bold", 34), fill=(235, 235, 245))
    label = f"DAY {ctx['n']}/{ctx['total']}"
    d.text((W - 70 - d.textlength(label, font=font("bold", 46)), 70), label, font=font("bold", 46), fill=(255, 196, 61))
    d.rectangle([40, 150, 40 + int((W - 80) * progress), 158], fill=(255, 196, 61))
    if caption:
        fnt = font("bold", 78)
        lines = wrap(d, caption, fnt, W - 140)[:3]
        y = 1500 - len(lines) * 94
        for ln in lines:
            d.text(((W - d.textlength(ln, font=fnt)) / 2, y), ln, font=fnt, fill=INK, stroke_width=10, stroke_fill=(0, 0, 0))
            y += 94
    return img
