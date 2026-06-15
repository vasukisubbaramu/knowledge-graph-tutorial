"""Entity + relation extraction from KYC documents.

Two strategies, implemented side-by-side so the lab can compare them:

  1) spacy_extract()  — classical NER baseline (PERSON / ORG / GPE / MONEY / DATE).
     Fast, deterministic, blind to bank-specific concepts like UBO or PEP-relative.

  2) claude_extract() — schema-guided LLM extraction.
     Slower, costlier, but understands "nephew of MP" as a PEP-relative
     without anyone training it.

Used in Hour 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kg_tutorial import llm


@dataclass
class ExtractedEntity:
    surface: str       # the substring as it appeared
    entity_type: str   # the type tag — vocabulary depends on extractor
    start: int = -1
    end: int = -1
    score: float = 1.0


@dataclass
class ExtractedRelation:
    head_surface: str
    relation: str
    tail_surface: str
    properties: dict = field(default_factory=dict)


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]
    notes: str = ""


# ---------------------------------------------------------------------------
# spaCy NER baseline
# ---------------------------------------------------------------------------

_SPACY_NLP = None


def _spacy_model():
    """Lazily load the small English model.

    Requires: python -m spacy download en_core_web_sm
    """
    global _SPACY_NLP
    if _SPACY_NLP is None:
        import spacy
        try:
            _SPACY_NLP = spacy.load("en_core_web_sm")
        except OSError as e:
            raise RuntimeError(
                "spaCy English model not found. Run: "
                "python -m spacy download en_core_web_sm"
            ) from e
    return _SPACY_NLP


def spacy_extract(text: str) -> ExtractionResult:
    """Run spaCy NER over the text.

    Returns named-entity spans only. No relation extraction — spaCy doesn't
    do relations natively, and the lab's point is to *show* this limit.
    """
    doc = _spacy_model()(text)
    ents = [
        ExtractedEntity(surface=e.text, entity_type=e.label_, start=e.start_char, end=e.end_char)
        for e in doc.ents
    ]
    return ExtractionResult(
        entities=ents,
        relations=[],
        notes="spaCy NER baseline: entities only, no relations.",
    )


# ---------------------------------------------------------------------------
# Claude schema-guided extraction
# ---------------------------------------------------------------------------

KYC_EXTRACTION_PROMPT = """You are an information extraction system for a bank's control-management platform.

The bank uses a knowledge graph with the following entity types and relations:

ENTITY TYPES
- Person          (a natural person)
- LegalEntity     (a company, trust, foundation, SPV — any non-natural legal person)
- Account         (a bank account)
- SanctionsRecord (an entry on a sanctions list)
- PEPDesignation  (an attribute attached to a Person classifying them as PEP, PEP-relative, etc.)

RELATIONS
- UBO              Person --UBO(percent)-->         LegalEntity     (ownership ≥ 25%)
- SHAREHOLDER      Person --SHAREHOLDER(percent)--> LegalEntity     (ownership < 25%)
- DIRECTOR         Person --DIRECTOR-->             LegalEntity
- POA              Person --POA-->                  LegalEntity     (power of attorney)
- PARENT           LegalEntity --PARENT(percent)--> LegalEntity     (parent owns subsidiary)
- HOLDS            LegalEntity --HOLDS-->           Account
- AUTHORIZED_ON    Person --AUTHORIZED_ON-->        Account         (signatory)
- RELATED_TO       Person --RELATED_TO(kind)-->     Person          (family / close associate)

Read the document below and return a JSON object with two keys:
  - "entities":  list of {{"surface": ..., "type": ...}}
  - "relations": list of {{"head": ..., "relation": ..., "tail": ..., "properties": {{...}}}}

Use surface forms exactly as they appear in the text. If a relation is mentioned only indirectly (e.g. "X is the UBO" without specifying the entity), use your best inference but flag low confidence in a "notes" key on the relation.

DOCUMENT:
{document}
"""


def claude_extract(document_text: str, *, model: str | None = None) -> ExtractionResult:
    """Schema-guided extraction with Claude.

    The schema is baked into the prompt — the model knows what entity types
    and relation types are valid. Output is parsed as JSON; malformed JSON
    raises (we want failures visible, not silent).
    """
    raw = llm.ask_json(
        KYC_EXTRACTION_PROMPT.format(document=document_text),
        model=model,
        max_tokens=2000,
    )

    entities = [
        ExtractedEntity(surface=e["surface"], entity_type=e.get("type", "Unknown"))
        for e in raw.get("entities", [])
    ]
    relations = [
        ExtractedRelation(
            head_surface=r["head"],
            relation=r["relation"],
            tail_surface=r["tail"],
            properties=r.get("properties", {}),
        )
        for r in raw.get("relations", [])
    ]
    return ExtractionResult(
        entities=entities,
        relations=relations,
        notes="Claude schema-guided extraction.",
    )


# ---------------------------------------------------------------------------
# Reconciliation (extracted surface → canonical id)
# ---------------------------------------------------------------------------

def reconcile_to_canonical(
    extracted_surface: str,
    candidates: list[tuple[str, list[str]]],
) -> str | None:
    """Resolve an extracted surface to a canonical id by simple fuzzy match.

    `candidates` is a list of (id, [surface_forms]) tuples. We score each
    surface form by character similarity and pick the best, with a
    threshold. Cheap and pedagogical — production would use a vector or
    learned entity resolver.
    """
    from difflib import SequenceMatcher

    s = extracted_surface.upper().strip()
    best_id: str | None = None
    best_score = 0.0
    for cid, forms in candidates:
        for f in forms:
            score = SequenceMatcher(None, s, f.upper().strip()).ratio()
            if score > best_score:
                best_score = score
                best_id = cid
    return best_id if best_score >= 0.70 else None
