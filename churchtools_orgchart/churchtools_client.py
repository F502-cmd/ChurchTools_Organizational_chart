"""
Schlanker HTTP-Client für die ChurchTools REST-API.

Wichtiger Hinweis zur API-Stabilität
-------------------------------------
ChurchTools dokumentiert seine REST-API pro Instanz live per
OpenAPI/Swagger unter ``https://<gemeinde-link>.church.tools/api``. Feld-
und Endpunktnamen können sich je nach installierter Version leicht
unterscheiden (das gilt insbesondere für Gruppenkategorien).
Bevor dieses Skript produktiv eingesetzt wird,
lohnt sich ein kurzer Abgleich in ``orgchart_builder.py``
mit der Swagger-UI Ihrer eigenen Instanz.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger("churchtools_orgchart")


class ChurchToolsAPIError(RuntimeError):
    """Wird ausgelöst, wenn die ChurchTools-API einen Fehler zurückliefert."""


class ChurchToolsClient:
    """
    Authentifizierung erfolgt über ein persönliches API-/Login-Token
    (ChurchTools -> eigenes Profil -> Reiter "API" -> Token generieren),
    das im Header ``Authorization: Login <token>`` mitgeschickt wird.
    Das ist der von ChurchTools empfohlene Weg für Server-zu-Server-
    Zugriffe (kein Session-Cookie, kein Ablauf durch Logout).
    """

    def __init__(
        self,
        base_url: str,
        login_token: str,
        timeout: float = 15.0,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Login {login_token}",
                "Accept": "application/json",
            }
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    # -- Low-Level -----------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.base_url}/api{path}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            retryable = True
            try:
                response = self._session.request(method, url, timeout=self.timeout, **kwargs)

                if response.status_code == 401:
                    retryable = False
                    raise ChurchToolsAPIError("Nicht autorisiert - Login-Token prüfen.")
                if response.status_code == 403:
                    retryable = False
                    raise ChurchToolsAPIError(f"Keine Berechtigung für {url}.")
                if response.status_code == 404:
                    # Endpunkt existiert auf dieser Instanz/Version nicht - ein
                    # erneuter Versuch würde das Ergebnis nicht ändern.
                    retryable = False
                    raise ChurchToolsAPIError(
                        f"Endpunkt nicht gefunden (404) bei {url}. "
                        f"Swagger-UI der Instanz prüfen: {self.base_url}/api"
                    )
                if response.status_code == 429:
                    raise ChurchToolsAPIError(f"Rate-Limit erreicht bei {url}.")
                if response.status_code >= 500:
                    raise ChurchToolsAPIError(f"Serverfehler {response.status_code} bei {url}")
                if response.status_code >= 400:
                    retryable = False
                    raise ChurchToolsAPIError(
                        f"Fehler {response.status_code} bei {url}: {response.text[:300]}"
                    )
                if not response.content:
                    return {}
                return response.json()

            except requests.RequestException as exc:
                last_exc = exc
            except ChurchToolsAPIError as exc:
                last_exc = exc
                if not retryable:
                    raise

            if attempt < self.max_retries:
                wait = self.retry_backoff**attempt
                logger.warning(
                    "Versuch %s/%s für %s fehlgeschlagen (%s) - retry in %.1fs",
                    attempt,
                    self.max_retries,
                    url,
                    last_exc,
                    wait,
                )
                time.sleep(wait)

        assert last_exc is not None
        raise last_exc

    def _get_paginated(self, path: str, params: Optional[dict] = None) -> list[dict]:
        """
        Holt alle Seiten eines paginierten Endpunkts ein. ChurchTools
        liefert Listen typischerweise als
        ``{"data": [...], "meta": {"pagination": {...}}}``.
        """
        params = dict(params or {})
        params.setdefault("limit", 100)
        page = 1
        items: list[dict] = []

        while True:
            params["page"] = page
            payload = self._request("GET", path, params=params)
            data = payload.get("data", payload if isinstance(payload, list) else [])

            if isinstance(data, dict):
                return [data]

            items.extend(data)
            pagination = payload.get("meta", {}).get("pagination", {})
            last_page = pagination.get("lastPage", page)

            if page >= last_page or not data:
                break
            page += 1

        return items

    # -- High-Level ------------------------------------------------------

    def whoami(self) -> dict:
        """Einfacher Verbindungs-/Auth-Test."""
        return self._request("GET", "/whoami")

    def get_group_ids(self) -> list[dict]:
        """Alle für den API-Nutzer sichtbaren Gruppen-IDs."""
        return self._get_paginated("/groups/ids")
    
    def get_group_by_id(self, group_id: int) -> dict:
        """Details zu einer einzelnen Gruppe (Rohdaten)."""
        return self._request("GET", f"/groups/{group_id}")

    def get_group_categories(self) -> list[dict]:
        """Alle für den API-Benutzer sichtbaren Kategorien."""
        return self._get_paginated("/group/groupcategories")
    
    def get_group_members_by_id(self, group_id: int, role_ids: list[int]) -> dict:
        """Details zu den Mitgliedern einer Gruppe (Rohdaten)."""
        return self._request("GET", f"/groups/{group_id}/members", params={"role_ids[]": role_ids})
    
    def get_person_by_id(self, personId: int) -> dict:
        """Details zu einer Person (Rohdaten)."""
        return self._request("GET", f"/persons/{personId}")