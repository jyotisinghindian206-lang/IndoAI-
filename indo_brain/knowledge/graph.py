"""Small deterministic concept graph extractor; not a semantic knowledge model."""
from __future__ import annotations
import re
from collections import Counter
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOP = {"the","and","for","with","that","this","from","have","will","your","about","into","when","what","where","which","their","there","then","than","also","using","does","make","more","less"}

def extract_concept_graph(text: str, max_nodes: int = 40) -> dict:
    words = [w.casefold() for w in _WORD.findall(str(text or "")) if w.casefold() not in _STOP]
    counts = Counter(words)
    nodes = [{"id": w, "label": w, "weight": n} for w, n in counts.most_common(max(1, min(int(max_nodes), 100)))]
    edges = []
    for left, right in zip(words, words[1:]):
        if left != right and left in counts and right in counts:
            pair = (left, right)
            if not any(e["source"] == left and e["target"] == right for e in edges):
                edges.append({"source": left, "target": right, "relation": "co_occurs_nearby"})
            if len(edges) >= 100: break
    return {"nodes": nodes, "edges": edges, "ephemeral": True,
            "note": "Frequency and adjacency extraction only; relationships are not verified facts."}
