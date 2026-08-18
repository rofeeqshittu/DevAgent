#!/usr/bin/env python3
"""
Web search helper for DevAgent.
Usage: python3 search_web.py "your query here"
Returns top 5 results as clean text for the agent to reason over.
"""
import sys
import json

def search(query: str, max_results: int = 5) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return results
    except ImportError:
        print("ERROR: duckduckgo-search not installed. Run: pip install duckduckgo-search", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Search failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 search_web.py \"query\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    results = search(query)

    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        print(f"[{i}] {r.get('title', 'No title')}")
        print(f"    URL: {r.get('href', 'N/A')}")
        print(f"    {r.get('body', 'No snippet')[:300]}")
        print()

if __name__ == "__main__":
    main()
