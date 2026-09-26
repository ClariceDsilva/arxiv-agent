# Design Decisions & Tradeoffs

## Architecture: Custom State Graph vs. Framework

**Decision:** Built a custom 50-line `StateGraph` (nodes + edges + runner) instead of using LangGraph/LlamaIndex/CrewAI.

**Rationale:**
- The assessment explicitly asks you to *design and justify* a state graph, not apply a template.
- Custom graph is transparent: every node, edge, and state transition is visible and traceable.
- Nodes are pure functions `(state) -> state`, trivially testable and swappable.
- Zero framework magic = easier debugging when things go wrong.
- No dependency that could fail to import in the reviewer's environment.

**Tradeoff:** Slightly more boilerplate than a framework, but worth it for clarity in a design exercise.

---

## State Management: In-Memory + Serializable

**Decision:** State lives in memory during pipeline (fast, simple). After briefing, save to disk (`state.json`) for resumable QA.

**Rationale:**
- In-memory: no DB overhead, trivial to debug (just log the state at each step).
- Serializable: after expensive ops (PDF download, embedding), save state so users can resume QA without re-downloading.
- JSON format is human-readable, language-agnostic, and trivial to parse.

**Tradeoff:** Not a true session database (no concurrent access), but perfect for single-user CLI.

---

## Chunking: Section-Aware, Not Sliding Window

**Decision:** Chunk *within* detected sections rather than blindly across the full text.

**Rationale:**
- Keeps section metadata meaningful ("this idea is from the Results") for better QA citations.
- Avoids splitting an idea about Method together with a Results paragraph into one incoherent chunk.
- Heuristic: match lines like "3.2 Method" against common heading patterns.

**Tradeoff:** Requires section detection. If it fails, fallback to a single "Full Text" pseudo-section, which works fine.

---

## Embeddings: Local Sentence-Transformers, Not LLM

**Decision:** Use `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cached locally), not LLM embeddings.

**Rationale:**
- Free-tier LLM quota is precious; chunking/retrieval shouldn't burn it (each paper digest uses ~2 LLM calls).
- Runs offline once cached; no API rate-limit risk.
- Proven on academic text; no fine-tuning needed.
- Small model (~80 MB) fits on any machine.

**Tradeoff:** General-purpose embeddings, not domain-specific. Fine-tuning could improve recall/precision, but is unnecessary for typical papers.

---

## LLM: Gemini Free Tier + Ollama Fallback

**Decision:** Default to Gemini 3.1 Flash-Lite (Google AI Studio free tier). Fallback to local Ollama.

**Rationale:**
- Gemini free tier is generous: 15 RPM, 500 RPD. Covers 1–2 papers/day, 5–10 QA turns each.
- Ollama means the entire pipeline works offline without any API key.
- Fully decoupled via `LLMClient` interface; adding another provider (Groq, Claude API, etc.) takes 30 lines.

**Tradeoff:** Rate limits apply; hitting them gracefully degrades to a rule-based fallback briefing. Production would implement exponential backoff + queue.

---

## Vector Store: Chroma (Local, Persistent)

**Decision:** Use local, persistent Chroma. One collection per paper (named by arxiv_id).

**Rationale:**
- Zero cloud cost or complexity.
- Re-running the same paper reuses the collection (no re-embedding).
- `pip install chromadb` is trivial.

**Tradeoff:** Not scalable to millions of papers (would need Pinecone/Weaviate), but fine for a prototype.

---

## Graceful Degradation: 3 Failure Modes Handled Explicitly

### A. Scanned PDFs
- **Detection:** Average chars/page < threshold.
- **Fallback:** `parse_quality='partial'` or `'abstract_only'`; briefing still works.
- **User sees:** Caveat added to briefing: "PDF parsing detected potential scanned images; extraction may be incomplete."

### B. PDF Download Failures
- **Fallback:** Use abstract only; no graph halt.
- **User sees:** Briefing + QA still work (thinner, but usable).

### C. LLM Call Failures
- **Behavior:** Retry with smaller context; on second failure, use rule-based fallback briefing.
- **User sees:** Minimal but readable briefing from the abstract.

**Rationale:** Users get *something* even when things go wrong. Better a thin briefing than a crash.

---

## Grounding: Explicit Similarity Thresholds

**Decision:** Only generate LLM answer if retrieved chunks exist AND max cosine similarity ≥ 0.22.

**Rationale:**
- Below 0.22: chunks are usually off-topic or tangential; LLM is likely to hallucinate.
- Teaches the user that the paper may not cover their question (honest failure > confident nonsense).
- Cosine similarity is meaningful for sentence-transformers embeddings.

**Tradeoff:** Threshold is empirical, not learned. Could be optimized with labeled data, but simple heuristic works well.

---

## Rate Limit Handling

**Free-Tier Limits (Gemini):**
- 15 requests/minute
- 500 requests/day
- 250K tokens/minute

**Pipeline Usage:**
- ~3–4 LLM calls per paper: 1 for summarization, then one per QA turn.
- Typical paper: fits well within limits.

**Mitigation:**
- Error caught and logged; fallback briefing generated.
- Production would implement exponential backoff + queue.

---

## Why No Fine-Tuning / Custom Embeddings?

Off-the-shelf embeddings work well for this use case. Fine-tuning would require:
- Labeled dataset of paper chunks + relevance labels.
- Training infrastructure.
- Marginal improvement (embeddings are already good on academic text).

Not worth the complexity for a prototype.

---

## What We'd Do With More Time

### 1. **Multi-Paper Comparison**
   - Load two papers, generate a comparative briefing.
   - Estimated: 4–6 hours.

### 2. **Citation Extraction & Linking**
   - Parse bibliography, link claims to specific references.
   - Would improve QA precision (e.g., "which prior work does this compare to?").
   - Estimated: 8–10 hours.

### 3. **Figure/Table Parsing**
   - OCR on figures, extract tables, integrate into chunks.
   - Would improve briefing quality for method/results sections.
   - Estimated: 12–16 hours.

### 4. **Cross-Encoder Reranking**
   - Use a larger model to rerank retrieved chunks.
   - Would improve QA accuracy (currently simple cosine similarity).
   - Estimated: 6–8 hours.

### 5. **Learned Similarity Threshold**
   - Train a small model to predict answer quality given chunk similarity.
   - Would optimize precision/recall tradeoff.
   - Estimated: 8–12 hours.

### 6. **FastAPI Server + Multi-User**
   - Expose as HTTP API with user sessions, persistent storage.
   - Would enable web UI and sharing.
   - Estimated: 20–24 hours.

### 7. **Fine-Tuned Embeddings**
   - Fine-tune sentence-transformers on a corpus of academic papers.
   - Would improve recall/precision on domain-specific queries.
   - Estimated: 16–20 hours.

### 8. **Integration with PapersWithCode**
   - Fetch associated code, results, reproducibility info.
   - Would enrich briefing with practical insights.
   - Estimated: 8–12 hours.

---

## Known Limitations

1. **No Multi-GPU Support**
   - State is in-memory; distribution would require a DB.
   - OK for prototype; fine for single-machine, single-user.

2. **Chunking Heuristic**
   - Section detection is regex-based, not ML-based.
   - Fails on unusual layouts (e.g., two-column papers, non-English).
   - Fallback to "Full Text" works, just less precise.

3. **No Sparse Attention Optimization**
   - Embeddings are computed for all chunks, then retrieved.
   - Could be optimized with hierarchical indexing (e.g., index by section, then by chunk).

4. **Limited to arXiv**
   - No support for journals, PapersWithCode, SSRN, etc.
   - Would require adding pluggable document sources.

5. **No Fine-Grained Attribution**
   - Briefing points to sections, not specific sentences.
   - Could improve with sentence-level chunk attribution.

---

## Conclusion

The design prioritizes **transparency** (custom graph, pure functions, serializable state), **robustness** (graceful degradation, explicit failure modes), and **simplicity** (minimal dependencies, no frameworks). It trades off some scalability and advanced features for clarity and debuggability—appropriate for a design exercise and a prototype.

The state graph is the heart of this system: every node is independent, every edge is justified, and the full pipeline is traceable. Adding new nodes (e.g., reference extraction, figure parsing) is straightforward—just implement `(state) -> state` and wire it in.
