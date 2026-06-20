"""Relational-FM stand-in for Hour 13c.

KumoRFM's actual mechanism (table-agnostic encoding + relational graph
transformer + in-context learning) is well past tutorial scope and
requires the published model. This module gives you the *architectural
shape*: feed the bank's relational tables in, get a calibrated risk
score out, with feature-level interpretability.

What's here:
  - export_tables(): write each Pydantic entity type as a CSV
  - lotus_features(): derive a feature vector per account from the tables
  - score_account(): a small calibrated risk function with documented weights

The classifier is rule-weighted rather than learned. That choice is
deliberate — the pedagogical point is the *architectural shape* (tables →
score), not whether the model is trained or hand-coded. A production
deployment would swap the rule function for a learned model with the
same input/output signature; nothing else changes.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from kg_tutorial.data.schema import DatasetBundle


# ---------------------------------------------------------------------------
# Table export — relational form
# ---------------------------------------------------------------------------

def export_tables(bundle: DatasetBundle, out_dir: Path) -> dict[str, Path]:
    """Write each entity type as a flat CSV.

    Returns a map of table_name -> file path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    # persons
    p = out_dir / "persons.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "full_name", "is_pep", "pep_reason", "residence_country", "date_of_birth"])
        for x in bundle.persons:
            w.writerow([x.id, x.full_name, x.is_pep, x.pep_reason or "", x.residence_country, x.date_of_birth.isoformat()])
    written["persons"] = p

    # legal_entities
    p = out_dir / "legal_entities.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "legal_name", "jurisdiction", "entity_type", "incorporation_date"])
        for x in bundle.entities:
            w.writerow([x.id, x.legal_name, x.jurisdiction, x.entity_type.value, x.incorporation_date.isoformat()])
    written["legal_entities"] = p

    # accounts
    p = out_dir / "accounts.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "account_number", "holder_entity_id", "status", "open_date", "currency"])
        for x in bundle.accounts:
            w.writerow([x.id, x.account_number, x.holder_entity_id, x.status, x.open_date.isoformat(), x.currency])
    written["accounts"] = p

    # controls (relational form)
    p = out_dir / "controls.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "controller_id", "controlled_id", "control_type", "ownership_pct", "effective_from"])
        for x in bundle.controls:
            w.writerow([x.id, x.controller_id, x.controlled_id, x.control_type.value, x.ownership_pct or "", x.effective_from.isoformat()])
    written["controls"] = p

    # deposits
    p = out_dir / "deposits.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "account_id", "amount_eur", "value_date", "counterparty_name", "counterparty_country", "purpose_code"])
        for x in bundle.deposits:
            w.writerow([x.id, x.account_id, x.amount_eur, x.value_date.isoformat(), x.counterparty_name, x.counterparty_country, x.purpose_code])
    written["deposits"] = p

    # sanctions
    p = out_dir / "sanctions.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "list_source", "name", "aliases", "listed_date", "country"])
        for x in bundle.sanctions:
            w.writerow([x.id, x.list_source.value, x.name, "|".join(x.aliases), x.listed_date.isoformat(), x.country])
    written["sanctions"] = p

    return written


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

OFFSHORE_JURISDICTIONS = {"KY", "BVI", "PA", "LI", "BS", "BZ", "MH", "AE", "JE", "GG", "MT"}


@dataclass
class AccountFeatures:
    """Numerical features derived from the relational tables for one account."""

    account_id: str
    chain_depth: int = 0
    n_offshore_jurisdictions: int = 0
    pep_relative_depth: int = 99  # 99 = no PEP found in chain
    max_fuzzy_sanctions_score: float = 0.0
    n_adverse_media_on_chain: int = 0
    total_inbound_eur: float = 0.0
    counterparty_country_concentration: float = 0.0
    # Auxiliary
    reached_entity_ids: list[str] = field(default_factory=list)
    reached_person_ids: list[str] = field(default_factory=list)


def _walk_up_chain(bundle: DatasetBundle, entity_id: str, max_depth: int = 6) -> tuple[list[str], list[str], int]:
    """Walk up the control chain from `entity_id`. Returns reached entities, persons, depth."""
    parents: dict[str, list[str]] = {}
    for c in bundle.controls:
        parents.setdefault(c.controlled_id, []).append(c.controller_id)
    reached_e: set[str] = set()
    reached_p: set[str] = set()
    max_d = 0

    def walk(node: str, d: int):
        nonlocal max_d
        if d > max_depth:
            return
        for parent in parents.get(node, []):
            if parent.startswith("p_"):
                if parent not in reached_p:
                    reached_p.add(parent)
                    max_d = max(max_d, d)
            else:
                if parent not in reached_e:
                    reached_e.add(parent)
                    max_d = max(max_d, d)
                    walk(parent, d + 1)

    walk(entity_id, 1)
    return sorted(reached_e), sorted(reached_p), max_d


def lotus_features(bundle: DatasetBundle, account_id: str) -> AccountFeatures:
    """Compute the feature vector for one account.

    Each feature is a single number — exactly the shape a relational FM
    or a learned classifier would consume.
    """
    feats = AccountFeatures(account_id=account_id)
    account = next(a for a in bundle.accounts if a.id == account_id)
    holder = account.holder_entity_id

    # Walk the ownership chain
    reached_e, reached_p, max_d = _walk_up_chain(bundle, holder)
    feats.chain_depth = max_d
    feats.reached_entity_ids = reached_e
    feats.reached_person_ids = reached_p

    # Offshore-jurisdiction count
    holder_juris = next(e.jurisdiction for e in bundle.entities if e.id == holder)
    chain_jurisdictions = {holder_juris}
    for eid in reached_e:
        e = next((ent for ent in bundle.entities if ent.id == eid), None)
        if e:
            chain_jurisdictions.add(e.jurisdiction)
    feats.n_offshore_jurisdictions = len(chain_jurisdictions & OFFSHORE_JURISDICTIONS)

    # PEP depth
    persons = {p.id: p for p in bundle.persons}
    feats.pep_relative_depth = min(
        (1 if persons[pid].is_pep else 99 for pid in reached_p),
        default=99,
    )

    # Fuzzy sanctions score across counterparties
    deposits = [d for d in bundle.deposits if d.account_id == account_id]
    feats.total_inbound_eur = sum(d.amount_eur for d in deposits)
    best_fuzzy = 0.0
    for dep in deposits:
        for s in bundle.sanctions:
            for name in [s.name] + s.aliases:
                score = SequenceMatcher(None, dep.counterparty_name.upper(), name.upper()).ratio() * 100
                if score > best_fuzzy:
                    best_fuzzy = score
    feats.max_fuzzy_sanctions_score = best_fuzzy

    # Adverse media on chain
    mentioned_ids = set(reached_p) | set(reached_e) | {holder}
    feats.n_adverse_media_on_chain = sum(
        1 for a in bundle.adverse_media if any(m in mentioned_ids for m in a.mentioned_ids)
    )

    # Counterparty concentration (Herfindahl)
    by_country: dict[str, float] = {}
    for d in deposits:
        by_country[d.counterparty_country] = by_country.get(d.counterparty_country, 0.0) + d.amount_eur
    total = sum(by_country.values()) or 1.0
    feats.counterparty_country_concentration = sum((v / total) ** 2 for v in by_country.values())

    return feats


# ---------------------------------------------------------------------------
# Risk scoring — the stand-in classifier
# ---------------------------------------------------------------------------

@dataclass
class RiskScore:
    score: float                          # in [0, 1]
    band: str                              # LOW / MEDIUM / HIGH
    contributions: dict[str, float] = field(default_factory=dict)
    features: AccountFeatures | None = None


# Calibrated weights. In production these would be learned from labelled
# data; here they're documented so a reader can see the inductive bias.
WEIGHTS: dict[str, float] = {
    "chain_depth": 0.10,            # deep chains are obfuscation-prone
    "offshore_count": 0.20,         # offshore stacking is a known risk
    "pep_relative": 0.20,           # PEPs require EDD
    "fuzzy_sanctions": 0.30,        # the single most consequential signal
    "adverse_media": 0.10,          # corroborative
    "concentration": 0.10,          # single-country flow is a risk pattern
}


def score_account(features: AccountFeatures) -> RiskScore:
    """Apply the calibrated risk function.

    Each component is normalised to [0, 1] then weighted. The total is
    capped at 1.0. The intuition behind each normalisation is documented
    inline — production would replace this with a learned model whose
    SHAP/attention scores serve the same interpretability role.
    """
    f = features
    contribs: dict[str, float] = {}

    # chain_depth: 0 hops -> 0; >=4 hops -> 1.0
    contribs["chain_depth"] = min(f.chain_depth / 4.0, 1.0) * WEIGHTS["chain_depth"]

    # offshore_count: 0 -> 0; >= 3 -> 1.0
    contribs["offshore_count"] = min(f.n_offshore_jurisdictions / 3.0, 1.0) * WEIGHTS["offshore_count"]

    # pep_relative: 99 (no PEP) -> 0; 1 (PEP at top of chain) -> 1.0
    pep_contrib = 0.0 if f.pep_relative_depth >= 5 else 1.0 - (f.pep_relative_depth - 1) / 4.0
    contribs["pep_relative"] = max(pep_contrib, 0.0) * WEIGHTS["pep_relative"]

    # fuzzy_sanctions: <70 -> 0; >=85 -> 1.0; linear in between
    fs = f.max_fuzzy_sanctions_score
    fs_normalized = 0.0 if fs < 70 else min((fs - 70) / 15.0, 1.0)
    contribs["fuzzy_sanctions"] = fs_normalized * WEIGHTS["fuzzy_sanctions"]

    # adverse_media: 0 -> 0; >= 2 items -> 1.0
    contribs["adverse_media"] = min(f.n_adverse_media_on_chain / 2.0, 1.0) * WEIGHTS["adverse_media"]

    # concentration: 0.5 -> 0; 1.0 -> 1.0 (highly concentrated)
    contribs["concentration"] = max(0.0, (f.counterparty_country_concentration - 0.5) * 2.0) * WEIGHTS["concentration"]

    score = min(sum(contribs.values()), 1.0)
    if score < 0.3:
        band = "LOW"
    elif score < 0.6:
        band = "MEDIUM"
    else:
        band = "HIGH"

    return RiskScore(score=score, band=band, contributions=contribs, features=f)
