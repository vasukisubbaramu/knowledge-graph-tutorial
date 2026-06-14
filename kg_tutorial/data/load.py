"""Load the synthetic dataset and offer quick lookup helpers.

Used in every notebook from Hour 0 onwards. Importing this is cheap; it
only reads the JSON file when `load()` is called.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from kg_tutorial import config
from kg_tutorial.data.schema import (
    Account,
    AdverseMediaItem,
    ControlRelationship,
    DatasetBundle,
    Deposit,
    KYCDocument,
    LegalEntity,
    Person,
    SanctionsRecord,
)


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> DatasetBundle:
    path = path or (config.DATA_DIR / "dataset.json")
    if not path.exists():
        raise FileNotFoundError(
            f"Synthetic dataset not found at {path}. "
            "Run: uv run python -m kg_tutorial.data.generate"
        )
    return DatasetBundle.model_validate_json(path.read_text())


# ---- Convenience getters --------------------------------------------------

def person(pid: str) -> Person:
    return next(p for p in load().persons if p.id == pid)


def entity(eid: str) -> LegalEntity:
    return next(e for e in load().entities if e.id == eid)


def account(aid: str) -> Account:
    return next(a for a in load().accounts if a.id == aid)


def document(did: str) -> KYCDocument:
    return next(d for d in load().documents if d.id == did)


def deposits_for(account_id: str) -> list[Deposit]:
    return [d for d in load().deposits if d.account_id == account_id]


def controls_for(controller_id: str) -> list[ControlRelationship]:
    return [c for c in load().controls if c.controller_id == controller_id]


def sanctions_records() -> list[SanctionsRecord]:
    return list(load().sanctions)


def adverse_media_for(entity_or_person_id: str) -> list[AdverseMediaItem]:
    return [a for a in load().adverse_media if entity_or_person_id in a.mentioned_ids]
