"""
churchtools_orgchart
=====================

Kleines Toolkit, um aus ChurchTools-Gruppendaten (+ Kategorien) automatisch ein Organigramm zu erzeugen - als PDF und als in eine Webseite einbettbares SVG/HTML.

## Architektur

churchtools_orgchart/
├── churchtools_client.py     # HTTP-Client (Auth, Pagination, Retry)
├── models.py                 # Group, GroupCategory, OrgNode (Dataclasses)
├── orgchart_builder.py       # Rohdaten -> normalisierte Baumstruktur
├── renderer.py               # Baumstruktur -> Graphviz -> PDF/SVG
└── web_export.py             # SVG -> einbettbares HTML-Snippet
"""

__version__ = "1.0.0"
