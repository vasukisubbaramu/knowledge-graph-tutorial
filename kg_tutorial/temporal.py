"""Bi-temporal helpers for Hour 13b.

The existing Lotus dataset already carries the temporal fields:
  - ControlRelationship.effective_from / .effective_to
  - SanctionsRecord.listed_date
  - AdverseMediaItem.published_date
  - Deposit.value_date
  - Account.open_date
  - LegalEntity.incorporation_date

This module adds the *queries* through those fields that the main tutorial
deferred. Nothing here is TIE — these are the schema-level approximations
that production platforms actually run today. The TIE-class mechanism (an
embedding-level temporal model) is sketched conceptually in the notebook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from kg_tutorial.data.schema import (
    AdverseMediaItem,
    ControlRelationship,
    DatasetBundle,
    Deposit,
    SanctionsRecord,
)


# ---------------------------------------------------------------------------
# Effective-at queries
# ---------------------------------------------------------------------------

def effective_controls_at(bundle: DatasetBundle, as_of: date) -> list[ControlRelationship]:
    """Return every control edge that was valid at `as_of`.

    A control is valid if effective_from <= as_of <= effective_to (or
    effective_to is None, meaning the relationship is still current at
    the time of the query).
    """
    out: list[ControlRelationship] = []
    for c in bundle.controls:
        if c.effective_from > as_of:
            continue
        if c.effective_to is not None and c.effective_to < as_of:
            continue
        out.append(c)
    return out


def effective_sanctions_at(bundle: DatasetBundle, as_of: date) -> list[SanctionsRecord]:
    """Sanctions entries that had been listed by `as_of`.

    Production lists usually have a delisting date too; our synthetic
    data does not model delisting. Real-world delistings are rare for the
    list_kinds we care about (OFAC SDN).
    """
    return [s for s in bundle.sanctions if s.listed_date <= as_of]


def effective_adverse_media_at(bundle: DatasetBundle, as_of: date) -> list[AdverseMediaItem]:
    return [a for a in bundle.adverse_media if a.published_date <= as_of]


def effective_deposits_at(bundle: DatasetBundle, as_of: date) -> list[Deposit]:
    """Deposits that have already occurred by `as_of`."""
    return [d for d in bundle.deposits if d.value_date <= as_of]


# ---------------------------------------------------------------------------
# Snapshot — a temporally-filtered bundle
# ---------------------------------------------------------------------------

def bundle_at(bundle: DatasetBundle, as_of: date) -> DatasetBundle:
    """Return a DatasetBundle as it would have appeared on `as_of`.

    Persons and LegalEntities are kept (they don't really come or go on a
    timescale that matters for the tutorial — births and incorporations
    are filtered for completeness, but the Lotus persons all predate any
    relevant date).
    """
    return DatasetBundle(
        persons=[p for p in bundle.persons if p.date_of_birth <= as_of],
        entities=[e for e in bundle.entities if e.incorporation_date <= as_of],
        controls=effective_controls_at(bundle, as_of),
        accounts=[a for a in bundle.accounts if a.open_date <= as_of],
        deposits=effective_deposits_at(bundle, as_of),
        sanctions=effective_sanctions_at(bundle, as_of),
        adverse_media=effective_adverse_media_at(bundle, as_of),
        documents=bundle.documents,  # docs aren't temporal in our schema
    )


# ---------------------------------------------------------------------------
# Snapshot diffs
# ---------------------------------------------------------------------------

@dataclass
class SnapshotDiff:
    added_controls: list[str] = field(default_factory=list)
    removed_controls: list[str] = field(default_factory=list)
    added_sanctions: list[str] = field(default_factory=list)
    added_adverse_media: list[str] = field(default_factory=list)
    added_deposits: list[str] = field(default_factory=list)


def diff(t1: date, t2: date, *, bundle: DatasetBundle) -> SnapshotDiff:
    """What changed between two dates? `t1` is earlier, `t2` is later."""
    s1 = bundle_at(bundle, t1)
    s2 = bundle_at(bundle, t2)
    ids = lambda items: {x.id for x in items}
    return SnapshotDiff(
        added_controls=sorted(ids(s2.controls) - ids(s1.controls)),
        removed_controls=sorted(ids(s1.controls) - ids(s2.controls)),
        added_sanctions=sorted(ids(s2.sanctions) - ids(s1.sanctions)),
        added_adverse_media=sorted(ids(s2.adverse_media) - ids(s1.adverse_media)),
        added_deposits=sorted(ids(s2.deposits) - ids(s1.deposits)),
    )


# ---------------------------------------------------------------------------
# A canonical set of audit-relevant snapshot dates
# ---------------------------------------------------------------------------

LOTUS_SNAPSHOT_DATES: list[tuple[str, date]] = [
    ("Q1 2020", date(2020, 3, 31)),
    ("Q1 2022", date(2022, 3, 31)),
    ("Q1 2024", date(2024, 3, 31)),   # Before OFAC lists Atlas Wirecorp
    ("Q3 2024", date(2024, 9, 30)),   # After OFAC listing, after adverse media
    ("Q2 2026", date(2026, 6, 30)),   # Now — Lotus case is being decided
]
