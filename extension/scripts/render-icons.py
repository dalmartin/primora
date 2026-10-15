"""Render the toolbar icons from icon-src/primrose.svg with headless Chrome.

From the repo root:
    uv run --no-project --with selenium python extension/scripts/render-icons.py
Writes public/icon/<size>.png (dark ink, for light toolbars) and
public/icon/light-<size>.png (light ink; Firefox uses it on dark toolbars).
"""
import base64
import pathlib

from selenium import webdriver

EXT = pathlib.Path(__file__).resolve().parent.parent
SRC = (EXT / "icon-src/primrose.svg").read_text()
OUT = EXT / "public/icon"

# Line width in viewBox units per size: small icons need heavier lines to stay legible.
LINE = {16: 2.6, 32: 2.0, 48: 1.7, 96: 1.4, 128: 1.3}
INKS = {"": "#4a3f55", "light-": "#f3ecf3"}

opts = webdriver.ChromeOptions()
opts.add_argument("--headless=new")
opts.browser_version = "stable"
d = webdriver.Chrome(options=opts)
try:
    d.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 400, "height": 400, "deviceScaleFactor": 1, "mobile": False})
    d.execute_cdp_cmd("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
    for prefix, ink in INKS.items():
        for size, line in LINE.items():
            svg = (SRC.replace('stroke-width="STROKE_HALF"', f'stroke-width="{line}"')
                      .replace('stroke-width="STROKE"', f'stroke-width="{line * 2}"')
                      .replace("INK", ink))
            uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
            d.get("data:text/html,<html><body style='margin:0;background:transparent'>"
                  f"<img src='{uri}' width='{size}' height='{size}' style='display:block'></body></html>")
            d.execute_script("return document.images[0].decode()")
            shot = d.execute_cdp_cmd("Page.captureScreenshot", {
                "format": "png", "clip": {"x": 0, "y": 0, "width": size, "height": size, "scale": 1}})
            (OUT / f"{prefix}{size}.png").write_bytes(base64.b64decode(shot["data"]))
            print("wrote", f"{prefix}{size}.png")
finally:
    d.quit()
