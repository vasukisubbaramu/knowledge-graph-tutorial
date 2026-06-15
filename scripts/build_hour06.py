"""Build notebooks/hour06_kg_querying.ipynb — Gen 2 query hour."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._nb import write_notebook

CELLS = [
    ("md", """\
# Hour 6 — Gen 2: Querying the graph

> *60 minutes dense, 2–3 hours to absorb. You will write a dozen Cypher queries against the Lotus graph that solve the questions Gen 1 could not, generate Cypher from natural language with Claude, produce Gen 2's full recommendation on the Lotus case, and place it side-by-side with Gen 1's. By the end you will have a precise picture of what Gen 2 buys you — and what it still cannot do.*

**Reading companion:** [`docs/hour06.md`](../docs/hour06.md).

**Prerequisite:** Hour 5 was run; Neo4j contains the Lotus graph.
"""),
    ("code", """\
from kg_tutorial import config, llm, display
from kg_tutorial.data import load
from kg_tutorial.graph import GraphDB, neo4j_subgraph_to_text

config.verify()
bundle = load.load()

db = GraphDB()
counts = db.count_by_label()
if not counts:
    print("Graph is empty — run Hour 5 first.")
else:
    print(f"Graph state: {counts}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 1. Cypher worked examples (the clean wins)

We'll go through six queries that demonstrate Gen 2's structural advantages over Gen 1. For each, the Gen 1 equivalent in Hours 2-3 either failed or was lucky.

### Query 1 — The UBO chain

Gen 1 attempted: "Who is the UBO of Gamma Operations?" with mixed success.
Gen 2: one query, exhaustive, includes percentages.
"""),
    ("code", """\
cypher = \"\"\"
MATCH path = (root:LegalEntity {id: 'e_gamma_ops'})<-[:CONTROLS*1..5]-(controller)
WHERE controller:Person OR controller:LegalEntity
RETURN
    [n IN nodes(path) | coalesce(n.full_name, n.legal_name, n.id)] AS chain,
    [r IN relationships(path) |
        coalesce(r.control_type, type(r)) + ' (' + toString(coalesce(r.ownership_pct, 0)) + '%)'
    ] AS edges
ORDER BY length(path)
\"\"\"
results = db.query(cypher)
for r in results:
    print("Path:")
    for node, edge in zip(r['chain'][:-1], r['edges']):
        print(f"  {node}")
        print(f"     ↑ {edge}")
    print(f"  {r['chain'][-1]}  <-- ROOT")
    print()
"""),
    ("md", """\
The variable-length path operator `[:CONTROLS*1..5]` does the multi-hop traversal in a single query. The answer is a *set of paths*, returned in increasing length order. In particular you should see two paths reaching John: the 3-hop ownership chain (Gamma ← AlphaBeta ← ACME ← John) and any direct edge if it exists.

This is the Gen 1-impossible case, made trivial by Gen 2.
"""),
    ("md", """\
### Query 2 — All entities John controls (the cross-link)

Hour 3's Diagnostic 2: "list every entity John controls directly or indirectly."
"""),
    ("code", """\
cypher = \"\"\"
MATCH (john:Person {id: 'p_john_q_public'})-[r:CONTROLS*1..4]->(e:LegalEntity)
RETURN DISTINCT e.legal_name AS entity, e.jurisdiction AS juris
\"\"\"
results = db.query(cypher)
for r in results:
    print(f"  {r['entity']} ({r['juris']})")
"""),
    ("md", """\
**Look at the result.** You should see:

- ACME Holdings Ltd (KY)
- AlphaBeta Trading SA (PA)
- Gamma Operations GmbH (LI)
- **Atlas Wirecorp (AE)** — the cross-link Gen 1 missed.

The Gen 1 retriever couldn't surface Atlas because the relevant chunk was about deposits, not control. Gen 2 doesn't need a chunk — it walks an edge. The cross-link is **structurally** present in the graph because the directorship is an edge.
"""),
    ("md", """\
### Query 3 — PEPs and PEP-relatives among controllers

Combine label filtering with traversal:
"""),
    ("code", """\
cypher = \"\"\"
MATCH (p:Person)-[r:CONTROLS]->(e:LegalEntity)
WHERE p.is_pep = true
RETURN p.full_name AS person, p.pep_reason AS reason, count(DISTINCT e) AS entities_controlled
ORDER BY entities_controlled DESC
\"\"\"
for r in db.query(cypher):
    print(f"  {r['person']:>35} controls {r['entities_controlled']} entities")
    print(f"    └─ {r['reason']}")
"""),
    ("md", """\
A single query that would be a join across three tables in SQL.
"""),
    ("md", """\
### Query 4 — Inbound deposits to the applicant + the originator

The Lotus deposit. Get its counterparty and immediately ask: was the counterparty named ATLAS WIRECORP also an entity in our graph (i.e., do we have any internal information about it)?
"""),
    ("code", """\
cypher = \"\"\"
MATCH (d:Deposit)-[:DEPOSITS_TO]->(a:Account {id: 'a_gamma_001'})
OPTIONAL MATCH (e:LegalEntity) WHERE toUpper(e.legal_name) = toUpper(d.counterparty_name)
RETURN d.amount_eur AS amount, d.counterparty_name AS counterparty, d.value_date AS date,
       e.id AS internal_entity_id, e.legal_name AS internal_match
ORDER BY d.amount_eur DESC
LIMIT 5
\"\"\"
for r in db.query(cypher):
    match = r['internal_match'] or "(no internal match — name not found)"
    print(f"  EUR {r['amount']:>12,.0f}  from {r['counterparty']:>25} → internal match: {match}")
"""),
    ("md", """\
**The exact-match join failed.** The deposit says `ATLAS WIRECORP`, our entity is `Atlas Wirecorp`. Case + spelling. Cypher's `=` is too crisp. Fix with a `CONTAINS` or `toLower()` normalization — and now you see why production graph queries are often *hand-tuned* with normalization.
"""),
    ("code", """\
cypher = \"\"\"
MATCH (d:Deposit)-[:DEPOSITS_TO]->(a:Account {id: 'a_gamma_001'})
OPTIONAL MATCH (e:LegalEntity)
WHERE toLower(e.legal_name) CONTAINS toLower(d.counterparty_name)
   OR toLower(d.counterparty_name) CONTAINS toLower(e.legal_name)
RETURN d.counterparty_name AS counterparty, e.id AS internal_id, e.legal_name AS internal_name
LIMIT 5
\"\"\"
for r in db.query(cypher):
    print(f"  {r['counterparty']:>25} → {r['internal_name'] or '(no match)'}")
"""),
    ("md", """\
Now we link the deposit to Atlas Wirecorp internally. **But the OFAC list says `ATLAS WIRE CORPORATION`** — that's an even bigger gap. `CONTAINS` would help on the substring "ATLAS WIRE" but it does not give you a calibrated similarity score, and "WIRE" matches a lot of false positives. **This is the Gen 2 strain. Hour 7 fixes it by calling a real fuzzy matcher as a tool.**
"""),
    ("md", """\
### Query 5 — Sanctions, the alias problem in Cypher

Try the literal match:
"""),
    ("code", """\
deposit = db.query("MATCH (d:Deposit {id: 'dep_001'}) RETURN d.counterparty_name AS name")[0]
target = deposit['name']
print(f"Deposit counterparty: '{target}'")

# Strict equality — fails
strict = db.query("MATCH (s:SanctionsRecord) WHERE s.name = $t RETURN s.name", {"t": target})
print(f"Strict equality matches: {len(strict)}")

# CONTAINS — partial, can over- or under-match
contains_hits = db.query(
    "MATCH (s:SanctionsRecord) WHERE toLower(s.name) CONTAINS toLower($t) OR toLower($t) CONTAINS toLower(s.name) "
    "RETURN s.name AS name LIMIT 10",
    {"t": target},
)
print(f"CONTAINS matches ({len(contains_hits)}):")
for r in contains_hits:
    print(f"  - {r['name']}")
"""),
    ("md", """\
The CONTAINS query may or may not find `ATLAS WIRE CORPORATION` depending on how exactly the strings overlap. Even when it does, the result is a boolean, not a score. **A control manager cannot escalate on a boolean.** They need a calibrated fuzzy score with a documented threshold, which is what Hour 7 builds.
"""),
    ("md", """\
### Query 6 — Subgraph retrieval for an LLM

The killer pattern for Gen 2 + LLM: extract a relevant subgraph, serialize it as text, give it to the LLM as context. The LLM then *reasons* over a clean, structured input.
"""),
    ("code", """\
# Get a 2-hop subgraph around the applicant
rows = db.subgraph_around("e_gamma_ops", depth=2)
context_text = neo4j_subgraph_to_text(rows)
print(context_text[:2000])
print("..." if len(context_text) > 2000 else "")
"""),
    ("md", """\
That text is now a clean, complete, citable representation of the Lotus structure. **Compare to Gen 1's context** — paragraphs of policy mixed with CDD form prose. The Gen 2 context is dense, structured, and contains nothing irrelevant.
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 2. Text-to-Cypher with Claude

The Cypher queries above are powerful but you had to write them. Asking a control manager to write Cypher is a non-starter. The Gen 2 retrieval pattern that scales is **natural-language → Cypher**: the user asks in English, the system generates Cypher, executes, returns results.

The key is giving the LLM the ontology in the system prompt — without it, the LLM hallucinates labels and edge types.
"""),
    ("code", """\
SCHEMA_PROMPT = \"\"\"You write Cypher queries against a Neo4j knowledge graph for a bank's control-management platform.

SCHEMA
Nodes:
  Person          {id, full_name, is_pep, pep_reason, residence_country, nationalities}
  LegalEntity     {id, legal_name, jurisdiction, entity_type, notes}
  Account         {id, account_number, status, currency}
  Deposit         {id, amount_eur, value_date, counterparty_name, counterparty_country, narrative}
  SanctionsRecord {id, name, aliases, list_source, country, reason}
  AdverseMediaItem{id, headline, snippet, source_outlet, sentiment, topics}

Edges:
  (Person|LegalEntity)-[:CONTROLS {control_type, ownership_pct, source}]->(LegalEntity)
  (LegalEntity)-[:HOLDS]->(Account)
  (Deposit)-[:DEPOSITS_TO]->(Account)
  (AdverseMediaItem)-[:MENTIONS]->(Person|LegalEntity)

RULES
- Return Cypher only. No prose, no explanation.
- Use case-insensitive string matching (toLower(...)) where appropriate.
- For multi-hop, use variable-length paths [:CONTROLS*1..N] with N <= 5.
- For aggregation, return clean column names with AS.
\"\"\"


def ask_for_cypher(question: str) -> str:
    answer = llm.ask(
        f"Question: {question}\\n\\nWrite the Cypher.",
        system=SCHEMA_PROMPT,
        max_tokens=500,
    )
    # Strip code fences if present
    import re
    return re.sub(r"^```(?:cypher)?\\n?|\\n?```$", "", answer.strip(), flags=re.MULTILINE)


# Try it
q = "List every person who is a PEP and is the UBO of at least one entity in Liechtenstein."
generated = ask_for_cypher(q)
print("Question:", q)
print()
print("Generated Cypher:")
print(generated)
print()
print("Results:")
try:
    for r in db.query(generated):
        print(f"  {r}")
except Exception as e:
    print(f"  Cypher failed: {e}")
"""),
    ("md", """\
**Stop and look at the generated Cypher.** Even simple queries reveal a lot:

- Did the model use the right label (`Person`, `LegalEntity`)?
- Did it filter `is_pep = true` correctly?
- Did it traverse `CONTROLS` with the right control_type filter?
- Did it scope to Liechtenstein with `jurisdiction = 'LI'`?

When text-to-Cypher works it feels like magic. When it fails, it fails in *interesting* ways — wrong labels, made-up properties, missing filters. Production text-to-Cypher systems use:

- A validated schema description (we have one above).
- Few-shot examples of successful queries.
- A post-hoc Cypher validator that catches syntax errors before execution.
- A fallback to "I cannot answer this with the available schema" rather than executing a malformed query.

Let's try a harder one — the Lotus question itself.
"""),
    ("code", """\
hard_q = "Show me everything that connects John Q. Public to the deposit a_gamma_001 in fewer than five hops."
generated = ask_for_cypher(hard_q)
print("Generated:")
print(generated)
print()
print("Results:")
try:
    for r in db.query(generated):
        print(f"  {r}")
except Exception as e:
    print(f"  Cypher failed: {e}")
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 3. Gen 2's Lotus answer

The whole point. Build a Gen 2 recommendation on the Lotus case. The pattern:

1. Retrieve a relevant subgraph from Neo4j (the structure).
2. Retrieve relevant unstructured chunks (the prose).
3. Compose both into a prompt.
4. Ask Claude for a recommendation.
"""),
    ("code", """\
# Get the 3-hop subgraph around the applicant + the deposit + sanctions
rows_g = db.subgraph_around("e_gamma_ops", depth=3)
rows_d = db.subgraph_around("dep_001", depth=2)
all_rows = rows_g + rows_d
graph_context = neo4j_subgraph_to_text(all_rows)
"""),
    ("code", """\
# Get a small set of unstructured chunks too — this is Gen 2 layered on Gen 1
from kg_tutorial.retrieval import chunk_documents, VectorIndex, BM25Index, rrf_combine
para_chunks = chunk_documents(bundle.documents, strategy="paragraph", max_chars=800)
vec = VectorIndex(name="lotus_paragraph")
if vec.count() == 0:
    vec.add(para_chunks)
bm25 = BM25Index(para_chunks)

q_lotus = "What policy obligations apply to this customer?"
vec_hits = vec.search(q_lotus, k=5)
bm25_hits = bm25.search(q_lotus, k=5)
top_chunks = rrf_combine([vec_hits, bm25_hits], top_k=3)
doc_context = "\\n\\n".join(f"From: {h.chunk.doc_title}\\n{h.chunk.text}" for h in top_chunks)
"""),
    ("code", """\
prompt = f\"\"\"You are a senior bank control manager.

KNOWLEDGE-GRAPH CONTEXT (the structural relationships):
{graph_context}

POLICY / UNSTRUCTURED CONTEXT:
{doc_context}

QUESTION: Should we approve the account-opening application for Gamma Operations GmbH?

Write a one-paragraph recommendation that EXPLICITLY:
(a) traces the ownership chain to the natural-person UBO,
(b) notes any cross-links between the customer and the deposit's originator,
(c) classifies the UBO under any policy categories (PEP, PEP-relative, sanctions concerns),
(d) flags the source-of-funds and source-of-wealth issues,
(e) cites the relevant policy or document for each claim.

End with APPROVE, DECLINE, or ESCALATE.
\"\"\"

gen2_answer = llm.ask(prompt, max_tokens=700, model=config.MODEL_DEFAULT)
display.md(gen2_answer)
"""),
    ("md", """\
**Grade Gen 2's answer against the same checklist from Hour 2.**

1. Full ownership chain (KY → PA → LI)? Gen 2 should ace this — it's in the graph context.
2. PEP-relative classification? Gen 2 reads the policy chunk + sees `is_pep = true` on John — should be solid.
3. **The cross-link** (John directs Atlas Wirecorp)? **This is the test.** Gen 2 should catch it from the graph context.
4. Alias-mismatched sanctions? Gen 2 will *probably* flag the deposit's counterparty by name. Whether it recognizes the OFAC alias depends on whether the LLM compares the deposit's `counterparty_name` to nearby sanctions records in the subgraph. Gen 2 won't give you a calibrated *score* — that's still Hour 7.
5. Source-of-funds gap? Should be cited from the SoF questionnaire chunk.
6. RM pressure / SoW gap? Depends on whether the right policy chunks made it into the top-3.
7. Defensible citations? The graph context lists exact node IDs and edges; citing them is precise.

**Compare to your saved Gen 1 answer from Hour 2.** What did Gen 2 catch that Gen 1 missed? What is *still* missed by Gen 2?
"""),
    # ------------------------------------------------------------------
    ("md", """\
## 4. What Gen 2 still cannot do

By the end of Hour 6 you should have a clear picture of the three remaining limits:

1. **Fuzzy sanctions match.** Cypher `=` is too crisp; `CONTAINS` is too loose. A calibrated fuzzy score with a documented threshold is a *tool*, not a query.
2. **Temporal reasoning.** "When did John become the UBO?" requires date arithmetic that the schema may or may not support. Real KGs are temporal; production needs bi-temporal modelling (valid time + transaction time) which we have not implemented.
3. **Open-ended reasoning.** "Is the bank exposed to reputational risk if it onboards this customer?" is not a Cypher query. The KG retrieves; the LLM reasons; but the LLM cannot easily *verify* its own reasoning against the graph without an agentic loop.

Each of these motivates a specific architecture move in Hours 7-11:

- Hour 7 — **Hybrid retrieval**: combine the graph's precision with vector's fuzziness, and route to a fuzzy-match tool when needed.
- Hour 8 — **Agentic reasoning**: ReAct, Self-RAG, Reflexion. The agent decides when to call which retriever.
- Hour 11 — **End-to-end agent**: the full Lotus answer with citations, self-critique, and HITL hand-off.
"""),
    # ------------------------------------------------------------------
    ("code", """\
db.close()
"""),
    ("md", """\
---

## Stop and think before Hour 7

Three questions:

1. **In the Gen 2 answer above, what *specific* claim has the strongest citation chain?** That claim's citation pattern (graph context with explicit IDs) is what Gen 3 will reproduce automatically.
2. **What *specific* claim has the weakest citation chain?** That's where you'd want Gen 3's self-critique to push back.
3. **Which of the three remaining limits (fuzzy match, temporal, open-ended reasoning) is the most consequential for your platform?** That ranking tells you which Gen 3 capability to prioritise.

Next: [Hour 7 — Gen 2 limits and hybrid retrieval](./hour07_hybrid_retrieval.ipynb). The transition hour. You'll build a hybrid retriever, run a fuzzy match as a *tool*, and watch the architectural seam between Gen 2 and Gen 3 form in front of you.
"""),
]


if __name__ == "__main__":
    out = write_notebook(
        Path(__file__).resolve().parent.parent / "notebooks" / "hour06_kg_querying.ipynb",
        CELLS,
    )
    print(f"Wrote {out}")
