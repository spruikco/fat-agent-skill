"""Video SEO audit module (Hobo-parity).

When a page hosts video, Google can surface it in Search, Video, and key-moments
results — but only with the right markup. Detectable from the live HTML:

- video present via `<video>` / YouTube / Vimeo embeds
- `VideoObject` structured data with the required properties
  (`name`, `description`, `thumbnailUrl`, `uploadDate`)
- a thumbnail image
- key-moments markup (`Clip` / `SeekToAction`)

A video sitemap can't be seen from the page — recommend it in findings.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule

_VIDEO_EMBED_RE = re.compile(
    r"<video[\s>]|youtube\.com/embed|youtube-nocookie\.com/embed|youtu\.be/|"
    r"player\.vimeo\.com|wistia\.|<embed[^>]+video|vimeo\.com/\d+",
    re.IGNORECASE,
)
_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def _videoobject_blocks(html):
    blocks = []
    for raw in _JSON_LD_RE.findall(html):
        if re.search(r'"@type"\s*:\s*"videoobject"', raw, re.IGNORECASE):
            blocks.append(raw.lower())
    return blocks


@register_module
class VideoModule(AuditModule):
    MODULE_ID = "video"
    DISPLAY_NAME = "Video SEO"

    @classmethod
    def detect(cls, html: str) -> bool:
        return bool(_VIDEO_EMBED_RE.search(html))

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        vo = _videoobject_blocks(html)
        joined = " ".join(vo)
        return {
            "has_video": bool(_VIDEO_EMBED_RE.search(html)),
            "has_videoobject": bool(vo),
            "required_props": {
                "name": '"name"' in joined,
                "description": '"description"' in joined,
                "thumbnailUrl": "thumbnailurl" in joined,
                "uploadDate": "uploaddate" in joined,
            },
            "has_key_moments": bool(
                re.search(r'"(?:clip|seektoaction)"', joined) or '"haspart"' in joined
            ),
            "has_thumbnail": bool(
                "thumbnailurl" in joined
                or re.search(r'<meta[^>]+property=["\']og:image', html, re.IGNORECASE)
            ),
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        present = 30 if analysis["has_videoobject"] else 0
        details["videoobject_present"] = {"score": present, "max": 30}
        total += present

        req = analysis["required_props"]
        req_pts = sum(10 for v in req.values() if v)
        details["required_props"] = {"score": req_pts, "max": 40}
        total += req_pts

        thumb = 15 if analysis["has_thumbnail"] else 0
        details["thumbnail"] = {"score": thumb, "max": 15}
        total += thumb

        km = 15 if analysis["has_key_moments"] else 0
        details["key_moments"] = {"score": km, "max": 15}
        total += km

        self._findings(analysis)
        return {"total": total, "max": 100, "details": details}

    def _findings(self, a: dict):
        if a["has_video"] and not a["has_videoobject"]:
            self.add_finding(
                priority="P2",
                title="Video present but no VideoObject schema",
                description="A video was found with no `VideoObject` structured data, so it isn't "
                "eligible for video rich results or Google's Video tab.",
                fix="Add `VideoObject` JSON-LD with `name`, `description`, `thumbnailUrl`, "
                "`uploadDate`, and `contentUrl`/`embedUrl`; submit a video sitemap.",
                effort="medium",
            )
            return
        if a["has_videoobject"]:
            missing = [k for k, v in a["required_props"].items() if not v]
            if missing:
                self.add_finding(
                    priority="P2",
                    title=f"VideoObject missing required propert{'y' if len(missing) == 1 else 'ies'}: {', '.join(missing)}",
                    description="VideoObject is present but missing properties Google requires for "
                    "video rich results.",
                    fix=f"Add {', '.join(missing)} to the VideoObject markup.",
                    effort="low",
                )
            if not a["has_key_moments"]:
                self.add_finding(
                    priority="P3",
                    title="No video key-moments markup",
                    description="No `Clip`/`SeekToAction` key-moments markup. Key moments earn richer, "
                    "more clickable video results.",
                    fix="Add `hasPart` `Clip` entries (or `SeekToAction`) for the video's key moments.",
                    effort="medium",
                )
