"""FAT Agent promo: 30s, 1920x1080, hand-drawn noir. Frames piped to ffmpeg; audio synthesised.

Usage: python promo.py [--preview t1,t2,...] [--out file.mp4]
"""
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = r"C:\Users\ryesm\fat-agent-packaging\fat-agent-skill\site\assets"
W, H, FPS, DUR = 1920, 1080, 30, 30.0
NF = int(FPS * DUR)

NIGHT = (16, 19, 25)
ASPHALT = (27, 31, 39)
MANILA = (232, 213, 163)
MANILA2 = (201, 174, 114)
INK = (43, 36, 24)
RED = (200, 16, 46)
RED2 = (224, 49, 76)
CHROME = (216, 220, 226)
DIM = (154, 161, 173)
WHITE = (245, 242, 232)


def F(name, size):
    return ImageFont.truetype(os.path.join(HERE, "fonts", name), size)


DISP = {s: F("BowlbyOne.ttf", s) for s in (40, 56, 64, 72, 88, 100, 120, 150, 210, 300)}
TYPE = {s: F("SpecialElite.ttf", s) for s in (24, 28, 32, 36, 40, 48, 56, 64, 80, 96)}
MONO = {s: F("JetBrainsMono.ttf", s) for s in (30, 34)}

PORTRAIT = Image.open(os.path.join(ASSETS, "agent-portrait.png")).convert("RGBA")
BADGE = Image.open(os.path.join(ASSETS, "badge-testing.png")).convert("RGBA")
SECRET = Image.open(os.path.join(ASSETS, "badge-topsecret.png")).convert("RGBA")


# ----------------------------------------------------------------- timeline
# every visual beat and every sound come from here, so they stay in sync
T_LINE1 = (0.25, "A WEBSITE WENT QUIET.", 0.055)
T_LINE2 = (1.55, "SOMEBODY CALLED THE FAT AGENT.", 0.040)
T_END_TYPE = (26.95, "He's not fat.", 0.055)
EV = {
    "whoosh": [3.2, 10.4, 14.0, 19.0, 23.0, 26.2],
    "thunk": [4.1, 6.15, 16.2, 17.0, 17.3, 20.5, 20.8, 21.1, 23.2, 23.6, 24.0, 27.8],
    "bigthunk": [17.6, 24.8],
    "thunder": [7.6],
    "ticks": (11.2, 12.4, 23),
    "stinger": [24.85],
    "motif": [3.4, 26.35],
}
SCENES = [(0.0, 3.2), (3.2, 6.0), (6.0, 10.4), (10.4, 14.0), (14.0, 19.0),
          (19.0, 23.0), (23.0, 26.2), (26.2, 30.0)]


# ----------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def seg(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def smooth(x):
    return x * x * (3 - 2 * x)


def back(x):  # ease-out-back: overshoot then settle
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def boil(fr):  # hand-drawn line boil at 10 fps
    return fr // 3


_tcache = {}


def text_img(txt, font, fill, stroke=0, stroke_fill=None, rot=0.0):
    key = (txt, font.path, font.size, fill, stroke, stroke_fill, round(rot, 2))
    if key in _tcache:
        return _tcache[key]
    bb = font.getbbox(txt, stroke_width=stroke)
    im = Image.new("RGBA", (bb[2] - bb[0] + 24, bb[3] - bb[1] + 24), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((12 - bb[0], 12 - bb[1]), txt, font=font, fill=fill,
                            stroke_width=stroke, stroke_fill=stroke_fill)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    _tcache[key] = im
    return im


def jrot(fr, amp=0.6):
    return (-amp, amp * 0.4, amp)[boil(fr) % 3]


def put(frame, im, cx, cy, scale=1.0, alpha=1.0, anchor="c"):
    if scale <= 0.001 or alpha <= 0.001:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.BICUBIC)
    if alpha < 0.999:
        im = im.copy()
        a = np.asarray(im.getchannel("A"), dtype=np.float32) * alpha
        im.putalpha(Image.fromarray(a.astype(np.uint8)))
    x = int(cx - im.width / 2) if anchor == "c" else int(cx)
    y = int(cy - im.height / 2) if anchor == "c" else int(cy)
    frame.paste(im, (x, y), im)


def jline(d, p1, p2, fill, width, fr, seed=0, amp=2.5):
    rnd = random.Random(hash((round(p1[0]), round(p1[1]), round(p2[0]), round(p2[1]),
                              boil(fr), seed)))
    pts = []
    for i in range(5):
        t = i / 4
        x = p1[0] + (p2[0] - p1[0]) * t
        y = p1[1] + (p2[1] - p1[1]) * t
        if 0 < i < 4:
            x += rnd.uniform(-amp, amp)
            y += rnd.uniform(-amp, amp)
        pts.append((x, y))
    d.line(pts, fill=fill, width=width, joint="curve")


def jrect(d, box, fill, outline, width, fr, seed=0, radius=6):
    x0, y0, x1, y1 = box
    if fill is not None:
        d.rounded_rectangle(box, radius=radius, fill=fill)
    for i, (a, b) in enumerate((((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                                ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)))):
        jline(d, a, b, outline, width, fr, seed * 10 + i)


_scache = {}


def stamp_img(txt, color, size, rot=-8):
    key = (txt, color, size, rot)
    if key in _scache:
        return _scache[key]
    font = TYPE[size]
    bb = font.getbbox(txt)
    pad = size // 3
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    im = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bw = max(4, size // 10)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), radius=size // 6, outline=color + (235,),
                        width=bw)
    d.text((10 + pad - bb[0], 10 + pad - bb[1]), txt, font=font, fill=color + (235,))
    im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    _scache[key] = im
    return im


def stamp_scale(t, at):
    if t < at:
        return 0.0
    x = seg(t, at, at + 0.13)
    return 1 + 0.9 * (1 - smooth(x))


def typed(txt, t, start, rate):
    n = int((t - start) / rate) + 1 if t >= start else 0
    return txt[: max(0, min(len(txt), n))]


# ----------------------------------------------------------------- backgrounds
def radial(cx, cy, rx, ry, color, strength):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    a = np.clip(1 - r, 0, 1) ** 1.6 * strength
    return a[..., None] * np.array(color, np.float32)[None, None, :]


def make_bg(base, spot=(0.62, 0.42), strength=0.22, skyline=False):
    top = np.array(base, np.float32)
    bot = np.array(base, np.float32) * 0.72
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = top * (1 - g) + bot * g
    arr = np.broadcast_to(arr, (H, W, 3)).copy()
    arr += radial(W * spot[0], H * spot[1], W * 0.42, H * 0.7, MANILA, strength * 255 / 255)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if skyline:
        d = ImageDraw.Draw(img)
        rnd = random.Random(7)
        x = -20
        while x < W:
            bw = rnd.randint(90, 200)
            bh = rnd.randint(160, 420)
            d.rectangle((x, H - bh, x + bw, H), fill=(11, 13, 18))
            for wy in range(H - bh + 24, H - 30, 34):
                for wx in range(x + 14, x + bw - 18, 28):
                    if rnd.random() < 0.22:
                        d.rectangle((wx, wy, wx + 12, wy + 16), fill=(122, 104, 58))
            x += bw + rnd.randint(4, 30)
    return img


BG_STREET = make_bg(NIGHT, (0.68, 0.40), 0.26, skyline=True)
BG_DESK = make_bg(ASPHALT, (0.5, 0.35), 0.16)
BG_BOARD = make_bg((40, 31, 22), (0.5, 0.4), 0.12)
BG_END = make_bg(NIGHT, (0.30, 0.45), 0.24)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = (1 - 0.55 * np.clip(np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 +
                                        ((yy - H / 2) / (H * 0.62)) ** 2) - 0.35, 0, 1))[..., None]
del yy, xx
_rng = np.random.default_rng(3)
GRAIN = [_rng.integers(-9, 10, (H, W, 1), dtype=np.int16) for _ in range(3)]


def rain(d, fr, n=150, alpha=(110, 125, 150)):
    for i in range(n):
        sx = (i * 197.3) % (W + 400)
        sy = (i * 131.7) % H
        speed = 38 + (i % 7) * 6
        x = (sx - fr * speed * 0.35) % (W + 400) - 200
        y = (sy + fr * speed) % (H + 200) - 100
        d.line((x, y, x - 10, y + 34), fill=alpha, width=2)


# ----------------------------------------------------------------- props
def page_sprite(title_w=70):
    im = Image.new("RGBA", (140, 176), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, 136, 172), radius=6, fill=WHITE + (255,), outline=INK + (255,),
                        width=4)
    d.rectangle((18, 22, 18 + title_w, 34), fill=RED + (255,))
    for yy in range(50, 160, 16):
        d.line((18, yy, 120 - (yy % 3) * 10, yy), fill=(150, 140, 120, 255), width=4)
    return im


PAGES = [page_sprite(40 + 10 * (i % 5)).rotate(a, resample=Image.BICUBIC, expand=True)
         for i, a in enumerate((-24, -12, -4, 6, 14, 26, 34, -32))]


def card(d, box, fr, seed, fill=MANILA, outline=INK, width=4):
    jrect(d, box, fill, outline, width, fr, seed)


# ----------------------------------------------------------------- scenes
def s1_cold_open(fr, t, img, d):  # 0 - 3.2
    img.paste(BG_STREET)
    rain(d, fr, 170)
    # agent into the spotlight
    a = smooth(seg(t, 1.1, 2.0))
    put(img, PORTRAIT, 1320, 520 + (1 - a) * 60, 1.55 + 0.1 * t / 3.2, a)
    x0 = 150
    t1 = typed(T_LINE1[1], t, T_LINE1[0], T_LINE1[2])
    if t1:
        put(img, text_img(t1, TYPE[56], MANILA, rot=jrot(fr, 0.3)), x0, 300, anchor="tl")
    t2 = typed(T_LINE2[1], t, T_LINE2[0], T_LINE2[2])
    if t2:
        put(img, text_img(t2, TYPE[48], CHROME, rot=jrot(fr, 0.3)), x0, 400, anchor="tl")
    return 1.0 + 0.05 * seg(t, 0, 3.2)


def s2_title(fr, t, img, d):  # 3.2 - 6.0
    img.paste(BG_DESK)
    lt = t - 3.2
    x = 1470 + (1 - back(seg(lt, 0, 0.45))) * 900
    put(img, BADGE, x, 540, 1.65)
    a = seg(lt, 0.3, 0.55)
    put(img, text_img("HE'S BIG ON", DISP[150], CHROME, 6, INK, jrot(fr, 0.4)), 600, 380, 1, a)
    s = stamp_scale(t, 4.1)
    if s:
        put(img, text_img("DETAIL.", DISP[210], RED2, 8, INK, jrot(fr, 0.5)), 600, 610, s)
    return 1.0 + 0.04 * seg(lt, 0, 2.8)


WEEKS = [23362, 25829, 24366, 24931, 25969, 23417, 21912, 29777, 31067, 28745, 13917, 1174,
         1142, 1103, 743]


def s3_case(fr, t, img, d):  # 6.0 - 10.4
    img.paste(BG_DESK)
    lt = t - 6.0
    # chart card
    box = (160, 170, 1260, 900)
    card(d, box, fr, 31)
    put(img, text_img("IMPRESSIONS PER WEEK", TYPE[36], INK), box[0] + 40, box[1] + 30,
        anchor="tl")
    x0, y0, x1, y1 = box[0] + 60, box[1] + 110, box[2] - 50, box[3] - 70
    jline(d, (x0, y1), (x1, y1), INK, 4, fr, 1)
    n = len(WEEKS)
    slot = (x1 - x0) / n
    grow = smooth(seg(lt, 0.25, 1.2))
    drop = smooth(seg(lt, 1.7, 2.2))
    for i, v in enumerate(WEEKS):
        full = v / 32000 * (y1 - y0)
        if i >= 10:
            pre = 27000 / 32000 * (y1 - y0)
            hgt = (pre + (full - pre) * drop) * grow
            col = RED if drop > 0.5 else INK
        else:
            hgt = full * grow
            col = INK
        bx = x0 + i * slot + slot * 0.18
        if hgt > 1:
            d.rectangle((bx, y1 - hgt, bx + slot * 0.64, y1), fill=col)
    # update marker
    if lt > 1.6:
        mx = x0 + 10 * slot + slot / 7
        for yy in range(int(y0 - 20), int(y1), 22):
            d.line((mx, yy, mx, yy + 12), fill=RED, width=4)
        put(img, text_img("18 AUG: SPAM UPDATE", TYPE[32], RED), mx - 20, y0 - 50, anchor="tl")
    # calendar
    s = stamp_scale(t, 6.15)
    if s:
        cal = Image.new("RGBA", (300, 320), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cal)
        cd.rounded_rectangle((10, 10, 290, 310), radius=10, fill=WHITE + (255,),
                             outline=INK + (255,), width=6)
        cd.rectangle((10, 10, 290, 90), fill=RED + (255,))
        cd.text((150, 50), "AUG", font=DISP[56], fill=WHITE, anchor="mm")
        cd.text((150, 205), "18", font=DISP[150], fill=INK, anchor="mm")
        put(img, cal.rotate(6, resample=Image.BICUBIC, expand=True), 1560, 330, s)
    # big numbers
    a = seg(lt, 2.4, 2.7)
    if a:
        put(img, text_img("29,000", DISP[120], CHROME, 5, INK), 1560, 640, 1, a)
        put(img, text_img("1,100", DISP[120], RED2, 5, INK, jrot(fr, 0.6)), 1560, 800,
            stamp_scale(t, 8.6) or 0.001)
        put(img, text_img("to", TYPE[40], DIM), 1560, 722, 1, a)
    # lightning flash handled in post
    shake = 1.0 + 0.06 * seg(lt, 0, 4.4)
    return shake


def s4_crawl(fr, t, img, d):  # 10.4 - 14.0
    img.paste(BG_DESK)
    lt = t - 10.4
    for i in range(26):
        sp = PAGES[i % len(PAGES)]
        speed = 520 + (i * 53) % 380
        x = W + 200 - ((lt * speed + i * 173) % (W + 500))
        y = 120 + (i * 97) % (H - 260) + math.sin(lt * 3 + i) * 30
        put(img, sp, x, y, 0.8 + (i % 3) * 0.15)
    bob = math.sin(lt * 5) * 8
    put(img, PORTRAIT, 330, 640 + bob, 1.45)
    put(img, text_img("EVERY PAGE. EVERY LINK.", DISP[88], CHROME, 5, INK, jrot(fr, 0.4)),
        1180, 250, 1, seg(lt, 0.15, 0.4))
    n = int(23 * seg(t, 11.2, 12.4))
    if t >= 11.2:
        put(img, text_img(str(n), DISP[300], RED2, 8, INK, jrot(fr, 0.5)), 900, 610)
        put(img, text_img("AUDIT MODULES", DISP[72], CHROME, 4, INK), 1470, 640, 1,
            seg(t, 11.3, 11.5))
    a = seg(t, 12.8, 13.1)
    if a:
        put(img, text_img("Google's rules, current to Sept 2026", TYPE[48], MANILA), 1180, 860,
            1, a)
    return 1.0 + 0.05 * seg(lt, 0, 3.6)


SUBURBS = ["CARLTON", "FITZROY", "RICHMOND", "KEW", "COBURG", "ST KILDA", "BONDI", "MANLY",
           "COOGEE", "NEW FARM", "SUBIACO", "HOBART", "NEWTOWN", "TOORAK", "BRUNSWICK",
           "ASCOT", "HAWTHORN", "MOSMAN"]


def s5_doorway(fr, t, img, d):  # 14.0 - 19.0
    img.paste(BG_DESK)
    lt = t - 14.0
    cols, rows = 5, 3
    cw, ch, gx, gy = 300, 190, 36, 34
    ox = (W - (cols * cw + (cols - 1) * gx)) / 2
    oy = 190
    fall = seg(lt, 2.0, 2.8)
    for r in range(rows):
        for c in range(cols):
            k = r * cols + c
            appear = seg(lt, k * 0.03, k * 0.03 + 0.2)
            if appear <= 0:
                continue
            x = ox + c * (cw + gx)
            y = oy + r * (ch + gy) + (1 - back(appear)) * 60
            y += fall * fall * (500 + k * 40) if fall else 0
            if y > H:
                continue
            card(d, (x, y, x + cw, y + ch), fr, 50 + k, fill=WHITE, width=3)
            name = SUBURBS[(k + int(lt * 6)) % len(SUBURBS)]
            put(img, text_img("SEO AGENCY IN", TYPE[24], INK), x + 18, y + 16, anchor="tl")
            put(img, text_img(name, DISP[40], RED), x + 18, y + 44, anchor="tl")
            for li in range(3):
                ly = y + 110 + li * 22
                d.line((x + 18, ly, x + cw - 30 - li * 40, ly), fill=(150, 140, 120), width=5)
    cap = seg(lt, 0.6, 0.9)
    if cap and lt < 2.2:
        put(img, text_img("SAME PAGE. DIFFERENT SUBURB.", DISP[64], CHROME, 4, INK,
                          jrot(fr, 0.4)), W / 2, 110, 1, cap)
    # magnifier sweep
    if 0.6 < lt < 2.1:
        m = smooth(seg(lt, 0.6, 2.0))
        mx, my = 380 + m * 1150, 420 + math.sin(m * 6) * 120
        d.ellipse((mx - 95, my - 95, mx + 95, my + 95), outline=INK, width=16)
        d.ellipse((mx - 88, my - 88, mx + 88, my + 88), outline=CHROME, width=5)
        d.line((mx + 66, my + 66, mx + 170, my + 170), fill=INK, width=28)
        put(img, PORTRAIT, mx + 250, my + 260, 0.8)
    s = stamp_scale(t, 16.2)
    if s:
        put(img, stamp_img("674 TEMPLATED PAGES", RED, 80, -6), W / 2, 330, s)
    if t >= 17.0:
        for i, (lab, num, col, at, big) in enumerate((
                ("KEEP", "41", CHROME, 17.0, False), ("IMPROVE", "150", MANILA, 17.3, False),
                ("PRUNE", "468", RED2, 17.6, True))):
            s = stamp_scale(t, at)
            if not s:
                continue
            cx = W / 2 + (i - 1) * 470
            b = Image.new("RGBA", (400, 230), (0, 0, 0, 0))
            bd = ImageDraw.Draw(b)
            bd.rounded_rectangle((8, 8, 392, 222), radius=10, fill=(20, 23, 30, 240),
                                 outline=col + (255,), width=8)
            bd.text((200, 100), num, font=DISP[120], fill=col, anchor="mm")
            bd.text((200, 190), lab, font=TYPE[40], fill=col, anchor="mm")
            put(img, b, cx, 700, s * (1.12 if big else 1.0))
    return 1.0 + 0.05 * seg(lt, 0, 5.0)


def s6_board(fr, t, img, d):  # 19.0 - 23.0
    img.paste(BG_BOARD)
    lt = t - 19.0
    cards = [((220, 170), "BROKEN LINKS", "P0", 20.5, (200, 16, 46)),
             ((1060, 140), "DOORWAY PAGES", "P1", 20.8, (217, 83, 30)),
             ((330, 590), "SPAM UPDATE HIT", "P1", 21.1, (217, 83, 30)),
             ((1120, 560), "AI SEARCH GAPS", "P2", 21.1, (176, 125, 18))]
    pins = []
    for i, ((x, y), lab, pr, at, col) in enumerate(cards):
        a = seg(lt, 0.1 + i * 0.1, 0.3 + i * 0.1)
        if not a:
            continue
        yy = y + (1 - back(a)) * -80
        card(d, (x, yy, x + 560, yy + 300), fr, 70 + i)
        put(img, text_img(lab, DISP[40], INK, rot=jrot(fr, 0.3)), x + 40, yy + 60, anchor="tl")
        for li in range(3):
            ly = yy + 170 + li * 30
            d.line((x + 40, ly, x + 360 - li * 60, ly), fill=(120, 100, 64), width=6)
        px, py = x + 280, yy + 18
        d.ellipse((px - 14, py - 14, px + 14, py + 14), fill=RED, outline=INK, width=3)
        pins.append((px, py))
        s = stamp_scale(t, at)
        if s:
            put(img, stamp_img(pr, col, 80, -10), x + 460, yy + 225, s)
    # red string, drawn progressively
    order = [(0, 1), (1, 3), (3, 2), (2, 0), (0, 3)]
    prog = seg(lt, 0.5, 1.4) * len(order)
    for k, (a, b) in enumerate(order):
        if k >= prog or a >= len(pins) or b >= len(pins):
            continue
        f = clamp(prog - k)
        p1, p2 = pins[a], pins[b]
        p2 = (p1[0] + (p2[0] - p1[0]) * f, p1[1] + (p2[1] - p1[1]) * f)
        jline(d, p1, p2, RED2, 6, fr, 90 + k, amp=4)
    put(img, SECRET, 1740, 900, 0.62)
    a = seg(t, 21.5, 21.8)
    if a:
        put(img, text_img("1,090 TESTS PASSING", DISP[88], CHROME, 5, INK, jrot(fr, 0.4)),
            820, 985, 1, a)
    return 1.0 + 0.05 * seg(lt, 0, 4.0)


def s7_fat(fr, t, img, d):  # 23.0 - 26.2
    img.paste(BG_DESK)
    for i, (L, word, at) in enumerate((("F", "FIX", 23.2), ("A", "AUDIT", 23.6),
                                       ("T", "TEST", 24.0))):
        s = stamp_scale(t, at)
        if not s:
            continue
        cx = W / 2 + (i - 1) * 520
        put(img, text_img(L, DISP[300], CHROME, 10, INK, jrot(fr, 0.8)), cx, 470, s)
        put(img, text_img(word, TYPE[64], MANILA), cx, 700, 1, seg(t, at + 0.05, at + 0.2))
    s = stamp_scale(t, 24.8)
    if s:
        put(img, stamp_img("CASE CLOSED", RED, 96, -9), W / 2, 540, s * 1.35)
    return 1.0 + 0.06 * seg(t, 23.0, 26.2)


def s8_end(fr, t, img, d):  # 26.2 - 30.0
    img.paste(BG_END)
    rain(d, fr, 70, (60, 68, 84))
    lt = t - 26.2
    put(img, BADGE, 470, 540, 1.65 * (0.7 + 0.3 * back(seg(lt, 0, 0.5))), seg(lt, 0, 0.25))
    x0 = 880
    tt = typed(T_END_TYPE[1], t, T_END_TYPE[0], T_END_TYPE[2])
    if tt:
        put(img, text_img(tt, DISP[88], CHROME, 5, INK), x0, 250, anchor="tl")
    s = stamp_scale(t, 27.8)
    if s:
        im = text_img("He's thorough.", DISP[88], RED2, 5, INK, jrot(fr, 0.5))
        put(img, im, x0 + im.width / 2, 440, s)
    a = seg(t, 28.4, 28.7)
    if a:
        bx = Image.new("RGBA", (920, 96), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bx)
        bd.rounded_rectangle((0, 0, 919, 95), radius=10, fill=(27, 31, 39, 255),
                             outline=(52, 58, 70, 255), width=3)
        bd.text((28, 48), "/plugin marketplace add spruikco/fat-agent-skill", font=MONO[30],
                fill=MANILA, anchor="lm")
        put(img, bx, x0, 640, 1, a, anchor="tl")
        put(img, text_img("Free for Claude Code. No API key required.", TYPE[40], DIM), x0, 770,
            1, seg(t, 28.7, 29.0), anchor="tl")
        put(img, text_img("FAT AGENT.  FIX. AUDIT. TEST.", DISP[40], MANILA, 3, INK), x0, 850,
            1, seg(t, 28.9, 29.2), anchor="tl")
    return 1.0 + 0.04 * seg(lt, 0, 3.8)


SCENE_FNS = [s1_cold_open, s2_title, s3_case, s4_crawl, s5_doorway, s6_board, s7_fat, s8_end]


# ----------------------------------------------------------------- compositor
def render_frame(fr):
    t = fr / FPS
    idx = max(i for i, (a, b) in enumerate(SCENES) if t >= a)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    zoom = SCENE_FNS[idx](fr, t, img, d)
    # camera shake on stamps
    sx = sy = 0.0
    for at in EV["thunk"] + EV["bigthunk"] + EV["thunder"]:
        if 0 <= t - at < 0.18:
            k = (1 - (t - at) / 0.18) * (18 if at in EV["bigthunk"] + EV["thunder"] else 9)
            sx += math.sin(fr * 12.9) * k
            sy += math.cos(fr * 7.3) * k
    # whip pan into each new scene
    for at in EV["whoosh"]:
        if 0 <= t - at < 0.14:
            sx += (1 - (t - at) / 0.14) ** 2 * 260
    if abs(zoom - 1) > 1e-3 or sx or sy:
        cw, chh = W / zoom, H / zoom
        cx, cy = W / 2 - sx, H / 2 - sy
        box = (cx - cw / 2, cy - chh / 2, cx + cw / 2, cy + chh / 2)
        img = img.transform((W, H), Image.EXTENT, box, Image.BILINEAR)
    arr = np.asarray(img, dtype=np.int16)
    arr = arr + GRAIN[boil(fr) % 3]
    arr = arr.astype(np.float32) * VIGNETTE
    # lightning flash
    for at in EV["thunder"]:
        if 0 <= t - at < 0.35:
            f = (1 - (t - at) / 0.35) ** 2 * (1.0 if (fr % 3) else 0.6)
            arr = arr * (1 - f * 0.85) + 255 * f * 0.85
    # fade in / out
    fade = min(seg(t, 0, 0.35), 1 - seg(t, DUR - 0.45, DUR))
    arr *= fade
    return np.clip(arr, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------- audio
SR = 44100


def audio():
    n = int(SR * DUR)
    out = np.zeros(n, np.float32)
    rng = np.random.default_rng(11)

    def place(sig, at, gain):
        i = int(at * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        out[i:j] += sig[: j - i] * gain

    def tt(d):
        return np.arange(int(SR * d)) / SR

    def lp(x, k):
        return np.convolve(x, np.ones(k) / k, mode="same") if k > 1 else x

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def pulse(freq, d, duty=0.5):
        t = tt(d)
        return np.where((t * freq) % 1 < duty, 1.0, -1.0).astype(np.float32)

    # rain bed
    r = lp(rng.standard_normal(n).astype(np.float32), 5)
    lvl = np.interp(np.arange(n) / SR, [0, 3.0, 3.6, 26, 27, 30], [0.10, 0.10, 0.035, 0.035, 0.07, 0.0])
    out += r * lvl

    # music: 120 bpm swing, C minor walking bass, from 3.2 to 29.2
    beat = 0.5
    walk = [36, 39, 41, 43, 44, 43, 41, 39, 41, 44, 46, 48, 46, 44, 43, 39]
    k = 0
    tb = 3.2
    while tb < 29.2:
        f = hz(walk[k % len(walk)])
        s = lp(pulse(f, beat * 0.95), 18)
        s *= np.exp(-tt(beat * 0.95) * 4.5)
        place(s, tb, 0.20)
        # swung brush hats
        for off, g in ((0.0, 0.035), (0.33, 0.05)):
            hs = rng.standard_normal(int(SR * 0.035)).astype(np.float32)
            hs = (hs - lp(hs, 6)) * np.exp(-tt(0.035) * 90)
            place(hs, tb + off, g)
        if k % 2 == 0:  # soft kick
            kt = tt(0.18)
            kick = np.sin(2 * np.pi * (58 * kt - 30 * kt ** 2)) * np.exp(-kt * 22)
            place(kick.astype(np.float32), tb, 0.28)
        tb += beat
        k += 1

    # 8-bit lead motif
    motif = [(67, .25), (68, .25), (67, .25), (65, .25), (63, .5), (62, .25), (60, .75)]
    for at in EV["motif"]:
        x = at
        for m, dd in motif:
            s = pulse(hz(m), dd * 0.9, 0.25) * np.exp(-tt(dd * 0.9) * 2.2)
            place(s, x, 0.075)
            x += dd
    # triumphant stinger (major arpeggio) on CASE CLOSED
    for at in EV["stinger"]:
        for i, m in enumerate((72, 76, 79, 84)):
            s = pulse(hz(m), 0.6, 0.25) * np.exp(-tt(0.6) * 3)
            place(s, at + i * 0.07, 0.08)
    # end chord
    for m in (48, 60, 63, 67):
        s = lp(pulse(hz(m), 1.4, 0.5), 10) * np.exp(-tt(1.4) * 1.8)
        place(s, 29.0, 0.06)

    # typewriter clicks + bells
    def click(at, g=0.22):
        c = rng.standard_normal(int(SR * 0.012)).astype(np.float32)
        c = (c - lp(c, 4)) * np.exp(-tt(0.012) * 300)
        place(c, at, g)

    for start, txt, rate in (T_LINE1, T_LINE2, T_END_TYPE):
        for i, ch in enumerate(txt):
            if ch != " ":
                click(start + i * rate)
        bell = np.sin(2 * np.pi * 1850 * tt(0.5)) * np.exp(-tt(0.5) * 9)
        place(bell.astype(np.float32), start + len(txt) * rate + 0.05, 0.10)

    # module counter ticks
    a, b, cnt = EV["ticks"]
    for i in range(cnt):
        click(a + (b - a) * i / cnt, 0.16)

    # stamps
    def thunk(at, g):
        kt = tt(0.22)
        body = np.sin(2 * np.pi * (95 * kt - 70 * kt ** 2)) * np.exp(-kt * 18)
        slap = lp(rng.standard_normal(len(kt)).astype(np.float32), 3) * np.exp(-kt * 60)
        place((body * 0.9 + slap * 0.5).astype(np.float32), at, g)

    for at in EV["thunk"]:
        thunk(at, 0.55)
    for at in EV["bigthunk"]:
        thunk(at, 0.85)

    # thunder
    for at in EV["thunder"]:
        crack = rng.standard_normal(int(SR * 0.12)).astype(np.float32)
        crack = (crack - lp(crack, 8)) * np.exp(-tt(0.12) * 25)
        place(crack, at, 0.45)
        rum = lp(rng.standard_normal(int(SR * 2.2)).astype(np.float32), 90) * 6
        envr = np.minimum(1, tt(2.2) / 0.08) * np.exp(-tt(2.2) * 1.6)
        place((rum * envr).astype(np.float32), at + 0.02, 0.55)

    # whooshes
    for at in EV["whoosh"]:
        d = 0.4
        w = lp(rng.standard_normal(int(SR * d)).astype(np.float32), 4)
        envw = np.sin(np.pi * np.clip(tt(d) / d, 0, 1)) ** 2
        place((w * envw).astype(np.float32), at - 0.12, 0.22)

    # master: soft clip, normalise, fades
    out = np.tanh(out * 1.2)
    out /= max(1e-6, np.abs(out).max()) / 0.89
    out *= np.minimum(1, np.arange(n) / (SR * 0.2))
    fo = np.clip((DUR - np.arange(n) / SR) / 0.5, 0, 1)
    out *= fo
    return (out * 32767).astype(np.int16)


def write_wav(path):
    pcm = audio()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ----------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    if "--preview" in args:
        times = [float(x) for x in args[args.index("--preview") + 1].split(",")]
        thumbs = [Image.fromarray(render_frame(int(t * FPS))).resize((640, 360)) for t in times]
        cols = 3
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 640, rows * 380), (0, 0, 0))
        d = ImageDraw.Draw(sheet)
        for i, th in enumerate(thumbs):
            x, y = (i % cols) * 640, (i // cols) * 380
            sheet.paste(th, (x, y + 20))
            d.text((x + 6, y + 2), f"t={times[i]}s", fill=(255, 80, 80))
        sheet.save(os.path.join(HERE, "promo_preview.jpg"), quality=80)
        print("preview written")
        return
    out = args[args.index("--out") + 1] if "--out" in args else os.path.join(HERE, "fat-agent-promo.mp4")
    wav = os.path.join(HERE, "promo_audio.wav")
    write_wav(wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
           "-tune", "animation", "-c:a", "aac", "-b:a", "128k", "-shortest",
           "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in range(NF):
        p.stdin.write(render_frame(fr).tobytes())
        if fr % 150 == 0:
            print(f"frame {fr}/{NF}", flush=True)
    p.stdin.close()
    p.wait()
    print("done", out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main()
