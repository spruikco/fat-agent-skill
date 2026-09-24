"""FAT Agent promo v3: v2 slowed to ~60s with per-scene holds and longer dissolves.

Each scene of promo2 plays at its own slow-down factor (heavier slides slower),
so text has time to be read. Picture and sound share one time warp.
Usage: python promo3.py [--preview t1,t2,...] [--out file.mp4]
"""
import os
import subprocess
import sys
import wave

from PIL import Image, ImageDraw

import promo2 as B

# per-scene slow-down: cold open, title, case chart, sweep, lineup, board, F-A-T, end card
FACTORS = [1.12, 1.0, 1.3, 1.18, 1.3, 1.4, 1.05, 1.28]
SRC = B.SCENES
OUT = []
t0 = 0.0
for (a, b), f in zip(SRC, FACTORS):
    OUT.append((t0, t0 + (b - a) * f))
    t0 += (b - a) * f
DUR = OUT[-1][1]


def src_to_out(x):
    for (a, b), (oa, ob), f in zip(SRC, OUT, FACTORS):
        if x <= b or (a, b) == SRC[-1]:
            return oa + (max(x, a) - a) * f
    return DUR


def out_to_src(T):
    for (a, b), (oa, ob), f in zip(SRC, OUT, FACTORS):
        if T < ob or (oa, ob) == OUT[-1]:
            return a + (T - oa) / f
    return SRC[-1][1]


B.FADE = 0.5


def _boil(fr):  # warped frames are fractional; keep the 10fps line boil on ints
    return int(fr) // 3


B.boil = _boil
B.P.boil = _boil
B.TW = src_to_out
B.DUR = DUR
FPS = B.FPS
NF = int(round(DUR * FPS))


def frame(fr_out):
    t_src = out_to_src(fr_out / FPS)
    return B.render_frame(t_src * FPS)


def main():
    args = sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    if "--preview" in args:
        times = [float(x) for x in args[args.index("--preview") + 1].split(",")]
        thumbs = [Image.fromarray(frame(int(t * FPS))).resize((640, 360)) for t in times]
        sheet = Image.new("RGB", (3 * 640, ((len(thumbs) + 2) // 3) * 380))
        d = ImageDraw.Draw(sheet)
        for i, th in enumerate(thumbs):
            x, y = (i % 3) * 640, (i // 3) * 380
            sheet.paste(th, (x, y + 20))
            d.text((x + 6, y + 2), f"t={times[i]}s", fill=(255, 80, 80))
        sheet.save(os.path.join(here, "promo3_preview.jpg"), quality=80)
        print("preview written; duration", round(DUR, 2))
        return
    out = args[args.index("--out") + 1] if "--out" in args else os.path.join(here, "fat-agent-promo-v3.mp4")
    wav = os.path.join(here, "promo3_audio.wav")
    pcm = B.audio()
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(B.SR)
        w.writeframes(pcm.tobytes())
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{B.P.W}x{B.P.H}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
           "-tune", "animation", "-c:a", "aac", "-b:a", "128k", "-shortest",
           "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in range(NF):
        p.stdin.write(frame(fr).tobytes())
        if fr % 300 == 0:
            print(f"frame {fr}/{NF}", flush=True)
    p.stdin.close()
    p.wait()
    print("done", out, os.path.getsize(out) // 1024, "KB", "duration", round(DUR, 2))


if __name__ == "__main__":
    main()
