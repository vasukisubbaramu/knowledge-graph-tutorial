"""Generate the synthetic corporate-KYC + UBO dataset.

The dataset is built around ONE pathological case ("Project Lotus") plus
noise entities, so the tutorial has a worked example that demonstrably
exposes Gen 1's failures and rewards Gen 2/3.

The Lotus chain (memorize this — it appears in every hour):

    John Q. Public (PEP-relative, UK/MC)
        ├── 50% owns ──> ACME Holdings Ltd (Cayman SPV)
        │                       ├── 100% owns ──> AlphaBeta Trading SA (Panama)
        │                       │                       └── 75% owns ──> Gamma Operations GmbH (Liechtenstein)
        │                       │                                              └── owns ──> Account a_gamma_001 (the applicant)
        │                       │                                                                  ↑
        │                       │                                                                  │
        └── Director of ──> Atlas Wirecorp ──────────── deposits EUR 500K ──────────────────────────┘
                                  ↑
                                  └── listed on OFAC under alias "Atlas Wire Corporation"
                                       (the alias-mismatch is the lab's hardest test)

Run:  uv run python -m kg_tutorial.data.generate
Writes: data/synthetic/dataset.json
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

from kg_tutorial import config
from kg_tutorial.data.schema import (
    Account,
    AccountType,
    AdverseMediaItem,
    ControlRelationship,
    ControlType,
    DatasetBundle,
    Deposit,
    EntityType,
    KYCDocument,
    LegalEntity,
    Person,
    SanctionsListSource,
    SanctionsRecord,
)

SEED = 42


# ---------------------------------------------------------------------------
# The hand-crafted Lotus case (lives in code so we can reason about it)
# ---------------------------------------------------------------------------

def _lotus_persons() -> list[Person]:
    return [
        Person(
            id="p_john_q_public",
            full_name="John Q. Public",
            aliases=["J. Q. Public", "Johnny Public"],
            date_of_birth=date(1978, 4, 12),
            nationalities=["GB"],
            residence_country="MC",  # Monaco
            is_pep=True,
            pep_reason=(
                "Nephew of Alice Public, Member of Parliament since 2019. "
                "Classified as PEP-relative under FATF Rec. 12 by our policy."
            ),
            sanctions_flag=False,  # not directly sanctioned — the trap
            notes="UBO of ACME Holdings; director of Atlas Wirecorp.",
        ),
        Person(
            id="p_alice_public",
            full_name="Alice Public, MP",
            aliases=["The Hon. Alice Public"],
            date_of_birth=date(1952, 9, 30),
            nationalities=["GB"],
            residence_country="GB",
            is_pep=True,
            pep_reason="Member of Parliament, House of Commons (sitting).",
            notes="Aunt of John Q. Public. Not herself implicated.",
        ),
        Person(
            id="p_maria_rossi",
            full_name="Maria Rossi",
            date_of_birth=date(1985, 1, 22),
            nationalities=["IT"],
            residence_country="LI",  # Liechtenstein
            is_pep=False,
            notes="Local director of Gamma Operations GmbH. Nominee per LI registry.",
        ),
        Person(
            id="p_tomas_velasco",
            full_name="Tomás Velasco",
            aliases=["Tom Velasco", "T. Velasco"],
            date_of_birth=date(1970, 11, 5),
            nationalities=["PA"],
            residence_country="PA",
            is_pep=False,
            notes="Director of AlphaBeta Trading SA. Director of 14 other Panamanian SPVs.",
        ),
    ]


def _lotus_entities() -> list[LegalEntity]:
    return [
        LegalEntity(
            id="e_gamma_ops",
            legal_name="Gamma Operations GmbH",
            aliases=["Gamma Ops", "Gamma GmbH"],
            entity_type=EntityType.GMBH,
            jurisdiction="LI",
            registration_number="FL-0002.123.456-7",
            incorporation_date=date(2021, 3, 15),
            registered_address="Lettstrasse 32, 9490 Vaduz, Liechtenstein",
            sic_codes=["7011"],  # Holding companies
            notes="Applicant entity. Stated purpose: 'consulting and trading in industrial commodities.'",
        ),
        LegalEntity(
            id="e_alphabeta_trading",
            legal_name="AlphaBeta Trading SA",
            entity_type=EntityType.SA,
            jurisdiction="PA",
            registration_number="2018-543-PA",
            incorporation_date=date(2018, 6, 1),
            registered_address="MMG Tower, Avenida Paseo del Mar, Panama City",
            sic_codes=["5099"],
            notes="Panamanian SA. Owns 75% of Gamma Operations.",
        ),
        LegalEntity(
            id="e_acme_holdings",
            legal_name="ACME Holdings Ltd",
            aliases=["ACME Holdings", "Acme Hldgs"],
            entity_type=EntityType.SPV,
            jurisdiction="KY",  # Cayman
            registration_number="CY-329910",
            incorporation_date=date(2015, 11, 9),
            registered_address="P.O. Box 309, Ugland House, Grand Cayman, KY1-1104",
            sic_codes=["7011"],
            notes="Cayman SPV. Owns 100% of AlphaBeta Trading SA.",
        ),
        LegalEntity(
            id="e_atlas_wirecorp",
            legal_name="Atlas Wirecorp",
            aliases=["Atlas WireCorp", "Atlas Wire Corp", "AtlasWire"],
            entity_type=EntityType.LTD,
            jurisdiction="AE",  # UAE
            registration_number="UAE-FZE-998877",
            incorporation_date=date(2019, 2, 11),
            registered_address="JLT Cluster X, Dubai, UAE",
            sic_codes=["6199"],
            notes=(
                "Source of the inbound EUR 500K deposit. "
                "Strong-but-imperfect match to an OFAC-listed name 'Atlas Wire Corporation'."
            ),
        ),
    ]


def _lotus_controls() -> list[ControlRelationship]:
    return [
        ControlRelationship(
            id="c_john_owns_acme",
            controller_id="p_john_q_public",
            controlled_id="e_acme_holdings",
            control_type=ControlType.UBO,
            ownership_pct=50.0,
            effective_from=date(2015, 11, 9),
            source="CDD-form:section-4",
        ),
        ControlRelationship(
            id="c_acme_owns_alphabeta",
            controller_id="e_acme_holdings",
            controlled_id="e_alphabeta_trading",
            control_type=ControlType.PARENT,
            ownership_pct=100.0,
            effective_from=date(2018, 6, 1),
            source="registry:Panama",
        ),
        ControlRelationship(
            id="c_alphabeta_owns_gamma",
            controller_id="e_alphabeta_trading",
            controlled_id="e_gamma_ops",
            control_type=ControlType.PARENT,
            ownership_pct=75.0,
            effective_from=date(2021, 3, 15),
            source="registry:Liechtenstein",
        ),
        ControlRelationship(
            id="c_maria_directs_gamma",
            controller_id="p_maria_rossi",
            controlled_id="e_gamma_ops",
            control_type=ControlType.DIRECTOR,
            ownership_pct=None,
            effective_from=date(2021, 3, 15),
            source="registry:Liechtenstein",
        ),
        ControlRelationship(
            id="c_tomas_directs_alphabeta",
            controller_id="p_tomas_velasco",
            controlled_id="e_alphabeta_trading",
            control_type=ControlType.DIRECTOR,
            ownership_pct=None,
            effective_from=date(2018, 6, 1),
            source="registry:Panama",
        ),
        ControlRelationship(
            id="c_john_directs_atlas",
            controller_id="p_john_q_public",
            controlled_id="e_atlas_wirecorp",
            control_type=ControlType.DIRECTOR,
            ownership_pct=None,
            effective_from=date(2019, 2, 11),
            source="UAE-FZA-registry",
        ),
    ]


def _lotus_sanctions() -> list[SanctionsRecord]:
    return [
        SanctionsRecord(
            id="s_atlas",
            list_source=SanctionsListSource.OFAC,
            name="ATLAS WIRE CORPORATION",
            aliases=["Atlas Wire Co.", "Atlas Wire Corp.", "Атлас Уайр"],
            listed_date=date(2024, 7, 15),
            country="AE",
            reason=(
                "Designated under Executive Order 13224 for providing material support "
                "to a designated terrorist financing network."
            ),
        ),
    ]


def _lotus_documents() -> list[KYCDocument]:
    return [
        KYCDocument(
            id="d_cdd_gamma_ops",
            title="Customer Due Diligence Form — Gamma Operations GmbH",
            doc_type="cdd_form",
            created_date=date(2026, 5, 20),
            mentioned_ids=["e_gamma_ops", "e_alphabeta_trading", "e_acme_holdings", "p_john_q_public", "p_maria_rossi"],
            body="""\
CUSTOMER DUE DILIGENCE FORM
Reference: CDD-2026-04417
Date: 20 May 2026

Section 1 — Applicant entity
    Legal name: Gamma Operations GmbH
    Type: Gesellschaft mit beschränkter Haftung
    Jurisdiction of incorporation: Liechtenstein
    Registered office: Lettstrasse 32, 9490 Vaduz
    Stated business activity: "Consulting and trading in industrial commodities."
    Date of incorporation: 15 March 2021

Section 2 — Local director
    Name: Maria Rossi
    Nationality: Italian
    Address: c/o registered office
    Status: Nominee director per Liechtenstein registry.

Section 3 — Direct shareholders
    AlphaBeta Trading SA (Panama) holds 75% of issued share capital.
    Remaining 25% held by undisclosed minority shareholders ("treasury").

Section 4 — Ultimate beneficial ownership
    Client states that the ultimate beneficial owner above the 25% threshold
    is Mr John Q. Public, a British national resident in Monaco, holding 50%
    of ACME Holdings Ltd (Cayman Islands), the 100% parent of AlphaBeta
    Trading SA.

Section 5 — Source of funds
    The opening deposit (anticipated EUR 500,000) is described as
    "operational treasury transfer from group affiliate." No supporting
    invoice or contract was provided.

Section 6 — Anticipated activity
    Inbound: EUR 1–5 million per year, multiple counterparties.
    Outbound: payments to "industrial suppliers in Asia and the Middle East."

Section 7 — Risk factors observed
    - Multi-jurisdictional ownership chain (LI → PA → KY).
    - UBO resides in Monaco (high-net-worth jurisdiction).
    - Group operates in UAE through a related entity (Atlas Wirecorp).
    - No commercial track record at the operating-company level.
""",
        ),
        KYCDocument(
            id="d_rm_memo",
            title="RM Memo — Project Lotus introduction",
            doc_type="rm_memo",
            created_date=date(2026, 5, 18),
            mentioned_ids=["e_gamma_ops", "p_john_q_public"],
            body="""\
MEMO
From: K. Andersson, Senior Relationship Manager
To: Onboarding Committee
Re: Project Lotus — proposed onboarding of Gamma Operations GmbH

I am introducing Gamma Operations GmbH, a Liechtenstein vehicle whose
group I have known since 2019 through a mutual contact in Monaco. The UBO,
Mr John Q. Public, is a discreet British investor with significant private
wealth and a long track record in commodity trading. He prefers not to be
visible on European registers and uses the Cayman ACME Holdings structure
for this purpose.

Mr Public has indicated that ANNUAL deposit volumes through the new account
will reach EUR 5 million in year one, growing thereafter. He has expressed
mild irritation at the volume of documentation requested in earlier stages
and asked that the onboarding be expedited if at all possible.

There is no adverse information of which I am aware. I recommend approval
subject to standard enhanced due diligence for the multi-jurisdictional
ownership chain.
""",
        ),
        KYCDocument(
            id="d_sof_questionnaire",
            title="Source of Funds Questionnaire — Atlas Wirecorp deposit",
            doc_type="sof_questionnaire",
            created_date=date(2026, 6, 2),
            mentioned_ids=["e_gamma_ops", "e_atlas_wirecorp"],
            body="""\
SOURCE OF FUNDS QUESTIONNAIRE
Reference: SOF-2026-04417-A
Account: Gamma Operations GmbH (a_gamma_001)
Transaction: Inbound wire EUR 500,000, value date 03 June 2026
Originating party (as stated in SWIFT MT103): "ATLAS WIRECORP"
Originating country: AE

Client response to question "What is the economic purpose of this transfer?"
    "Inter-company funding for working capital. Atlas Wirecorp is a UAE
    affiliate within the same beneficial-owner group."

Client response to question "Please describe the commercial relationship
between the originator and beneficiary."
    "Both entities are ultimately controlled by Mr John Q. Public via ACME
    Holdings. Atlas Wirecorp provides treasury services to the group."

No invoice, contract, or board resolution was provided in support of this
transfer.
""",
        ),
        KYCDocument(
            id="d_policy_pep",
            title="Internal Policy — Politically Exposed Persons (excerpt)",
            doc_type="policy",
            created_date=date(2025, 1, 15),
            body="""\
INTERNAL POLICY — POLITICALLY EXPOSED PERSONS (excerpt)

3.2 Scope of "close associate" and "family member"
A "family member" of a PEP, for the purpose of this policy, includes:
  (a) spouses and partners;
  (b) children and their spouses or partners;
  (c) parents;
  (d) siblings;
  (e) nephews and nieces — see note below.

Note on (e): While FATF Recommendation 12 does not strictly require coverage
of nephews and nieces, this Bank's policy elects to treat them as PEP-
relatives, subject to enhanced due diligence (EDD), where the underlying
PEP is currently sitting in a national legislature.

3.3 Required EDD measures for PEPs and PEP-relatives
  - Senior management sign-off on onboarding;
  - Establishment and ongoing review of source of wealth (NOT only source of
    funds);
  - Enhanced monitoring of transactions for a minimum of 12 months.
""",
        ),
        KYCDocument(
            id="d_policy_sanctions",
            title="Internal Policy — Sanctions screening tolerance",
            doc_type="policy",
            created_date=date(2024, 11, 1),
            body="""\
INTERNAL POLICY — SANCTIONS SCREENING TOLERANCE

The Bank screens all counterparties against OFAC, UN, EU and UK HM Treasury
consolidated lists at the following points:
  (a) at onboarding;
  (b) on every value-date for inbound and outbound transactions over
      EUR 10,000;
  (c) overnight, against the full customer book, on every list refresh.

Tolerance: Fuzzy name matches with a score >= 85 must be escalated to L2
Sanctions Operations regardless of any local context arguments. Strict
matches (score 100) trigger an immediate hold pending investigation.

Particular attention is required where any of the following are present:
  - the originator's spelling appears slightly altered from the list entry
    (e.g. trailing 'Corporation' vs 'Corp');
  - the country of incorporation aligns with the listed entity;
  - a beneficial owner of the counterparty is shared with the customer.

It is NOT acceptable to dismiss a fuzzy match on the basis that the local
business unit is comfortable with the customer.
""",
        ),
        KYCDocument(
            id="d_news_offshore",
            title="News clipping — 'Offshore vehicles for British wealth' (2024)",
            doc_type="news_clipping",
            created_date=date(2024, 10, 8),
            mentioned_ids=["p_john_q_public", "e_acme_holdings"],
            body="""\
[The Financial Examiner, 8 October 2024]

OFFSHORE VEHICLES FOR BRITISH WEALTH

Among the structures examined by this paper in connection with the recent
leak of Cayman registry data is ACME Holdings Ltd, a Cayman SPV held via
Ugland House. ACME's principal owner is reported by sources familiar with
the matter to be Mr John Q. Public, a British national long resident in
Monaco. ACME holds a Panamanian subsidiary, AlphaBeta Trading SA, which in
turn holds operating companies in Liechtenstein and the UAE.

Mr Public is a nephew of the sitting MP Alice Public; he has not been the
subject of any criminal proceedings. A representative for Mr Public declined
to comment for this article.
""",
        ),
        KYCDocument(
            id="d_regulatory_ubo",
            title="Regulatory guidance — UBO disclosure under 6MLD",
            doc_type="regulatory_guidance",
            created_date=date(2023, 12, 1),
            body="""\
REGULATORY GUIDANCE — ULTIMATE BENEFICIAL OWNERSHIP UNDER 6MLD

A beneficial owner is any natural person who ultimately owns or controls
the customer, whether directly or indirectly. Where ownership is structured
through a chain of legal entities, the obliged entity must trace the
ownership chain to its terminating natural person(s).

A 25% (twenty-five percent) ownership threshold is indicative but not
exhaustive: control may exist below the 25% threshold by virtue of
contractual arrangements, voting rights, or veto power.

The obliged entity must document the steps taken to verify ownership chains
spanning multiple jurisdictions, and must independently verify the
declaration where possible — for example, by consulting the relevant
beneficial ownership register in each jurisdiction of incorporation. Where
no such register exists or the register is not accessible, the obliged
entity must record this fact and apply enhanced ongoing monitoring.
""",
        ),
    ]


def _lotus_adverse_media() -> list[AdverseMediaItem]:
    return [
        AdverseMediaItem(
            id="am_offshore_clipping_2024",
            headline="Offshore vehicles for British wealth",
            snippet=(
                "ACME Holdings Ltd, a Cayman SPV held via Ugland House, is "
                "reported by sources familiar with the matter to be principally "
                "owned by Mr John Q. Public, a British national resident in Monaco. "
                "Mr Public is a nephew of sitting MP Alice Public."
            ),
            published_date=date(2024, 10, 8),
            source_outlet="The Financial Examiner",
            mentioned_ids=["p_john_q_public", "e_acme_holdings"],
            topics=["offshore-structures", "PEP-relative"],
            sentiment="negative",
        ),
        AdverseMediaItem(
            id="am_panama_directors_2022",
            headline="Panama nominees: directors with hundreds of mandates",
            snippet=(
                "Among the names appearing on more than 12 corporate boards in "
                "Panama, Tomás Velasco was identified as director of fourteen "
                "vehicles linked through ACME Holdings of Cayman."
            ),
            published_date=date(2022, 4, 30),
            source_outlet="Latin Investigative Network",
            mentioned_ids=["p_tomas_velasco", "e_acme_holdings"],
            topics=["nominee-directorship"],
            sentiment="mixed",
        ),
    ]


def _lotus_account_and_deposits() -> tuple[Account, list[Deposit]]:
    account = Account(
        id="a_gamma_001",
        account_number="LI98 0880 0000 0294 4717 2",
        account_type=AccountType.CURRENT,
        holder_entity_id="e_gamma_ops",
        authorized_signatory_ids=["p_maria_rossi", "p_john_q_public"],
        open_date=date(2026, 5, 30),
        status="pending",  # account-opening review is the lab's question
        currency="EUR",
    )
    deposits = [
        Deposit(
            id="dep_001",
            account_id="a_gamma_001",
            amount_eur=500_000.00,
            original_amount=500_000.00,
            original_currency="EUR",
            value_date=date(2026, 6, 3),
            counterparty_name="ATLAS WIRECORP",  # NOTE the variant spelling
            counterparty_country="AE",
            purpose_code="INTC",
            narrative="Intercompany treasury transfer, ref. ALPHA-2026-Q2",
        ),
    ]
    return account, deposits


# ---------------------------------------------------------------------------
# Noise generators
# ---------------------------------------------------------------------------

NOISE_ENTITY_TYPES = [EntityType.LLC, EntityType.PLC, EntityType.GMBH, EntityType.LTD, EntityType.SA]
NOISE_COUNTRIES = ["DE", "FR", "ES", "IT", "NL", "BE", "IE", "GB", "PT", "AT", "FI", "SE", "DK"]


def _make_noise_persons(fake: Faker, n: int) -> list[Person]:
    out: list[Person] = []
    for i in range(n):
        name = fake.name()
        out.append(
            Person(
                id=f"p_noise_{i:03d}",
                full_name=name,
                date_of_birth=fake.date_of_birth(minimum_age=25, maximum_age=78),
                nationalities=[random.choice(NOISE_COUNTRIES)],
                residence_country=random.choice(NOISE_COUNTRIES),
                is_pep=False,
            )
        )
    return out


def _make_noise_entities(fake: Faker, n: int) -> list[LegalEntity]:
    out: list[LegalEntity] = []
    for i in range(n):
        country = random.choice(NOISE_COUNTRIES)
        out.append(
            LegalEntity(
                id=f"e_noise_{i:03d}",
                legal_name=fake.company(),
                entity_type=random.choice(NOISE_ENTITY_TYPES),
                jurisdiction=country,
                registration_number=f"{country}-{fake.numerify('######')}",
                incorporation_date=fake.date_between(start_date=date(2005, 1, 1), end_date=date(2024, 1, 1)),
                registered_address=fake.address().replace("\n", ", "),
                sic_codes=[random.choice(["6201", "7011", "4690", "4789", "8121"])],
            )
        )
    return out


def _make_noise_sanctions(fake: Faker, n: int) -> list[SanctionsRecord]:
    sources = list(SanctionsListSource)
    out: list[SanctionsRecord] = []
    for i in range(n):
        out.append(
            SanctionsRecord(
                id=f"s_noise_{i:03d}",
                list_source=random.choice(sources),
                name=fake.company().upper(),
                aliases=[fake.company().upper() for _ in range(random.randint(0, 2))],
                listed_date=fake.date_between(start_date=date(2018, 1, 1), end_date=date(2026, 1, 1)),
                country=random.choice(["RU", "IR", "KP", "SY", "MM", "BY"]),
                reason=random.choice(
                    [
                        "Designated under Executive Order 13224 for material support to a terrorist organization.",
                        "Sanctioned for proliferation financing.",
                        "Designated for grand corruption and human rights abuses.",
                        "Subject to sectoral sanctions for activities in the energy sector.",
                    ]
                ),
            )
        )
    return out


def _make_noise_deposits(fake: Faker, account_id: str, n: int) -> list[Deposit]:
    """Add benign noise deposits to the Gamma account so monitoring labs have data."""
    out: list[Deposit] = []
    base_date = date(2026, 6, 4)
    for i in range(n):
        cp = fake.company().upper()
        out.append(
            Deposit(
                id=f"dep_noise_{i:03d}",
                account_id=account_id,
                amount_eur=round(random.uniform(2_000, 75_000), 2),
                original_amount=round(random.uniform(2_000, 75_000), 2),
                original_currency=random.choice(["EUR", "USD", "CHF"]),
                value_date=base_date + timedelta(days=i // 2),
                counterparty_name=cp,
                counterparty_country=random.choice(NOISE_COUNTRIES),
                purpose_code=random.choice(["GDDS", "SERV", "INTC", "DIVI"]),
                narrative=f"Payment ref {fake.bothify('???-#####').upper()}",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def build_dataset() -> DatasetBundle:
    random.seed(SEED)
    fake = Faker()
    Faker.seed(SEED)

    persons = _lotus_persons() + _make_noise_persons(fake, 16)
    entities = _lotus_entities() + _make_noise_entities(fake, 8)
    controls = _lotus_controls()
    account, lotus_deposits = _lotus_account_and_deposits()
    noise_deposits = _make_noise_deposits(fake, account.id, 30)
    sanctions = _lotus_sanctions() + _make_noise_sanctions(fake, 24)
    adverse_media = _lotus_adverse_media()
    documents = _lotus_documents()

    return DatasetBundle(
        persons=persons,
        entities=entities,
        controls=controls,
        accounts=[account],
        deposits=lotus_deposits + noise_deposits,
        sanctions=sanctions,
        adverse_media=adverse_media,
        documents=documents,
    )


def write_dataset(out_path: Path | None = None) -> Path:
    out_path = out_path or (config.DATA_DIR / "dataset.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = build_dataset()
    out_path.write_text(bundle.model_dump_json(indent=2))
    return out_path


def main() -> None:
    path = write_dataset()
    print(f"Wrote dataset → {path}")
    print(f"Stats: {build_dataset().stats()}")


if __name__ == "__main__":
    main()
