"""
Transformiert rohe ChurchTools-Gruppendaten in eine normalisierte
Baumstruktur (Wald aus ``OrgNode``), die der Renderer anschließend
zeichnet.

Die Funktionen ``_extract_category_ids`` und ``fetch_parent_ids`` sind
bewusst als kleine, isolierte Adapter geschrieben: das sind die einzigen
Stellen, an denen versionsabhängige ChurchTools-Feldnamen ins Spiel
kommen. Falls Ihre Instanz abweicht, reicht es, diese zwei Funktionen
anzupassen - der Rest der Pipeline bleibt unberührt.
"""
from __future__ import annotations

import logging

from .churchtools_client import ChurchToolsClient
from .models import Group, GroupCategory, OrgNode

logger = logging.getLogger("churchtools_orgchart")


# ---------------------------------------------------------------------
# Adapter: Rohdaten -> Modelle (hier ansetzen, falls Ihre CT-Version
# andere Feldnamen verwendet)
# ---------------------------------------------------------------------

def normalize_group(raw_group: dict) -> Group:
    info = raw_group.get("information") or {}
    settings = raw_group.get("settings") or {}
    raw_id = raw_group.get("id")
    return Group(
        gid=raw_id,
        name=raw_group.get("name"),
        group_type=info.get("groupTypeId"),
        category_id=info.get("groupCategoryId"),
        member_count=info.get("memberCount"),
        is_public=bool(settings.get("isPublic", False)),
    )

def normalize_category(raw_category: dict) -> GroupCategory:
    return GroupCategory(
        gcid=raw_category.get("id"),
        name=raw_category.get("name"),
        color=raw_category.get("color"),
    )

def get_phone_number(raw_person: dict) -> str | None:
    data = raw_person.get("data") or {}
    return data.get("phonePrivate") or data.get("mobile") or data.get("phoneWork")

def get_mail_address(raw_person: dict) -> str | None:
    data = raw_person.get("data") or {}
    if data.get("email"):
        return data["email"]

    emails = data.get("emails") or {}
    if isinstance(emails, dict):
        return emails.get("email")
    if isinstance(emails, list):
        return next(
            (entry.get("email") for entry in emails if isinstance(entry, dict) and entry.get("email")),
            None,
        )
    return None

def add_group_leaders(groups: list[Group], client: ChurchToolsClient, if_add_groupleaderphonenumber: bool,if_add_groupleadermailaddress: bool) -> None:
    """
    Lädt die Leader-IDs für jede Gruppe und fügt sie den Group-Objekten hinzu.
    Für Gruppentyp 'Gruppe' mit GruppenTypID 1 ist die role_id eines Leiters 9.
    Für Gruppentyp 'Dienst' mit GruppenTypID 2 ist die role_id eines Leiters 16.
    Für Gruppentyp 'Gremium/Ausschüsse' mit GruppenTypID 3 ist die role_id eines Vorsitzenden 23.
    Für Gruppentyp 'Merkmal' mit GruppenTypID 4 ist die role_id eines Leiters 30.
    Für Gruppentyp 'Veranstaltung/Aktion' mit GruppenTypID 5 ist die role_id eines Leiters 37.
    Für Gruppentyp 'Gruppe mit Dienst' mit GruppenTypID 6 ist die role_id eines Leiters 43.
    """
    group_type_doubledot_leader_role_id = {
        1: 9,  # Gruppentyp 1 nutzt die Leiter-Rollen-ID 9
        2: 16,
        3: 23,
        4: 30,
        5: 37,
        6: 43,
    }

    for group in groups:
        # 1. Rolle für den Gruppentyp ermitteln
        role_id = group_type_doubledot_leader_role_id.get(group.group_type)
        
        # Falls dieser Gruppentyp nicht im Dictionary definiert ist, überspringen wir die Abfrage
        if role_id is None:
            continue
            
        try:
            # API-Abfrage mit der ermittelten Rollen-ID (als Liste übergeben)
            response = client.get_group_members_by_id(
                group_id=group.gid, 
                role_ids=[role_id]
            )
            
            # Falls die API keine Daten liefert, nutzen wir eine leere Liste [] als Fallback (verhindert Absturz)
            leaders_data = response.get("data") if response else []
            if not leaders_data:
                continue

            for leader in leaders_data:
                person = leader.get("person", {})
                
                # 2. Daten defensiv auslesen (verhindert Abstürze bei fehlenden JSON-Feldern)
                leader_name = person.get("title") or person.get("name") or "Unbekannt"
                leader_id = person.get("domainIdentifier")

                # 3. Zum Group-Objekt hinzufügen
                # (Stellt sicher, dass .leaders initialisiert ist)
                if not hasattr(group, "leaders") or group.leaders is None:
                    group.leaders = []

                raw_person = client.get_person_by_id(leader_id)

                group.leaders.append({
                    "leader_name": leader_name,
                    "leader_id": leader_id,
                    "leader_phone_number": get_phone_number(raw_person) if if_add_groupleaderphonenumber else None,
                    "leader_mail_address": get_mail_address(raw_person) if if_add_groupleadermailaddress else None,
                })

        except Exception as e:
            # Fehler bei einer einzelnen Gruppe loggen, damit das restliche Skript weiterläuft
            print(f"Fehler beim Laden der Leiter für Gruppe {group.name} (ID: {group.gid}): {e}")

# ---------------------------------------------------------------------
# Laden + Aufbau
# ---------------------------------------------------------------------


def load_orgchart_data(
    client: ChurchToolsClient,
    if_add_groupleader: bool,
    if_add_groupleaderphonenumber: bool,
    if_add_groupleadermailaddress: bool,
) -> tuple[list[Group], dict[int, GroupCategory]]:
    """
    Lädt Gruppen (+ optional Hierarchie) und Kategorien und gibt beides
    normalisiert zurück.
    """
    group_ids = client.get_group_ids()
    groups: list[Group] = []

    raw_categories = client.get_group_categories()
    categories = {c.gcid: c for c in (normalize_category(rc) for rc in raw_categories)}

    for group_id in group_ids:
        group = normalize_group(client.get_group_by_id(group_id).get("data"))
        if group.category_id is not None:
            groups.append(group)
    
    if if_add_groupleader:
        add_group_leaders(groups, client, if_add_groupleaderphonenumber, if_add_groupleadermailaddress)
    
    return groups, categories

# Negativer ID-Bereich für synthetische Kategorie-Wurzelknoten, damit sie
# nie mit echten (positiven) ChurchTools-Gruppen-IDs kollidieren.
_CATEGORY_ROOT_ID_OFFSET = -1_000_000


def _category_root_id(category_id: int) -> int:
    return _CATEGORY_ROOT_ID_OFFSET - category_id


def build_category_forest(
    groups: list[Group],
    categories: dict[int, GroupCategory],
) -> list[OrgNode]:
    """
    Baut einen Wald, dessen Wurzelknoten die Gruppenkategorien sind.
    Innerhalb einer Kategorie bleibt die bestehende Eltern-Kind-
    Hierarchie der Gruppen erhalten.
    """
    # 1. Kategorie-IDs richtig extrahieren (unterstützt Listen und einzelne Ints)
    category_ids_present = set()
    for g in groups:
        if g.category_id is not None:
            if isinstance(g.category_id, list):
                category_ids_present.update(g.category_id)
            else:
                category_ids_present.add(g.category_id)

    forest: list[OrgNode] = []

    for cat_id in sorted(category_ids_present):
        category = categories.get(cat_id) or GroupCategory(
            gcid=cat_id, name="Ohne Kategorie" if cat_id == 0 else f"Kategorie {cat_id}"
        )
        
        # category_id sauber als Liste übergeben, wie in der Dataclass definiert
        root_group = Group(
            gid=_category_root_id(cat_id), # Vorhandene Hilfsfunktion
            name=category.name,
            category_id=[cat_id],
            is_category=True,
        )
        root_node = OrgNode(group=root_group)

        # 2. Mitglieder finden (Prüfen, ob cat_id in der Liste ist)
        members = []
        for g in groups:
            if g.category_id is None:
                continue
            if isinstance(g.category_id, list) and cat_id in g.category_id:
                members.append(g)
            elif not isinstance(g.category_id, list) and g.category_id == cat_id:
                members.append(g)

        # 3. Typensicherheit: Alle gids explizit als Integer für das Set und Mapping
        member_ids = {int(g.gid) for g in members}
        member_nodes = {int(g.gid): OrgNode(group=g) for g in members}

        for member in members:
            member_gid = int(member.gid)
            
            # 4. Typensicherheit für parent_ids (String vs. Int Problem beheben)
            safe_parent_ids = [int(pid) for pid in member.parent_ids] if member.parent_ids else []
            
            in_category_parents = [pid for pid in safe_parent_ids if pid in member_ids]

            if in_category_parents:
                for pid in in_category_parents:
                    member_nodes[pid].children.append(member_nodes[member_gid])
            else:
                root_node.children.append(member_nodes[member_gid])

        forest.append(root_node)

    return forest
