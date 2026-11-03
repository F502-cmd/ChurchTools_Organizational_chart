"""
CLI-Einstiegspunkt: Lädt Gruppendaten aus ChurchTools, baut ein
Organigramm auf Basis der Gruppenhierarchie/-kategorien und exportiert
es als PDF sowie als in eine Webseite einbettbares HTML/SVG.

Nutzung s. README.md

Zugangsdaten können statt über Argumente auch per .env-Datei bereit-
gestellt werden (siehe .env.example).

Regelmäßige/dynamische Aktualisierung: dieses Skript ist idempotent und
kann problemlos per Cronjob/CI-Pipeline periodisch ausgeführt werden, um
PDF und Web-Snippet aktuell zu halten.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from churchtools_orgchart.churchtools_client import ChurchToolsAPIError, ChurchToolsClient
from churchtools_orgchart.models import GroupCategory, OrgNode
from churchtools_orgchart.orgchart_builder import build_category_forest, load_orgchart_data
from churchtools_orgchart.renderer import OrgChartRenderer
from churchtools_orgchart.web_export import build_embeddable_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("churchtools_orgchart")


RUNNER_EXPORT_VARIANTS = (
    ("Orgchart", False, False, False),
    ("Orgchart_phone", True, True, False),
    ("Orgchart_mail", True, False, True),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChurchTools-Organigramm-Generator", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--base-url",
        type=str,
        default=f"{os.getenv("CHURCHTOOLS_BASE_URL")}",
        help="z.B. https://meine-gemeinde.church.tools",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=f"{os.getenv("CHURCHTOOLS_LOGIN_TOKEN")}",
        help="Persönliches API-/Login-Token (ChurchTools -> Profil -> API)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Zielverzeichnis für PDF/SVG/HTML"
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Organigramm Kirchengemeinde",
        help="Titel im Diagramm"
    )
    parser.add_argument(
        "--rankdir",
        type=str,
        default="TB",
        choices=["TB", "LR"],
        help="Ausrichtung: top-down (TB) oder links-nach-rechts (LR)",
    )
    parser.add_argument(
        "--addgroupleader",
        action="store_true",
        dest="addgroupleader",
        help="Fügt Gruppenleiter (Namen) zum Organigramm hinzu, wenn die Flag mit angegeben wird.",
    )
    parser.add_argument(
        "--addgroupleaderphonenumber",
        action="store_true",
        dest="addgroupleaderphonenumber",
        help="Fügt Gruppenleiter (Handynummer) zum Organigramm hinzu, wenn die Flag mit angegeben wird.",
    )
    parser.add_argument(
        "--addgroupleadermailaddress",
        action="store_true",
        dest="addgroupleadermailaddress",
        help="Fügt Gruppenleiter (Mailadresse) zum Organigramm hinzu, wenn die Flag mit angegeben wird.",
    )
    parser.add_argument(
        "--runner-export",
        action="store_true",
        help=(
            "Erzeugt die drei PDF-Varianten Orgchart, Orgchart_phone und "
            "Orgchart_mail für den GitHub Runner."
        ),
    )

    

    return parser.parse_args()


def render_runner_exports(
    renderer: OrgChartRenderer,
    forest: list[OrgNode],
    categories: dict[int, GroupCategory],
    output_dir: Path,
) -> list[Path]:
    """Erzeugt die drei PDF-Dateien, die vom GitHub Runner veröffentlicht werden."""
    pdf_paths: list[Path] = []

    for filename, add_leaders, add_phone, add_mail in RUNNER_EXPORT_VARIANTS:
        graph = renderer.build_graph(
            forest,
            categories,
            include_legend=False,
            if_add_groupleader=add_leaders,
            if_add_groupleaderphonenumber=add_phone,
            if_add_groupleadermailaddress=add_mail,
        )
        pdf_paths.append(renderer.render_pdf(graph, output_dir / filename))

    return pdf_paths


def main() -> int:
    load_dotenv()
    args = parse_args()

    if not args.base_url or not args.token:
        logger.error("--base-url und --token müssen gesetzt sein (Argument oder .env-Datei).")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = ChurchToolsClient(base_url=args.base_url, login_token=args.token)

    try:
        client.whoami()
    except ChurchToolsAPIError as exc:
        logger.error("Verbindungstest fehlgeschlagen: %s", exc)
        return 1

    logger.info("Lade Gruppen und Kategorien ...")
    # Für die Runner-Varianten werden alle Kontaktdaten in einem einzigen
    # ChurchTools-Lauf geladen und anschließend je PDF gezielt eingeblendet.
    load_leaders = args.addgroupleader or args.runner_export
    load_phone = args.addgroupleaderphonenumber or args.runner_export
    load_mail = args.addgroupleadermailaddress or args.runner_export
    groups, categories = load_orgchart_data(
        client=client,
        if_add_groupleader=load_leaders,
        if_add_groupleaderphonenumber=load_phone,
        if_add_groupleadermailaddress=load_mail,
    )
    logger.info("%d Gruppen, %d Kategorien geladen.", len(groups), len(categories))

    forest = build_category_forest(groups, categories)

    renderer = OrgChartRenderer(title=args.title, rankdir=args.rankdir)
    if args.runner_export:
        pdf_paths = render_runner_exports(renderer, forest, categories, output_dir)
        logger.info("Fertig:")
        for pdf_path in pdf_paths:
            logger.info("  PDF: %s", pdf_path)
        return 0

    graph = renderer.build_graph(forest, categories, include_legend=False, if_add_groupleader=args.addgroupleader, if_add_groupleaderphonenumber=args.addgroupleaderphonenumber, if_add_groupleadermailaddress=args.addgroupleadermailaddress)

    pdf_path = renderer.render_pdf(graph, output_dir / "orgchart")
    svg_path = renderer.render_svg(graph, output_dir / "orgchart")
    html_path = build_embeddable_html(svg_path, args.title, output_dir / "orgchart_embed.html")

    logger.info("Fertig:")
    logger.info("  PDF:  %s", pdf_path)
    logger.info("  SVG:  %s", svg_path)
    logger.info("  HTML: %s", html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
