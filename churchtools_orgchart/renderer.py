"""
Rendert einen Organigramm-Wald (``list[OrgNode]``) mittels Graphviz als
PDF (Druck/Archiv) und SVG (Web-Einbindung, skalierbar, crisp).

Voraussetzung: Das Graphviz-Systempaket muss installiert sein
(z.B. ``apt-get install graphviz`` / ``brew install graphviz``), da die
Python-Bibliothek ``graphviz`` lediglich den ``dot``-Befehl aufruft.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as xml_escape
from itertools import islice

import graphviz

from .models import GroupCategory, OrgNode

# Fallback-Palette, falls eine Kategorie in ChurchTools keine eigene
# Farbe hinterlegt hat. Zuweisung ist deterministisch (Hash der
# Kategorie-ID), damit Farben zwischen Läufen stabil bleiben.
_DEFAULT_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]

_DEFAULT_PALETTE_CODEWORDS = [
    "blue", "orange", "emerald", "red", "violet", "brown", "pink", "gray", "yellow", "cyan",
]

SPECIAL_COLORS = {
    "accent": "#4C72B0",   # Mapped auf das Standard-Blau
    "default": "#8C8C8C",  # Mapped auf Grau
}

CODEWORD_TO_HEX = dict(zip(_DEFAULT_PALETTE_CODEWORDS, _DEFAULT_PALETTE))

def is_valid_hex(color_str: str) -> bool:
    """Prüft, ob ein String ein gültiger 6-stelliger Hex-Code ist (mit oder ohne #)."""
    clean = color_str.lstrip("#")
    return len(clean) == 6 and all(c in "0123456789abcdefABCDEF" for c in clean)


def _color_for_category(category_id: int, category: Optional[GroupCategory]) -> str:
    if category and category.color:
        color = category.color.strip().lower()
        
        # 1. Fall: Es ist ein bekanntes Codewort (z.B. "blue", "orange")
        if color in CODEWORD_TO_HEX:
            return CODEWORD_TO_HEX[color]
            
        # 2. Fall: Es ist ein ChurchTools-Spezialwert (z.B. "accent")
        if color in SPECIAL_COLORS:
            return SPECIAL_COLORS[color]
            
        # 3. Fall: Es ist bereits ein gültiger Hex-Wert
        if is_valid_hex(color):
            return color if color.startswith("#") else f"#{color}"
            
    # Fallback: Wenn keine Farbe definiert ist oder der Wert ungültig war, hashen wir die ID
    digest = hashlib.md5(str(category_id).encode()).hexdigest()
    index = int(digest, 16) % len(_DEFAULT_PALETTE)
    return _DEFAULT_PALETTE[index]


def _is_dark(hex_color: str) -> bool:
    hex_color = hex_color.lstrip("#")
    # Sicherheitsnetz: Wenn hier doch mal ein fehlerhafter Wert durchrutscht
    if not is_valid_hex(hex_color):
        return False  # Standardmäßig als "hell" behandeln oder True als Fallback
        
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance < 140

_SPINE_COLOR = "#4472C4"  # Trunk-/Ast-Farbe, angelehnt an dein Referenzbild


class OrgChartRenderer:
    def __init__(
        self,
        title: str = "Organigramm",
        rankdir: str = "TB",
        font_name: str = "Helvetica",
    ) -> None:
        self.title = title
        self.rankdir = rankdir
        self.font_name = font_name

    def _new_graph(self) -> graphviz.Digraph:
        graph = graphviz.Digraph("orgchart")
        graph.attr(
            rankdir=self.rankdir,
            fontname=self.font_name,
            label=self.title,
            labelloc="t",
            fontsize="20",
            bgcolor="white",
            splines="polyline",      # rechtwinklige Kanten (Trunk + Äste)
            nodesep="0.35",
            ranksep="0.45",
            size="11.69,8.27",    # A4 Hochformat in Zoll -> Ausgabe wird darauf skaliert
            margin="0.3",
        )
        graph.attr(
            "node",
            shape="box",
            style="rounded,filled",
            fontname=self.font_name,
            fontsize="11",
            margin="0.15,0.08",
        )
        graph.attr("edge", color="#888888", arrowsize="0.7")
        return graph

    # ------------------------------------------------------------------
    # Box zeichnen (reiner Node, ohne Kanten)
    # ------------------------------------------------------------------
    def _draw_box(
        self,
        graph: graphviz.Digraph,
        node: OrgNode,
        categories: dict[int, GroupCategory],
        seen: set[int],
        namespace: str,
        if_add_groupleader: bool,
        if_add_groupleaderphonenumber: bool,
        if_add_groupleadermailaddress: bool,
    ) -> str:
        node_id = f"{namespace}_{node.group.gid}"
        if node.group.gid in seen:
            return node_id  # schon gezeichnet (Mehrfach-Parent) -> nur ID zurückgeben
        seen.add(node.group.gid)

        cat_id_field = node.group.category_id
        if isinstance(cat_id_field, list):
            primary_category_id = cat_id_field[0] if cat_id_field else 0
        else:
            primary_category_id = cat_id_field if cat_id_field is not None else 0
        category = categories.get(primary_category_id)
        fill_color = _color_for_category(primary_category_id, category)
        fill_color = fill_color if fill_color not in _DEFAULT_PALETTE_CODEWORDS else CODEWORD_TO_HEX[fill_color]
        font_color = "white" if _is_dark(fill_color) else "black"

        if node.group.is_category:
            graph.node(
                node_id,
                label=node.group.name,
                fillcolor=fill_color,
                fontcolor=font_color,
                fontsize="14",
                style="bold,filled,rounded",
                penwidth="2",
            )
        else:
            label_lines = [node.group.name]
            # if node.group.member_count is not None:
            #     label_lines.append(f"{node.group.member_count} Mitglieder")

            for leader in node.group.leaders:
                leader_name = leader.get("leader_name")

                if if_add_groupleader is True:
                    if if_add_groupleaderphonenumber is True and if_add_groupleadermailaddress is True:
                        leader_phone = leader.get("leader_phone_number")
                        leader_mail = leader.get("leader_mail_address")
                        if leader_phone and leader_mail:
                            label_lines.append(f"{leader_name} · {leader_mail} · {leader_phone}")
                        elif leader_phone and not leader_mail:
                            label_lines.append(f"{leader_name} · {leader_phone}")
                        elif not leader_phone and leader_mail:
                            label_lines.append(f"{leader_name} · {leader_mail}")
                        else:
                            label_lines.append(f"{leader_name}")
                    elif if_add_groupleaderphonenumber is True and if_add_groupleadermailaddress is not True:
                        leader_phone = leader.get("leader_phone_number")
                        if leader_phone:
                            label_lines.append(f"{leader_name} · {leader_phone}")
                        else:
                            label_lines.append(f"{leader_name}")
                    elif if_add_groupleaderphonenumber is not True and if_add_groupleadermailaddress is True:
                        leader_mail = leader.get("leader_mail_address")
                        if leader_mail:
                            label_lines.append(f"{leader_name} · {leader_mail}")
                        else:
                            label_lines.append(f"{leader_name}")
                    else:
                        label_lines.append(f"{leader_name}")
                
            label = "\n".join(line.replace("\\", "/") for line in label_lines)
            graph.node(
                node_id,
                label=label,
                fillcolor=fill_color,
                fontcolor=font_color,
            )
        return node_id

    # ------------------------------------------------------------------
    # Trunk + Äste für eine Kinderliste
    # ------------------------------------------------------------------
    def _add_children_spine(
        self,
        graph: graphviz.Digraph,
        parent_id: str,
        children: list[OrgNode],
        categories: dict[int, GroupCategory],
        seen: set[int],
        namespace: str,
        depth: int,
        if_add_groupleader: bool,
        if_add_groupleaderphonenumber: bool,
        if_add_groupleadermailaddress: bool,
    ) -> None:
        if not children:
            return

        prev_spine_id: Optional[str] = None
        for index, child in enumerate(children):
            child_gid = child.group.gid
            already_drawn = child_gid in seen
            child_id = self._draw_box(graph, child, categories, seen, namespace, if_add_groupleader=if_add_groupleader, if_add_groupleaderphonenumber=if_add_groupleaderphonenumber, if_add_groupleadermailaddress=if_add_groupleadermailaddress)

            spine_id = f"{namespace}_spine_{depth}_{index}_{child_gid}"
            graph.node(spine_id, shape="point", width="0.01", style="invis")

            if prev_spine_id is None:
                # Trunk beginnt direkt unter der Elternbox
                graph.edge(parent_id, spine_id, color=_SPINE_COLOR, arrowhead="none", penwidth="1.3")
            else:
                # Vertikales Trunk-Segment zum nächsten Punkt
                graph.edge(prev_spine_id, spine_id, color=_SPINE_COLOR, arrowhead="none", penwidth="1.3")

            # Horizontaler Ast vom Trunk in die Box
            graph.edge(spine_id, child_id, color=_SPINE_COLOR, arrowhead="none", penwidth="1.3")

            if not already_drawn:
                with graph.subgraph() as s:
                    s.attr(rank="same")
                    s.node(spine_id)
                    s.node(child_id)

            prev_spine_id = spine_id

            # Falls die Kind-Gruppe selbst Kinder hat: eigener Trunk, einen Schritt weiter rechts
            self._add_children_spine(graph, child_id, child.children, categories, seen, namespace, depth + 1, if_add_groupleader=if_add_groupleader, if_add_groupleaderphonenumber=if_add_groupleaderphonenumber, if_add_groupleadermailaddress=if_add_groupleadermailaddress)

    def _add_node(
        self,
        graph: graphviz.Digraph,
        node: OrgNode,
        categories: dict[int, GroupCategory],
        seen: set[int],
        namespace: str,
        if_add_groupleader: bool,
        if_add_groupleaderphonenumber: bool,
        if_add_groupleadermailaddress: bool,
    ) -> None:
        node_id = self._draw_box(graph, node, categories, seen, namespace, if_add_groupleader=if_add_groupleader, if_add_groupleaderphonenumber=if_add_groupleaderphonenumber, if_add_groupleadermailaddress=if_add_groupleadermailaddress)
        self._add_children_spine(graph, node_id, node.children, categories, seen, namespace, depth=0, if_add_groupleader=if_add_groupleader, if_add_groupleaderphonenumber=if_add_groupleaderphonenumber, if_add_groupleadermailaddress=if_add_groupleadermailaddress)

    def _add_legend(self, graph: graphviz.Digraph, categories: dict[int, GroupCategory]) -> None:
        if not categories:
            return
        with graph.subgraph(name="cluster_legend") as legend:
            legend.attr(label="Kategorien", fontsize="10", style="dashed", color="#cccccc")
            legend.attr("node", shape="plaintext", fontsize="9")
            for cat_id, category in sorted(categories.items(), key=lambda kv: kv[1].name or ""):
                color = _color_for_category(cat_id, category)
                color = color if color not in _DEFAULT_PALETTE_CODEWORDS else CODEWORD_TO_HEX[color]
                label_text = category.name or f"Kategorie {cat_id}"
                legend.node(
                    f"legend_{cat_id}",
                    label=(
                        '<<table border="0" cellborder="0" cellspacing="2">'
                        f'<tr><td bgcolor="{color}" width="14" height="14"></td>'
                        f"<td>{xml_escape(label_text)}</td></tr></table>>"
                    ),
                )

    def build_graph(
        self,
        forest: list[OrgNode],
        categories: dict[int, GroupCategory],
        if_add_groupleader: bool,
        if_add_groupleaderphonenumber: bool,
        if_add_groupleadermailaddress: bool,
        include_legend: bool = False,
    ) -> graphviz.Digraph:
        graph = self._new_graph()
        for index, root in enumerate(forest):
            seen: set[int] = set()
            self._add_node(graph, root, categories, seen, namespace=f"root{index}", if_add_groupleader=if_add_groupleader, if_add_groupleaderphonenumber=if_add_groupleaderphonenumber, if_add_groupleadermailaddress=if_add_groupleadermailaddress)

        if include_legend:
            self._add_legend(graph, categories)

        return graph

    @staticmethod
    def render_pdf(graph: graphviz.Digraph, output_path: Path) -> Path:
        graph.format = "pdf"
        rendered = graph.render(
            filename=output_path.stem, directory=str(output_path.parent), cleanup=True
        )
        return Path(rendered)

    @staticmethod
    def render_svg(graph: graphviz.Digraph, output_path: Path) -> Path:
        graph.format = "svg"
        rendered = graph.render(
            filename=output_path.stem, directory=str(output_path.parent), cleanup=True
        )
        return Path(rendered)
