"""Build archive/index.html — a dated list of every published snapshot.

Run from the workflow after a new snapshot is copied in. Kept as a script
rather than shell in the YAML so it can be tested locally.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

STAMP = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})\.html$")

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>radar archive</title>
<style>
:root{{--bg:#fbfaf8;--panel:#fff;--ink:#1a1a19;--muted:#6b6a67;--line:#e6e3dd;
  --accent:#b8563a;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
@media (prefers-color-scheme:dark){{:root{{--bg:#17171a;--panel:#1f1f23;--ink:#eceae6;
  --muted:#9b9994;--line:#33333a;--accent:#e08a6c}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:720px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}}
h1 span{{color:var(--accent)}}
.sub{{color:var(--muted);font-size:13px;font-family:var(--mono);
  border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:24px}}
a{{color:var(--ink)}} a:hover{{color:var(--accent)}}
.latest{{display:block;padding:14px 16px;border:1px solid var(--accent);
  border-radius:8px;margin-bottom:24px;text-decoration:none;background:var(--panel)}}
.latest b{{color:var(--accent)}}
ul{{list-style:none;padding:0;margin:0}}
li{{padding:9px 2px;border-bottom:1px solid var(--line);display:flex;gap:12px}}
li a{{text-decoration:none;font-weight:600}}
li span{{margin-left:auto;color:var(--muted);font-family:var(--mono);font-size:12px}}
footer{{margin-top:44px;color:var(--muted);font-size:12px;font-family:var(--mono)}}
</style></head><body><div class="wrap">
<h1>radar<span>.</span> archive</h1>
<div class="sub">{count} snapshots &middot; generated {generated}</div>
<a class="latest" href="../"><b>&rarr; Latest run</b><br>
  <span style="color:var(--muted);font-size:13px">always the most recent snapshot</span></a>
<ul>
{rows}
</ul>
<footer>built by <a href="https://github.com/CdyDoodle/project-radar">project-radar</a></footer>
</div></body></html>
"""


def build(archive_dir: Path) -> int:
    entries = []
    for path in archive_dir.glob("*.html"):
        m = STAMP.match(path.name)
        if not m:
            continue  # index.html itself, and anything hand-added
        y, mo, d, hh, mm = m.groups()
        entries.append((f"{y}-{mo}-{d} {hh}:{mm}", path.name, path.stat().st_size))
    entries.sort(reverse=True)

    rows = "\n".join(
        f'  <li><a href="{name}">{when}</a><span>{size // 1024} KB</span></li>'
        for when, name, size in entries
    ) or '  <li><span>no snapshots yet</span></li>'

    (archive_dir / "index.html").write_text(
        PAGE.format(count=len(entries), rows=rows,
                    generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        encoding="utf-8",
    )
    return len(entries)


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "site/archive")
    target.mkdir(parents=True, exist_ok=True)
    print(f"archive index: {build(target)} snapshots -> {target / 'index.html'}")
