"""Tree search + grounded answer using PageIndex structure JSON."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.content import content_to_str
from app.core.llm import get_chat_model

_MAX_SUMMARY_CHARS = 400
_MAX_ANSWER_CONTEXT_CHARS = 60_000


def _node_map_and_roots(tree: dict | list) -> tuple[dict[str, dict], list]:
    node_map: dict[str, dict] = {}

    def collect(n: dict) -> None:
        nid = n.get("node_id")
        if nid is not None:
            node_map[str(nid)] = n
            if str(nid).isdigit():
                node_map[str(nid).zfill(4)] = n
        for c in n.get("nodes") or []:
            collect(c)

    if isinstance(tree, list):
        roots = tree
        for r in roots:
            collect(r)
    else:
        roots = [tree]
        collect(tree)
    return node_map, roots


def _strip_for_search(node: dict) -> dict:
    out: dict = {}
    for k in ("title", "node_id", "summary", "prefix_summary"):
        if k not in node:
            continue
        v = node[k]
        if isinstance(v, str) and len(v) > _MAX_SUMMARY_CHARS:
            v = v[:_MAX_SUMMARY_CHARS] + "..."
        out[k] = v
    if node.get("nodes"):
        out["nodes"] = [_strip_for_search(c) for c in node["nodes"]]
    return out


def _tree_search_prompt(query: str, tree_no_text: dict | list) -> str:
    return f"""You are a precise retrieval assistant. Given a question and a document tree, output the node_ids of every section likely to contain the answer.

Rules:
- Use exact node_id strings from the tree.
- Include parent and relevant child nodes when the question spans a section.
- Return 1–15 node_ids. Output only valid node_ids.

Question: {query}

Document tree (titles, node_ids, summaries only):
{json.dumps(tree_no_text, indent=2)}

Reply with exactly one JSON object:
{{
  "thinking": "brief reasoning",
  "node_list": ["node_id_1", "node_id_2"]
}}"""


def _answer_prompt(query: str, context: str) -> str:
    return f"""Answer using ONLY the context below.

Question: {query}

Context:
{context}

Answer clearly and cite section titles when helpful:"""


def _extract_json(text: object) -> dict:
    text = content_to_str(text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in (r"```(?:json)?\s*([\s\S]*?)```", r"(\{[\s\S]*\})"):
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue
    raise ValueError("Could not parse JSON from model output")


class DocumentRetriever:
    def __init__(self, tree_path: Path) -> None:
        self.tree_path = Path(tree_path)
        raw = json.loads(self.tree_path.read_text(encoding="utf-8"))
        self.doc_name = raw.get("doc_name") if isinstance(raw, dict) else None
        tree = raw["structure"] if isinstance(raw, dict) and "structure" in raw else raw
        self._node_map, self._roots = _node_map_and_roots(tree)
        self._tree_no_text = (
            [_strip_for_search(r) for r in self._roots]
            if isinstance(tree, list)
            else _strip_for_search(tree)
        )

    async def retrieve_context(self, query: str) -> str:
        if not query.strip():
            return ""
        model = get_chat_model()
        resp = await model.ainvoke([HumanMessage(content=_tree_search_prompt(query, self._tree_no_text))])
        text = content_to_str(getattr(resp, "content", resp))
        try:
            data = _extract_json(text)
        except ValueError:
            return ""
        node_ids = data.get("node_list") or []
        if not node_ids:
            return ""

        expanded: set[str] = set()

        def collect_children(n: dict) -> None:
            nid = n.get("node_id")
            if nid:
                expanded.add(str(nid))
            for c in n.get("nodes") or []:
                collect_children(c)

        for nid in node_ids:
            nid_str = str(nid).strip()
            node = self._node_map.get(nid_str) or (
                self._node_map.get(nid_str.zfill(4)) if nid_str.isdigit() else None
            )
            if node:
                collect_children(node)

        parts: list[str] = []
        for nid in sorted(expanded, key=lambda x: self._node_map.get(x, {}).get("start_index", 0)):
            node = self._node_map.get(nid) or self._node_map.get(nid.zfill(4) if nid.isdigit() else nid)
            if not node:
                continue
            body = content_to_str(node.get("text") or node.get("summary") or "")
            if body.strip():
                parts.append(f"## {node.get('title', 'Section')}\n\n{body}")
        context = "\n\n".join(parts)
        if len(context) > _MAX_ANSWER_CONTEXT_CHARS:
            context = context[:_MAX_ANSWER_CONTEXT_CHARS] + "\n\n[Truncated.]"
        return context

    async def ask(self, query: str) -> str:
        parts: list[str] = []
        async for chunk in self.ask_stream(query):
            parts.append(chunk)
        return "".join(parts)

    async def ask_stream(self, query: str) -> AsyncGenerator[str, None]:
        if not query.strip():
            yield "Please enter a question about your document."
            return
        context = await self.retrieve_context(query)
        if not context:
            yield "No relevant sections found. Try rephrasing your question."
            return
        model = get_chat_model()
        async for chunk in model.astream([
            SystemMessage(content="Answer only from the provided context."),
            HumanMessage(content=_answer_prompt(query, context)),
        ]):
            part = content_to_str(getattr(chunk, "content", None))
            if part:
                yield part
