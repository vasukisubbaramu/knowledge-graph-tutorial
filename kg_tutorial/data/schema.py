"""Domain schema for the corporate-KYC + UBO worked example.

Why Pydantic instead of dataclasses or plain dicts:
- The schema is the spec — readable to a control manager, not just a programmer
- Validation catches synthesis bugs (e.g., orphan UBO references) immediately
- Easy to serialize/deserialize as JSON for the data files

Design choices worth noting:
- Every entity has a stable string `id` — used as the node id when we build
  the KG in Hours 4–6. The id is human-readable for debuggability.
- `ControlRelationship` is a separate top-level entity, not a field on Person
  or Entity. This decision matters: it's why graph models *naturally* express
  ownership chains and tabular models don't.
- Geographic risk is encoded as a list of country codes, NOT a single
  jurisdiction — a corporation in Liechtenstein with an account opener
  visiting from Russia is a very different risk profile from one fully in
  Liechtenstein. Hour 10 (hypergraphs) revisits this.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums — kept short and aligned with realistic CDD vocabularies
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    LLC = "LLC"
    PLC = "PLC"
    GMBH = "GmbH"
    SA = "SA"
    LTD = "Ltd"
    TRUST = "Trust"
    FOUNDATION = "Foundation"
    SPV = "SPV"  # Special Purpose Vehicle


class ControlType(str, Enum):
    UBO = "UBO"  # Ultimate Beneficial Owner (≥25%)
    DIRECTOR = "Director"
    SHAREHOLDER = "Shareholder"  # <25%, still material
    SIGNATORY = "AuthorizedSignatory"
    POA = "PowerOfAttorney"
    PARENT = "Parent"  # entity-to-entity
    SUBSIDIARY = "Subsidiary"


class AccountType(str, Enum):
    CURRENT = "Current"
    SAVINGS = "Savings"
    FIDUCIARY = "Fiduciary"
    ESCROW = "Escrow"


class SanctionsListSource(str, Enum):
    OFAC = "OFAC"
    UN = "UN"
    EU = "EU"
    UK_HMT = "UK_HMT"


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

class Person(BaseModel):
    id: str  # e.g. "p_john_q_public"
    full_name: str
    aliases: list[str] = Field(default_factory=list)
    date_of_birth: date
    nationalities: list[str]  # ISO-2 country codes; e.g. ["GB", "MT"] dual nat
    residence_country: str
    is_pep: bool = False
    pep_reason: str | None = None  # e.g. "nephew of MP Alice Public"
    sanctions_flag: bool = False  # naive boolean — Hour 2/3 shows why this is insufficient
    notes: str | None = None


class LegalEntity(BaseModel):
    id: str  # e.g. "e_acme_holdings"
    legal_name: str
    aliases: list[str] = Field(default_factory=list)  # trade names, transliterations
    entity_type: EntityType
    jurisdiction: str  # ISO-2 country code of incorporation
    registration_number: str
    incorporation_date: date
    registered_address: str
    sic_codes: list[str] = Field(default_factory=list)
    status: Literal["active", "dissolved", "inactive"] = "active"
    notes: str | None = None


class ControlRelationship(BaseModel):
    """A directed control edge.

    `controller` and `controlled` are entity ids. The model deliberately
    keeps the polymorphism implicit: `p_*` is a Person, `e_*` is an Entity.
    Validators catch ill-formed ids when the dataset loads.
    """

    id: str
    controller_id: str  # p_* or e_*
    controlled_id: str  # always e_*  (Persons cannot be controlled in our model)
    control_type: ControlType
    ownership_pct: float | None = None  # 0–100; None for non-ownership control (e.g. POA)
    effective_from: date
    effective_to: date | None = None  # None means current
    source: str  # "registry:Cayman", "CDD-form:section-4", etc. — provenance matters


class Account(BaseModel):
    id: str  # e.g. "a_gamma_ops_001"
    account_number: str
    account_type: AccountType
    holder_entity_id: str  # the LegalEntity that owns the account
    authorized_signatory_ids: list[str] = Field(default_factory=list)  # Person ids
    open_date: date
    status: Literal["pending", "active", "closed", "frozen"] = "active"
    currency: str = "EUR"


class Deposit(BaseModel):
    """A single inbound transaction.

    We model deposits as discrete events. Hour 10 reframes them as hyperedges
    (account, counterparty, source-of-funds, jurisdiction, time, amount,
    purpose) — that reframing is the *point* of that hour.
    """

    id: str
    account_id: str
    amount_eur: float  # normalized to EUR for cross-currency comparison
    original_amount: float
    original_currency: str
    value_date: date
    counterparty_name: str  # AS STATED IN THE WIRE — entity resolution is part of the lab
    counterparty_country: str  # ISO-2; "ZZ" if unknown
    purpose_code: str  # SWIFT-like; e.g. "GDDS" (goods), "CHAR" (charity)
    narrative: str  # the free-text reference field — what humans actually wrote


class SanctionsRecord(BaseModel):
    id: str
    list_source: SanctionsListSource
    name: str  # PRIMARY name as listed
    aliases: list[str] = Field(default_factory=list)  # the hard part: aka, transliterations
    listed_date: date
    country: str
    reason: str  # short justification text — useful for explainability


class AdverseMediaItem(BaseModel):
    """A short, dated news snippet implicating a person or entity."""

    id: str
    headline: str
    snippet: str  # ~150 words
    published_date: date
    source_outlet: str
    mentioned_ids: list[str]  # Person/Entity ids the snippet refers to
    topics: list[str]  # e.g. ["money-laundering", "tax-evasion", "litigation"]
    sentiment: Literal["negative", "neutral", "mixed"] = "negative"


class KYCDocument(BaseModel):
    """An unstructured document — the kind of thing Gen 1 RAG operates on.

    Examples:
      - CDD intake form (semi-structured narrative)
      - Memo from Relationship Manager
      - Bank policy excerpt
      - Source-of-funds questionnaire
      - Regulatory guidance paragraph
    """

    id: str
    title: str
    doc_type: Literal[
        "cdd_form",
        "rm_memo",
        "policy",
        "sof_questionnaire",
        "regulatory_guidance",
        "registry_extract",
        "news_clipping",
    ]
    body: str  # the actual text — chunked & embedded in Hour 2
    mentioned_ids: list[str] = Field(default_factory=list)  # Person/Entity ids referenced
    created_date: date


# ---------------------------------------------------------------------------
# The full bundle written to disk
# ---------------------------------------------------------------------------

class DatasetBundle(BaseModel):
    """The synthetic dataset, written as a single JSON file for portability."""

    persons: list[Person]
    entities: list[LegalEntity]
    controls: list[ControlRelationship]
    accounts: list[Account]
    deposits: list[Deposit]
    sanctions: list[SanctionsRecord]
    adverse_media: list[AdverseMediaItem]
    documents: list[KYCDocument]

    def stats(self) -> dict[str, int]:
        return {
            "persons": len(self.persons),
            "entities": len(self.entities),
            "controls": len(self.controls),
            "accounts": len(self.accounts),
            "deposits": len(self.deposits),
            "sanctions": len(self.sanctions),
            "adverse_media": len(self.adverse_media),
            "documents": len(self.documents),
        }
