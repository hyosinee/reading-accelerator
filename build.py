"""정적 배포본을 만든다 — reader.html 하나에서 index.html / 아이콘 / 매니페스트 / 서비스워커.

reader.html 은 <head> 없는 본문 조각이 원본이다(아티팩트 쪽이 그 형태를 쓴다).
배포용 index.html 은 여기서 문서 껍데기를 입혀 생성하므로, 리더를 고칠 때는
reader.html 만 고치고 `python build.py` 를 다시 돌리면 된다.

    python build.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
READER = ROOT / "reader.html"

NAME = "읽기 가속기"
SHORT = "가속기"
DESC = "붙여넣은 글을 어절 단위로 흘려보내거나 어근만 굵게 세워 읽는 속독 도구."

GROUND = (0x16, 0x18, 0x1C)
GUIDE = (0x3A, 0x40, 0x48)
AXIS = (0xFF, 0x6F, 0x5E)


def draw_icon(size: int) -> Image.Image:
    """앱의 조준선(가로 안내선 두 줄 + 가운데 빨간 축)을 그대로 쓴다.

    마스커블 대응으로 모든 요소를 안쪽 80% 안에 둔다.
    """
    img = Image.new("RGB", (size, size), GROUND)
    d = ImageDraw.Draw(img)
    t = max(2, round(size * 0.022))  # 안내선 두께

    for y in (0.355, 0.645):
        yy = round(size * y)
        d.rectangle(
            [round(size * 0.20), yy - t // 2, round(size * 0.80), yy + t // 2 + t % 2],
            fill=GUIDE,
        )

    w = max(3, round(size * 0.075))
    cx = size // 2
    d.rectangle(
        [cx - w // 2, round(size * 0.285), cx - w // 2 + w, round(size * 0.715)],
        fill=AXIS,
    )
    return img


SHELL = [
    "./",
    "./index.html",
    "./manifest.webmanifest",
    "./icon-192.png",
    "./icon-512.png",
    "./apple-touch-icon.png",
]

SW = """// 네트워크 우선 + 캐시 폴백. 온라인이면 항상 최신을 받고,
// 한 번 열어 본 뒤에는 신호가 없어도 그대로 열린다.
const VERSION = "__VERSION__";
const CACHE = "accel-" + VERSION;
const SHELL = __SHELL__;

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  e.respondWith(
    fetch(req)
      .then((res) => {
        // 불투명(cross-origin no-cors) 응답은 cache.put 이 거부하므로 ok 인 것만 담는다.
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then(
          (hit) => hit || (req.mode === "navigate" ? caches.match("./index.html") : Response.error())
        )
      )
  );
});
"""

HEAD = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{desc}">
<meta name="theme-color" content="#F6F7F7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#111317" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{short}">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="icon" href="./icon-192.png" sizes="192x192">
<link rel="apple-touch-icon" href="./apple-touch-icon.png">
<style>
  /* 아티팩트 플랫폼이 붙여 주던 최소 리셋을 배포본에서 직접 넣는다. */
  :root{{color-scheme:light dark;
        padding-top:env(safe-area-inset-top,0px);
        padding-bottom:env(safe-area-inset-bottom,0px)}}
  body{{margin:0;font:14px system-ui,-apple-system,sans-serif}}
  img{{max-width:100%}}
  [hidden]{{display:none!important}}
</style>
</head>
<body>
"""

TAIL = """
<script>
// 서비스워커는 https 에서만 등록한다. 파일로 직접 열었을 때 콘솔을 더럽히지 않게.
if ("serviceWorker" in navigator && location.protocol === "https:") {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("./sw.js").catch(function () {});
  });
}
</script>
</body>
</html>
"""


def main() -> None:
    body = READER.read_text(encoding="utf-8")
    page = HEAD.format(desc=DESC, short=SHORT) + body + TAIL
    (ROOT / "index.html").write_text(page, encoding="utf-8", newline="\n")

    manifest = {
        "name": NAME,
        "short_name": SHORT,
        "description": DESC,
        "lang": "ko",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#111317",
        "theme_color": "#F6F7F7",
        "icons": [
            {"src": "./icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "./icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "./icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    (ROOT / "manifest.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")):
        draw_icon(size).save(ROOT / name, "PNG", optimize=True)

    # 내용이 바뀌면 캐시 이름이 바뀌어야 친구들 폰에 옛 버전이 남지 않는다.
    version = hashlib.sha256(page.encode("utf-8")).hexdigest()[:12]
    sw = SW.replace("__VERSION__", version).replace("__SHELL__", json.dumps(SHELL))
    (ROOT / "sw.js").write_text(sw, encoding="utf-8", newline="\n")

    print(f"index.html            {len(page):>7,} 바이트")
    print(f"manifest.webmanifest  아이콘 3종")
    print(f"sw.js                 캐시 accel-{version}")


if __name__ == "__main__":
    main()
