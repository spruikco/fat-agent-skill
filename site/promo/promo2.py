"""FAT Agent promo v2: slower, investigative e-commerce case (illustrative), ~50s.

Reuses the drawing helpers, fonts and art from promo.py.
Usage: python promo2.py [--preview t1,t2,...] [--out file.mp4]
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import promo as P
from promo import (BADGE, CHROME, DIM, DISP, INK, MANILA, MONO, NIGHT, PORTRAIT, RED, RED2,
                   SECRET, TYPE, WHITE, W, H, FPS, back, boil, card, clamp, jline, jrot, put,
                   seg, smooth, stamp_img, stamp_scale, text_img, typed)

DUR = 50.0
NF = int(FPS * DUR)

# ----------------------------------------------------------------- timeline
TYPED = [  # (start, text, rate, font-size, colour, x, y)
    (0.5, "AN ONLINE STORE WENT QUIET.", 0.06, 56, MANILA, 150, 280),
    (2.5, "ORGANIC SALES DOWN 62%. NOBODY KNEW WHY.", 0.045, 48, CHROME, 150, 380),
    (4.7, "SOMEBODY CALLED THE FAT AGENT.", 0.04, 48, CHROME, 150, 460),
]
EXHIBITS = [(10.7, "EXHIBIT A: THE SCENE"), (17.7, "EXHIBIT B: THE SWEEP"),
            (23.7, "EXHIBIT C: THE LINEUP"), (33.2, "EXHIBIT D: THE BOARD")]
END_TYPE = (42.8, "He's not fat.", 0.07)
SCENES = [(0.0, 6.5), (6.5, 10.5), (10.5, 17.5), (17.5, 23.5), (23.5, 33.0),
          (33.0, 38.0), (38.0, 42.0), (42.0, 50.0)]
EV = {
    "whoosh": [6.5, 10.5, 17.5, 23.5, 33.0, 38.0, 42.0],
    "thunk": [7.5, 12.6, 14.6, 24.2, 24.6, 25.0, 25.4, 34.6, 34.9, 35.2, 38.3, 38.9, 39.5,
              44.2],
    "bigthunk": [30.0, 35.5, 40.4],
    "thunder": [13.4],
    "ticks": (18.6, 20.2, 32),
    "stinger": [40.45],
    "motif": [7.0, 42.3],
}
ILLUSTRATIVE = (10.5, 38.0)
RINGS = [(3.9, 0.85), (5.05, 0.85)]  # (start, length): old bell phone, two rings
FADE = 0.3  # dip-to-black between scenes (seconds of source time)


def TW(x):  # time warp for audio events (identity here; promo3 slows scenes)
    return x


def exhibit_label(img, fr, t):
    for at, txt in EXHIBITS:
        if at <= t < at + 5.5:
            s = typed(txt, t, at, 0.045)
            if s:
                put(img, text_img(s, TYPE[40], MANILA, rot=jrot(fr, 0.2)), 110, 70, anchor="tl")
    if ILLUSTRATIVE[0] <= t < ILLUSTRATIVE[1]:
        put(img, text_img("ILLUSTRATIVE CASE", TYPE[24], DIM), W - 280, 90)


# ----------------------------------------------------------------- scenes
_GLOW = None


def draw_phone(img, fr, t):
    """A black rotary desk phone that rattles while it rings."""
    ringing = any(a <= t < a + ln for a, ln in RINGS)
    shake = (np.sin(fr * 2.7) * 6, np.cos(fr * 3.3) * 3) if ringing else (0, 0)
    ph = Image.new("RGBA", (340, 260), (0, 0, 0, 0))
    pd = ImageDraw.Draw(ph)
    ink, hi = (20, 21, 26, 255), (150, 156, 168, 255)
    pd.polygon([(40, 250), (300, 250), (262, 120), (78, 120)], fill=ink, outline=hi)
    pd.ellipse((118, 138, 222, 242), fill=(28, 30, 36, 255), outline=hi, width=3)
    for k in range(10):
        ang = math.radians(200 + k * 25)
        cx, cy = 170 + math.cos(ang) * 34, 190 + math.sin(ang) * 34
        pd.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=(12, 12, 14, 255), outline=hi)
    pd.ellipse((158, 178, 182, 202), fill=(200, 16, 46, 255))
    lift = -10 if ringing and (fr // 2) % 2 else 0
    pd.rounded_rectangle((30, 70 + lift, 310, 108 + lift), radius=18, fill=ink, outline=hi, width=3)
    pd.ellipse((14, 58 + lift, 88, 120 + lift), fill=ink, outline=hi, width=3)
    pd.ellipse((252, 58 + lift, 326, 120 + lift), fill=ink, outline=hi, width=3)
    cx0, cy0 = 400, 800
    global _GLOW
    if _GLOW is None:  # soft warm pool of light behind the phone (built once)
        _GLOW = Image.new("RGBA", (1000, 760), (232, 213, 163, 0))
        ImageDraw.Draw(_GLOW).ellipse((200, 170, 800, 590), fill=(232, 213, 163, 80))
        _GLOW = _GLOW.filter(ImageFilter.GaussianBlur(80))
    glow = _GLOW
    put(img, glow, cx0, cy0 + 40)
    put(img, ph.rotate(shake[0] * 0.6, resample=Image.BICUBIC, expand=True),
        cx0 + shake[0], cy0 + shake[1])
    if ringing:
        d = ImageDraw.Draw(img)
        for k in range(3):
            r = 150 + k * 34 + (fr % 6) * 4
            for side in (-1, 1):
                a0 = -60 if side > 0 else 180 - 20
                d.arc((cx0 - r, cy0 - 40 - r, cx0 + r, cy0 - 40 + r), a0, a0 + 40,
                      fill=RED2, width=6)
        put(img, text_img("RING", DISP[64], RED2, 4, INK, jrot(fr, 3)), cx0, cy0 - 250)


def s1(fr, t, img, d):
    img.paste(P.BG_STREET)
    P.rain(d, fr, 170)
    a = smooth(seg(t, 3.9, 5.0))
    put(img, PORTRAIT, 1560, 560 + (1 - a) * 60, 1.3 + 0.06 * t / 6.5, a)
    draw_phone(img, fr, t)
    for start, txt, rate, size, col, x, y in TYPED:
        s = typed(txt, t, start, rate)
        if s:
            put(img, text_img(s, TYPE[size], col, rot=jrot(fr, 0.3)), x, y, anchor="tl")
    return 1.0 + 0.04 * seg(t, 0, 6.5)


def s2(fr, t, img, d):
    img.paste(P.BG_DESK)
    lt = t - 6.5
    x = 1470 + (1 - back(seg(lt, 0, 0.55))) * 900
    put(img, BADGE, x, 540, 1.65)
    put(img, text_img("HE'S BIG ON", DISP[150], CHROME, 6, INK, jrot(fr, 0.4)), 600, 380, 1,
        seg(lt, 0.4, 0.7))
    s = stamp_scale(t, 7.5)
    if s:
        put(img, text_img("DETAIL.", DISP[210], RED2, 8, INK, jrot(fr, 0.5)), 600, 610, s)
    return 1.0 + 0.03 * seg(lt, 0, 4.0)


SALES = [410, 432, 398, 445, 460, 452, 470, 488, 501, 476, 302, 176, 168, 172, 160]


def s3(fr, t, img, d):
    img.paste(P.BG_DESK)
    lt = t - 10.5
    box = (160, 190, 1180, 920)
    card(d, box, fr, 31)
    put(img, text_img("ORGANIC ORDERS PER WEEK", TYPE[36], INK), box[0] + 40, box[1] + 30,
        anchor="tl")
    x0, y0, x1, y1 = box[0] + 60, box[1] + 110, box[2] - 50, box[3] - 70
    jline(d, (x0, y1), (x1, y1), INK, 4, fr, 1)
    n = len(SALES)
    slot = (x1 - x0) / n
    grow = smooth(seg(t, 11.2, 12.2))
    drop = smooth(seg(t, 13.5, 14.1))
    for i, v in enumerate(SALES):
        full = v / 540 * (y1 - y0)
        if i >= 10:
            pre = 470 / 540 * (y1 - y0)
            hgt = (pre + (full - pre) * drop) * grow
            col = RED if drop > 0.5 else INK
        else:
            hgt, col = full * grow, INK
        bx = x0 + i * slot + slot * 0.18
        if hgt > 1:
            d.rectangle((bx, y1 - hgt, bx + slot * 0.64, y1), fill=col)
    if t > 13.4:
        mx = x0 + 10 * slot + slot / 7
        for yy in range(int(y0 - 20), int(y1), 22):
            d.line((mx, yy, mx, yy + 12), fill=RED, width=4)
        put(img, text_img("18 AUG: SPAM UPDATE", TYPE[32], RED), mx - 20, y0 - 50, anchor="tl")
    s = stamp_scale(t, 12.6)
    if s:
        cal = Image.new("RGBA", (300, 320), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cal)
        cd.rounded_rectangle((10, 10, 290, 310), radius=10, fill=WHITE + (255,),
                             outline=INK + (255,), width=6)
        cd.rectangle((10, 10, 290, 90), fill=RED + (255,))
        cd.text((150, 50), "AUG", font=DISP[56], fill=WHITE, anchor="mm")
        cd.text((150, 205), "18", font=DISP[150], fill=INK, anchor="mm")
        put(img, cal.rotate(6, resample=Image.BICUBIC, expand=True), 1560, 360, s)
    s = stamp_scale(t, 14.6)
    if s:
        put(img, text_img("-62%", DISP[150], RED2, 8, INK, jrot(fr, 0.6)), 1540, 700, s)
    a = seg(t, 15.0, 15.4)
    if a:
        put(img, text_img("SALES FELL OFF A CLIFF.", TYPE[40], MANILA), 1540, 850, 1, a)
    exhibit_label(img, fr, t)
    return 1.0 + 0.04 * seg(lt, 0, 7.0)


def s4(fr, t, img, d):
    img.paste(P.BG_DESK)
    lt = t - 17.5
    for i in range(22):
        sp = P.PAGES[i % len(P.PAGES)]
        speed = 360 + (i * 53) % 300
        x = W + 200 - ((lt * speed + i * 173) % (W + 500))
        y = 170 + (i * 97) % (H - 300) + math.sin(lt * 2.4 + i) * 26
        put(img, sp, x, y, 0.8 + (i % 3) * 0.15, 0.5)
    put(img, PORTRAIT, 330, 660 + math.sin(lt * 3.2) * 8, 1.45)
    plate = Image.new("RGBA", (1000, 560), (16, 19, 25, 200))
    put(img, plate, 1100, 640, 1, seg(t, 18.5, 18.8))
    put(img, text_img("EVERY PAGE. EVERY LINK.", DISP[88], CHROME, 5, INK, jrot(fr, 0.4)),
        1180, 260, 1, seg(t, 18.0, 18.35))
    if t >= 18.6:
        n = int(4812 * smooth(seg(t, 18.6, 20.2)))
        put(img, text_img(f"{n:,}", DISP[210], RED2, 8, INK, jrot(fr, 0.5)), 1100, 540)
        put(img, text_img("PAGES CRAWLED", DISP[64], CHROME, 4, INK), 1100, 700, 1,
            seg(t, 18.8, 19.1))
    a = seg(t, 20.8, 21.2)
    if a:
        put(img, text_img("23 AUDIT MODULES ON EVERY ONE", TYPE[48], MANILA), 1100, 840, 1, a)
    exhibit_label(img, fr, t)
    return 1.0 + 0.04 * seg(lt, 0, 6.0)


SUSPECTS = [("3,400", "DUPLICATE", "FILTER PAGES"), ("1,200", "COPIED", "PRODUCT COPY"),
            ("212", "PRODUCTS WITH", "NO PRICE"), ("38", "DEAD CHECKOUT", "LINKS")]
LINEUP_X = [330, 750, 1170, 1590]


def lineup_bg(d):
    for k, y in enumerate(range(200, 860, 110)):
        d.line((60, y, W - 60, y), fill=(58, 64, 76), width=3)
        d.text((70, y - 34), f"{7 - k}FT", font=TYPE[28], fill=(96, 104, 118))


def s5(fr, t, img, d):
    img.paste(P.BG_DESK)
    lineup_bg(d)
    for i, ((num, l1, l2), cx, at) in enumerate(zip(SUSPECTS, LINEUP_X,
                                                     (24.2, 24.6, 25.0, 25.4))):
        s = stamp_scale(t, at)
        if not s:
            continue
        b = Image.new("RGBA", (360, 400), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b)
        bd.rounded_rectangle((6, 6, 354, 394), radius=8, fill=(14, 15, 18, 255),
                             outline=(210, 210, 200, 255), width=5)
        bd.text((180, 52), f"SUSPECT {i + 1}", font=TYPE[32], fill=(200, 200, 190), anchor="mm")
        bd.line((40, 88, 320, 88), fill=(120, 120, 110), width=2)
        bd.text((180, 185), num, font=DISP[100], fill=WHITE, anchor="mm")
        bd.text((180, 290), l1, font=TYPE[32], fill=(225, 225, 215), anchor="mm")
        bd.text((180, 335), l2, font=TYPE[32], fill=(225, 225, 215), anchor="mm")
        put(img, b.rotate([-2, 1.5, -1, 2][i], resample=Image.BICUBIC, expand=True), cx, 520,
            min(s, 1.25))
    if t >= 30.0:
        s = stamp_scale(t, 30.0)
        put(img, stamp_img("GUILTY", RED, 80, -14), LINEUP_X[0], 690, s)
    a = seg(t, 30.8, 31.2)
    if a:
        put(img, text_img("IT'S ALWAYS THE DUPLICATES.", DISP[72], CHROME, 5, INK,
                          jrot(fr, 0.4)), W / 2, 900, 1, a)
    put(img, PORTRAIT, 150, 930, 0.85)
    exhibit_label(img, fr, t)
    return 1.0 + 0.04 * seg(t, 23.5, 33.0)


def lineup_spot(t):
    """Flashlight position for the lineup (None = lights up)."""
    if not (25.9 <= t < 30.0):
        return None
    k = smooth(seg(t, 26.0, 29.6))
    path = [(LINEUP_X[3], 520), (LINEUP_X[2], 470), (LINEUP_X[1], 560), (LINEUP_X[0], 520)]
    f = k * (len(path) - 1)
    i = min(int(f), len(path) - 2)
    u = smooth(f - i)
    x = path[i][0] + (path[i + 1][0] - path[i][0]) * u
    y = path[i][1] + (path[i + 1][1] - path[i][1]) * u
    return x, y


def s6(fr, t, img, d):
    img.paste(P.BG_BOARD)
    lt = t - 33.0
    cards = [((220, 190), "DUPLICATE PAGES", "P1", 34.6, (217, 83, 30)),
             ((1060, 160), "COPIED COPY", "P2", 34.9, (176, 125, 18)),
             ((330, 600), "NO PRICE SCHEMA", "P1", 35.2, (217, 83, 30)),
             ((1120, 580), "DEAD CHECKOUT LINKS", "P0", 35.5, (200, 16, 46))]
    pins = []
    for i, ((x, y), lab, pr, at, col) in enumerate(cards):
        a = seg(lt, 0.2 + i * 0.12, 0.45 + i * 0.12)
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
    order = [(0, 1), (1, 3), (3, 2), (2, 0), (0, 3)]
    prog = seg(lt, 0.8, 1.6) * len(order)
    for k, (a, b) in enumerate(order):
        if k >= prog or a >= len(pins) or b >= len(pins):
            continue
        f = clamp(prog - k)
        p1, p2 = pins[a], pins[b]
        p2 = (p1[0] + (p2[0] - p1[0]) * f, p1[1] + (p2[1] - p1[1]) * f)
        jline(d, p1, p2, RED2, 6, fr, 90 + k, amp=4)
    put(img, SECRET, 1740, 930, 0.55)
    a = seg(t, 36.2, 36.6)
    if a:
        put(img, text_img("23 MODULES. 1,090 TESTS.", DISP[72], CHROME, 5, INK, jrot(fr, 0.4)),
            860, 1000, 1, a)
    exhibit_label(img, fr, t)
    return 1.0 + 0.04 * seg(lt, 0, 5.0)


def s7(fr, t, img, d):
    img.paste(P.BG_DESK)
    for i, (L, word, at) in enumerate((("F", "FIX", 38.3), ("A", "AUDIT", 38.9),
                                       ("T", "TEST", 39.5))):
        s = stamp_scale(t, at)
        if not s:
            continue
        cx = W / 2 + (i - 1) * 520
        put(img, text_img(L, DISP[300], CHROME, 10, INK, jrot(fr, 0.8)), cx, 470, s)
        put(img, text_img(word, TYPE[64], MANILA), cx, 700, 1, seg(t, at + 0.05, at + 0.25))
    s = stamp_scale(t, 40.4)
    if s:
        put(img, stamp_img("CASE CLOSED", RED, 96, -9), W / 2, 540, s * 1.35)
    return 1.0 + 0.05 * seg(t, 38.0, 42.0)


def s8(fr, t, img, d):
    img.paste(P.BG_END)
    P.rain(d, fr, 60, (60, 68, 84))
    lt = t - 42.0
    put(img, BADGE, 470, 540, 1.65 * (0.7 + 0.3 * back(seg(lt, 0, 0.7))), seg(lt, 0, 0.4))
    x0 = 880
    s = typed(END_TYPE[1], t, END_TYPE[0], END_TYPE[2])
    if s:
        put(img, text_img(s, DISP[88], CHROME, 5, INK), x0, 200, anchor="tl")
    sc = stamp_scale(t, 44.2)
    if sc:
        im = text_img("He's thorough.", DISP[88], RED2, 5, INK, jrot(fr, 0.5))
        put(img, im, x0 + im.width / 2, 390, sc)
    a = seg(t, 45.2, 45.6)
    if a:
        bx = Image.new("RGBA", (920, 96), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bx)
        bd.rounded_rectangle((0, 0, 919, 95), radius=10, fill=(27, 31, 39, 255),
                             outline=(52, 58, 70, 255), width=3)
        bd.text((28, 48), "/plugin marketplace add spruikco/fat-agent-skill", font=MONO[30],
                fill=MANILA, anchor="lm")
        put(img, bx, x0, 540, 1, a, anchor="tl")
    for at, txt, size, col, y in ((45.9, "Works on Shopify, Wix, Squarespace,", 36, CHROME, 680),
                                  (45.9, "WordPress and more.", 36, CHROME, 728),
                                  (46.6, "Free for Claude Code. No API key required.", 36, DIM,
                                   800)):
        a = seg(t, at, at + 0.4)
        if a:
            put(img, text_img(txt, TYPE[size], col), x0, y, 1, a, anchor="tl")
    a = seg(t, 47.3, 47.7)
    if a:
        put(img, text_img("FAT AGENT.  FIX. AUDIT. TEST.", DISP[40], MANILA, 3, INK), x0, 880,
            1, a, anchor="tl")
    return 1.0 + 0.03 * seg(lt, 0, 8.0)


FNS = [s1, s2, s3, s4, s5, s6, s7, s8]

_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)


def render_frame(fr):
    t = fr / FPS
    idx = max(i for i, (a, b) in enumerate(SCENES) if t >= a)
    a0, b0 = SCENES[idx]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    zoom = FNS[idx](fr, t, img, d)
    sx = sy = 0.0
    for at in EV["thunk"] + EV["bigthunk"] + EV["thunder"]:
        if 0 <= t - at < 0.18:
            k = (1 - (t - at) / 0.18) * (16 if at in EV["bigthunk"] + EV["thunder"] else 7)
            sx += math.sin(fr * 12.9) * k
            sy += math.cos(fr * 7.3) * k
    if abs(zoom - 1) > 1e-3 or sx or sy:
        cw, chh = W / zoom, H / zoom
        cx, cy = W / 2 - sx, H / 2 - sy
        img = img.transform((W, H), Image.EXTENT,
                            (cx - cw / 2, cy - chh / 2, cx + cw / 2, cy + chh / 2),
                            Image.BILINEAR)
    arr = np.asarray(img, dtype=np.int16) + P.GRAIN[boil(fr) % 3]
    arr = arr.astype(np.float32) * P.VIGNETTE
    spot = lineup_spot(t)
    if spot is not None:
        r = np.sqrt((_xx - spot[0]) ** 2 + (_yy - spot[1]) ** 2)
        m = np.clip(1 - (r - 190) / 110, 0, 1)[..., None]
        ramp = min(seg(t, 25.9, 26.2), 1 - seg(t, 29.7, 30.0))
        arr *= 1 - ramp * 0.78 * (1 - m)
    for at in EV["thunder"]:
        if 0 <= t - at < 0.35:
            f = (1 - (t - at) / 0.35) ** 2 * (1.0 if (fr % 3) else 0.6)
            arr = arr * (1 - f * 0.85) + 255 * f * 0.85
    # dip to black between scenes (breathing room), long fade at the very end
    fin = 0.5 if idx == 0 else FADE
    fout = 0.9 if idx == len(SCENES) - 1 else FADE
    fade = min(seg(t, a0, a0 + fin), 1 - seg(t, b0 - fout, b0))
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

    def tt(dd):
        return np.arange(int(SR * dd)) / SR

    def lp(x, k):
        return np.convolve(x, np.ones(k) / k, mode="same") if k > 1 else x

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def pulse(freq, dd, duty=0.5):
        tv = tt(dd)
        return np.where((tv * freq) % 1 < duty, 1.0, -1.0).astype(np.float32)

    r = lp(rng.standard_normal(n).astype(np.float32), 5)
    lvl = np.interp(np.arange(n) / SR, [0, TW(6.0), TW(6.8), TW(41), TW(42.5), DUR],
                    [0.10, 0.10, 0.03, 0.03, 0.07, 0.0])
    out += r * lvl

    beat = 0.6  # 100 bpm: slower, more brooding than v1
    walk = [36, 39, 41, 43, 44, 43, 41, 39, 41, 44, 46, 48, 46, 44, 43, 39]
    k, tb = 0, TW(6.5)
    while tb < TW(48.5):
        # let the lineup breathe: bass drops out while the flashlight sweeps
        quiet = TW(26.0) <= tb < TW(29.9)
        f = hz(walk[k % len(walk)])
        s = lp(pulse(f, beat * 0.95), 18) * np.exp(-tt(beat * 0.95) * 4.0)
        place(s, tb, 0.07 if quiet else 0.20)
        for off, g in ((0.0, 0.03), (0.4, 0.045)):
            hs = rng.standard_normal(int(SR * 0.035)).astype(np.float32)
            hs = (hs - lp(hs, 6)) * np.exp(-tt(0.035) * 90)
            place(hs, tb + off, g * (0.4 if quiet else 1))
        if k % 2 == 0 and not quiet:
            kt = tt(0.18)
            kick = np.sin(2 * np.pi * (58 * kt - 30 * kt ** 2)) * np.exp(-kt * 22)
            place(kick.astype(np.float32), tb, 0.26)
        tb += beat
        k += 1
    # suspense drone under the lineup
    dt_ = tt(TW(30.1) - TW(25.9))
    drone = (np.sin(2 * np.pi * hz(36) * dt_) + 0.5 * np.sin(2 * np.pi * hz(43) * dt_)) * \
        np.minimum(1, dt_ / 0.6) * np.minimum(1, (dt_[-1] - dt_) / 0.4)
    place(drone.astype(np.float32), TW(25.9), 0.12)

    motif = [(67, .3), (68, .3), (67, .3), (65, .3), (63, .6), (62, .3), (60, .9)]
    for at in EV["motif"]:
        x = TW(at)
        for m, dd in motif:
            place(pulse(hz(m), dd * 0.9, 0.25) * np.exp(-tt(dd * 0.9) * 2.0), x, 0.075)
            x += dd
    for at in EV["stinger"]:
        for i, m in enumerate((72, 76, 79, 84)):
            place(pulse(hz(m), 0.7, 0.25) * np.exp(-tt(0.7) * 3), TW(at) + i * 0.08, 0.08)
    for m in (48, 60, 63, 67):
        place(lp(pulse(hz(m), 2.2, 0.5), 10) * np.exp(-tt(2.2) * 1.2), TW(47.6), 0.06)

    def click(at, g=0.2):
        c = rng.standard_normal(int(SR * 0.012)).astype(np.float32)
        c = (c - lp(c, 4)) * np.exp(-tt(0.012) * 300)
        place(c, at, g)

    def bell(at):
        b = np.sin(2 * np.pi * 1850 * tt(0.5)) * np.exp(-tt(0.5) * 9)
        place(b.astype(np.float32), at, 0.09)

    for start, txt, rate, *_ in TYPED:
        for i, ch in enumerate(txt):
            if ch != " ":
                click(TW(start + i * rate))
        bell(TW(start + len(txt) * rate) + 0.05)
    for at, txt in EXHIBITS:
        for i, ch in enumerate(txt):
            if ch != " ":
                click(TW(at + i * 0.045), 0.14)
    s0, txt, rate = END_TYPE
    for i, ch in enumerate(txt):
        if ch != " ":
            click(TW(s0 + i * rate))
    a, b, cnt = EV["ticks"]
    for i in range(cnt):
        click(TW(a + (b - a) * i / cnt), 0.12)

    def thunk(at, g):
        kt = tt(0.22)
        body = np.sin(2 * np.pi * (95 * kt - 70 * kt ** 2)) * np.exp(-kt * 18)
        slap = lp(rng.standard_normal(len(kt)).astype(np.float32), 3) * np.exp(-kt * 60)
        place((body * 0.9 + slap * 0.5).astype(np.float32), at, g)

    for at in EV["thunk"]:
        thunk(TW(at), 0.5)
    for at in EV["bigthunk"]:
        thunk(TW(at), 0.85)
    for at in EV["thunder"]:
        crack = rng.standard_normal(int(SR * 0.12)).astype(np.float32)
        place((crack - lp(crack, 8)) * np.exp(-tt(0.12) * 25), TW(at), 0.45)
        rum = lp(rng.standard_normal(int(SR * 2.4)).astype(np.float32), 90) * 6
        envr = np.minimum(1, tt(2.4) / 0.08) * np.exp(-tt(2.4) * 1.4)
        place((rum * envr).astype(np.float32), TW(at) + 0.02, 0.55)
    # old telephone bell: two detuned bells, hammer at 20 Hz
    for at, ln in RINGS:
        tr = tt(ln)
        bell2 = (np.sin(2 * np.pi * 980 * tr) + 0.8 * np.sin(2 * np.pi * 1310 * tr)
                 + 0.3 * np.sin(2 * np.pi * 2620 * tr))
        hammer = 0.55 + 0.45 * np.sign(np.sin(2 * np.pi * 20 * tr))
        envb = np.minimum(1, tr / 0.02) * np.minimum(1, (ln - tr) / 0.06)
        place((bell2 * hammer * envb).astype(np.float32), TW(at), 0.16)
    click(TW(RINGS[-1][0] + RINGS[-1][1] + 0.25), 0.4)  # receiver picked up
    # flashlight click on and off
    for at in (25.9, 29.95):
        click(TW(at), 0.35)
    for at in EV["whoosh"]:
        dd = 0.5
        w = lp(rng.standard_normal(int(SR * dd)).astype(np.float32), 5)
        envw = np.sin(np.pi * np.clip(tt(dd) / dd, 0, 1)) ** 2
        place((w * envw).astype(np.float32), TW(at) - 0.25, 0.13)

    out = np.tanh(out * 1.2)
    out /= max(1e-6, np.abs(out).max()) / 0.89
    out *= np.minimum(1, np.arange(n) / (SR * 0.2))
    out *= np.clip((DUR - np.arange(n) / SR) / 1.0, 0, 1)
    return (out * 32767).astype(np.int16)


def main():
    args = sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    if "--preview" in args:
        times = [float(x) for x in args[args.index("--preview") + 1].split(",")]
        thumbs = [Image.fromarray(render_frame(int(tv * FPS))).resize((640, 360)) for tv in times]
        cols = 3
        sheet = Image.new("RGB", (cols * 640, ((len(thumbs) + 2) // 3) * 380))
        dd = ImageDraw.Draw(sheet)
        for i, th in enumerate(thumbs):
            x, y = (i % cols) * 640, (i // cols) * 380
            sheet.paste(th, (x, y + 20))
            dd.text((x + 6, y + 2), f"t={times[i]}s", fill=(255, 80, 80))
        sheet.save(os.path.join(here, "promo2_preview.jpg"), quality=80)
        print("preview written")
        return
    out = args[args.index("--out") + 1] if "--out" in args else os.path.join(here, "fat-agent-promo-v2.mp4")
    wav = os.path.join(here, "promo2_audio.wav")
    pcm = audio()
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
           "-tune", "animation", "-c:a", "aac", "-b:a", "128k", "-shortest",
           "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in range(NF):
        p.stdin.write(render_frame(fr).tobytes())
        if fr % 300 == 0:
            print(f"frame {fr}/{NF}", flush=True)
    p.stdin.close()
    p.wait()
    print("done", out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main()
