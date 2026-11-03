"""Datenklassen für das Organigramm-Toolkit."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GroupCategory:
    """Eine ChurchTools-Gruppenkategorie (z.B. 'Kinder & Jugend', 'Leitung')."""

    gcid: int
    name: str
    color: Optional[str] = None  # z.B. "#4C72B0", falls in CT hinterlegt


@dataclass
class Group:
    """Normalisierte Repräsentation einer ChurchTools-Gruppe."""

    gid: int
    name: str
    group_type: int = None
    parent_ids: list[int] = field(default_factory=list)
    category_id: list[int] = field(default_factory=list)
    member_count: Optional[int] = None
    is_public: bool = False
    is_category: bool = False
    leaders: list[dict] = field(default_factory=list)

@dataclass
class OrgNode:
    """Ein Knoten im Organigramm-Baum (Wrapper um eine Gruppe + Kinder)."""

    group: Group
    children: list["OrgNode"] = field(default_factory=list)
