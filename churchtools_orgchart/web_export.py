"""
Erzeugt ein eigenständiges, responsives HTML-Snippet mit eingebettetem
SVG-Organigramm - fertig zur Einbindung per <iframe> oder direkt inline
in eine bestehende Webseite.
"""
from __future__ import annotations

from pathlib import Path

_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  html, body {{ margin: 0; padding: 0; }}
  .orgchart-wrapper {{
    width: 100%;
    max-width: 100%;
    overflow: auto;
    background: #ffffff;
  }}
  .orgchart-wrapper svg {{
    width: 100%;
    height: auto;
    display: block;
  }}
</style>
</head>
<body>
<div class="orgchart-wrapper">
{svg_content}
</div>
</body>
</html>
"""


def build_embeddable_html(svg_path: Path, title: str, output_path: Path) -> Path:
    """
    Liest das gerenderte SVG ein, entfernt die XML-Deklaration (damit es
    direkt als Inline-SVG funktioniert) und schreibt ein fertiges,
    responsives HTML-Dokument.
    """
    svg_content = svg_path.read_text(encoding="utf-8")
    if svg_content.startswith("<?xml"):
        svg_content = svg_content.split("?>", 1)[1].lstrip()

    html = _TEMPLATE.format(title=title, svg_content=svg_content)
    output_path.write_text(html, encoding="utf-8")
    return output_path
