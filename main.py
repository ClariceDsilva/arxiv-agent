#!/usr/bin/env python3
"""
Orchestrate the full arXiv digest + QA agent.

Usage:
    python main.py "recent work on quantization for large language models"
    python main.py "https://arxiv.org/abs/2401.12345"
    python main.py 2401.12345

Then interactively ask follow-up questions about the paper.

See README.md for architecture and design notes.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from src import edges
from src.briefing import briefing_to_markdown
from src.embeddings import get_embedder
from src.graph import StateGraph
from src.llm import get_llm_client
from src.nodes import (
    chunk_embed,
    fetch_parse,
    query_understanding,
    selection_ranking,
    summarize,
    qa,
    arxiv_retrieval,
)
from src.state import AgentState, Intent, RunStatus
from src.vectorstore.chroma_store import ChromaChunkStore

logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s",
)
logger = logging.getLogger("arxiv_agent.main")

CHROMA_DIR = Path.home() / ".cache" / "arxiv-agent" / "chroma"


def build_graph(llm_client, embedder, vector_store):
    """Construct the state graph with all nodes and edges."""
    graph = StateGraph()

    # Nodes
    graph.add_node("query_understanding", query_understanding.query_understanding_node)
    graph.add_node("arxiv_retrieval", arxiv_retrieval.arxiv_retrieval_node)
    graph.add_node(
        "selection_ranking",
        selection_ranking.make_selection_ranking_node(embedder),
    )
    graph.add_node("fetch_parse", fetch_parse.fetch_parse_node)
    graph.add_node("chunk_embed", chunk_embed.make_chunk_embed_node(vector_store))
    graph.add_node("summarize", summarize.make_summarize_node(llm_client))

    # Edges
    graph.set_entry("query_understanding")
    graph.add_edge("query_understanding", edges.route_after_understanding)
    graph.add_edge("arxiv_retrieval", edges.route_after_retrieval)
    graph.add_edge("selection_ranking", edges.route_after_ranking)
    graph.add_edge("fetch_parse", edges.route_after_fetch_parse)
    graph.add_edge("chunk_embed", edges.route_after_chunk_embed)
    graph.add_edge("summarize", edges.route_after_summarize)

    return graph


def run_digest_pipeline(query: str, llm_client, embedder, vector_store) -> AgentState:
    """Run the full pipeline: query -> briefing."""
    graph = build_graph(llm_client, embedder, vector_store)
    state = AgentState(raw_query=query)
    state = graph.run(state)
    return state


def interactive_qa_loop(state: AgentState, llm_client, vector_store):
    """Repeatedly prompt user for questions about the paper."""
    if not state.selected_paper or not state.chunks:
        print("\n(No chunks indexed; QA unavailable.)")
        return

    answer_fn = qa.make_qa_node(llm_client, vector_store)
    print("\n" + "=" * 70)
    print("Now in QA mode. Ask questions about the paper, or type 'exit'/'quit'.")
    print("=" * 70)

    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            break

        state = answer_fn(state, question)
        last_turn = state.qa_history[-1]
        print(f"\n{last_turn.answer}")
        if last_turn.retrieved_chunk_ids:
            print(f"\n  (Grounded in {len(last_turn.retrieved_chunk_ids)} retrieved chunk(s), "
                  f"max similarity: {last_turn.max_similarity:.2f})")


def save_state_summary(state: AgentState, output_dir: Path):
    """Save briefing + QA history in both Markdown and JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save full state as JSON for rehydration
    state_file = output_dir / "state.json"
    state.save(state_file)
    print(f"\nFull state saved to: {state_file}")

    # Save briefing as Markdown
    if state.briefing:
        briefing_file = output_dir / "briefing.md"
        with open(briefing_file, "w", encoding="utf-8") as f:
            f.write(briefing_to_markdown(state.briefing))
        print(f"Briefing saved to: {briefing_file}")

    # Save QA history
    if state.qa_history:
        qa_file = output_dir / "qa_history.json"
        with open(qa_file, "w", encoding="utf-8") as f:
            json.dump([q.__dict__ for q in state.qa_history], f, indent=2)
        print(f"QA history saved to: {qa_file}")

    # Save trace/warnings for debugging
    if state.warnings or state.errors:
        debug_file = output_dir / "debug.txt"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("Execution Trace:\n")
            f.write("\n".join(f"  {line}" for line in state.trace))
            f.write("\n\nWarnings:\n")
            f.write("\n".join(f"  - {w}" for w in state.warnings))
            f.write("\n\nErrors:\n")
            f.write("\n".join(f"  - {e}" for e in state.errors))
        print(f"Debug info saved to: {debug_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Digest an arXiv paper and ask follow-up questions about it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "recent work on quantization for LLMs"
  python main.py "https://arxiv.org/abs/2401.12345"
  python main.py 2401.12345
  python main.py "kv-cache compression" --llm-provider ollama --output-dir ./results
        """,
    )
    parser.add_argument("query", help="Topic, arXiv ID, or URL")
    parser.add_argument(
        "--llm-provider",
        default=None,
        help="LLM provider: 'gemini', 'ollama', or 'echo'. Defaults to GEMINI_API_KEY > OLLAMA_HOST.",
    )
    parser.add_argument(
        "--embedding-provider",
        default="local",
        help="Embedding provider: 'local' (default) or 'fake' (for tests).",
    )
    parser.add_argument(
        "--output-dir",
        default="./arxiv_output",
        help="Directory to save briefing, QA history, debug logs.",
    )
    parser.add_argument(
        "--no-qa",
        action="store_true",
        help="Skip interactive QA mode after generating briefing.",
    )
    parser.add_argument(
        "--load-state",
        help="Load a previously saved state.json to resume QA without re-running the pipeline.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose logging.",
    )

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    print("arXiv Autonomous Digest & QA Agent")
    print("=" * 70)

    # Handle state rehydration for QA-only mode
    if args.load_state:
        logger.info("Loading state from %s", args.load_state)
        state = AgentState.load(args.load_state)
        llm_client = get_llm_client(args.llm_provider)
        vector_store = ChromaChunkStore(str(CHROMA_DIR), get_embedder(args.embedding_provider))
        if not args.no_qa:
            interactive_qa_loop(state, llm_client, vector_store)
        return

    # Normal flow: run the full pipeline
    try:
        llm_client = get_llm_client(args.llm_provider)
        embedder = get_embedder(args.embedding_provider)
        vector_store = ChromaChunkStore(str(CHROMA_DIR), embedder)
    except RuntimeError as exc:
        print(f"\nERROR: {exc}\n", file=sys.stderr)
        sys.exit(1)

    logger.info("Query: %s", args.query)
    logger.info("Using LLM provider: %s", args.llm_provider or "(auto)")
    logger.info("Using embedding provider: %s", args.embedding_provider)

    state = run_digest_pipeline(args.query, llm_client, embedder, vector_store)

    print("\n" + "=" * 70)
    print("BRIEFING")
    print("=" * 70 + "\n")

    if state.status == RunStatus.FAILED:
        print(f"PIPELINE FAILED: {state.errors[0] if state.errors else 'unknown error'}\n")
        sys.exit(1)

    if state.briefing:
        print(briefing_to_markdown(state.briefing))
    else:
        print("(No briefing generated.)\n")

    if state.warnings:
        print("\n" + "=" * 70)
        print("WARNINGS")
        print("=" * 70)
        for w in state.warnings:
            print(f"  ⚠ {w}")

    # Save output
    output_dir = Path(args.output_dir)
    save_state_summary(state, output_dir)

    # Interactive QA
    if not args.no_qa:
        interactive_qa_loop(state, llm_client, vector_store)

    print("\nDone.\n")


if __name__ == "__main__":
    main()
