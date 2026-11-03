#!/usr/bin/env python3
"""
Demo/Smoke-Test: baut ein Beispiel-Organigramm aus synthetischen Daten,
ohne dass eine echte ChurchTools-Verbindung nötig ist. Nützlich, um die
Pipeline (Builder -> Renderer -> Web-Export) und die lokale Graphviz-
Installation schnell zu prüfen, bevor echte Zugangsdaten verdrahtet
werden.

Aufruf:
    python demo_mock_data.py
"""
from pathlib import Path

from churchtools_orgchart.models import Group, GroupCategory
from churchtools_orgchart.orgchart_builder import build_category_forest
from churchtools_orgchart.renderer import OrgChartRenderer
from churchtools_orgchart.web_export import build_embeddable_html

categories = {
    1: GroupCategory(id=1, name="Leitung"),
    2: GroupCategory(id=2, name="Kinder & Jugend"),
    3: GroupCategory(id=3, name="Musik & Anbetung"),
    4: GroupCategory(id=4, name="Diakonie"),
}

groups = [
    Group(id=1, name="Gemeindeleitung", category_ids=[1], member_count=6, parent_ids=[]),
    Group(id=2, name="Kinderkirche", category_ids=[2], member_count=12, parent_ids=[1]),
    Group(id=3, name="Jugendkreis", category_ids=[2], member_count=18, parent_ids=[1]),
    Group(id=4, name="Kindergottesdienst-Team", category_ids=[2], member_count=8, parent_ids=[2]),
    Group(id=5, name="Lobpreisteam Orgel & Klavier", category_ids=[3], member_count=5, parent_ids=[1]),
    Group(id=6, name="Chor", category_ids=[3], member_count=22, parent_ids=[5]),
    Group(id=7, name="Besuchsdienst", category_ids=[4], member_count=9, parent_ids=[1]),
    Group(id=8, name="Tafel-Team", category_ids=[4], member_count=14, parent_ids=[7]),
    # Beispiel für Mehrfach-Kategorie: erscheint als eigene Box sowohl
    # unter "Kinder & Jugend" als auch unter "Musik & Anbetung"
    Group(id=9, name="Jugendchor", category_ids=[2, 3], member_count=15, parent_ids=[]),
]

forest = build_category_forest(groups, categories)

renderer = OrgChartRenderer(title="Beispiel-Organigramm nach Kategorien (Mock-Daten)", rankdir="TB")
graph = renderer.build_graph(forest, categories)

output_dir = Path("./output")
output_dir.mkdir(exist_ok=True)

pdf_path = renderer.render_pdf(graph, output_dir / "demo_orgchart")
svg_path = renderer.render_svg(graph, output_dir / "demo_orgchart")
html_path = build_embeddable_html(svg_path, "Beispiel-Organigramm", output_dir / "demo_orgchart_embed.html")

print(f"PDF:  {pdf_path}")
print(f"SVG:  {svg_path}")
print(f"HTML: {html_path}")