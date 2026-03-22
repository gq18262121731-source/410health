from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from backend.config import Settings


@dataclass
class RetrievalCandidate:
    source: str
    text: str
    score: float


class LangChainRAGService:
    """Offline-first RAG service using deterministic local keyword retrieval."""

    def __init__(self, settings: Settings, knowledge_dir: Path) -> None:
        self._settings = settings
        self._knowledge_dir = knowledge_dir
        self._token_pattern = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")
        self._documents = self._load_documents()
        self._chunks = self._build_chunks(self._documents)
        self._docs_hash = self._build_docs_hash(self._chunks)

    def search(
        self,
        query: str,
        top_k: int = 3,
        *,
        network_online: bool = False,
        allow_rerank: bool | None = None,
    ) -> list[str]:
        del network_online
        del allow_rerank

        query = query.strip()
        if not query or not self._chunks:
            return []

        limit = max(1, top_k)
        candidates = self._keyword_retrieve(query, max(limit, self._settings.rag_fetch_k))
        return [self._format_candidate(item) for item in candidates[:limit]]

    def stats(self) -> dict[str, object]:
        return {
            "retrieval_mode": "local_keyword",
            "offline_only": True,
            "document_count": len(self._documents),
            "chunk_count": len(self._chunks),
            "docs_hash": self._docs_hash,
        }

    def _keyword_retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return []

        scored: list[RetrievalCandidate] = []
        for chunk in self._chunks:
            text = chunk["text"]
            tokens = set(self._tokenize(text))
            overlap = len(query_tokens.intersection(tokens))
            if overlap <= 0:
                continue

            heading_bonus = self._heading_overlap_score(query_tokens, text)
            source_bias = self._source_bias(query, chunk["source"])
            score = float(overlap) + heading_bonus + source_bias
            scored.append(
                RetrievalCandidate(
                    source=chunk["source"],
                    text=text,
                    score=score,
                )
            )

        if not scored:
            return [
                RetrievalCandidate(source=chunk["source"], text=chunk["text"], score=0.0)
                for chunk in self._chunks[:top_k]
            ]

        scored.sort(key=lambda item: (item.score, len(item.text)), reverse=True)
        return scored[:top_k]

    def _heading_overlap_score(self, query_tokens: set[str], text: str) -> float:
        best_overlap = 0
        for line in text.splitlines():
            normalized = line.strip().lstrip("#").strip()
            if not normalized:
                continue
            heading_tokens = set(self._tokenize(normalized))
            best_overlap = max(best_overlap, len(query_tokens.intersection(heading_tokens)))
        return float(best_overlap) * 0.75

    def _source_bias(self, query: str, source: str) -> float:
        normalized_query = query.lower()
        normalized_source = source.lower()

        community_query = any(term in normalized_query for term in ("community", "社区", "值班", "巡查", "随访"))
        sos_query = any(term in normalized_query for term in ("sos", "无应答", "急救", "emergency"))
        oxygen_query = any(term in normalized_query for term in ("oxygen", "spo2", "血氧"))
        fever_query = any(term in normalized_query for term in ("fever", "temperature", "发热", "体温"))
        bp_hr_query = any(term in normalized_query for term in ("blood pressure", "heart rate", "血压", "心率"))
        device_query = any(term in normalized_query for term in ("device", "battery", "offline", "掉线", "电量", "佩戴"))
        report_query = any(term in normalized_query for term in ("report", "summary", "brief", "handoff", "报告", "汇总", "总结", "交班"))
        family_query = any(term in normalized_query for term in ("family", "家属", "家庭"))

        bias = 0.0
        if "community" in normalized_source:
            bias += 2.5 if community_query else -0.5
        if "sos" in normalized_source:
            bias += 2.5 if sos_query else -0.5
        if "oxygen" in normalized_source:
            bias += 3.0 if oxygen_query else 0.0
        if "fever" in normalized_source:
            bias += 2.0 if fever_query else -0.25
        if "pressure" in normalized_source or "heart-rate" in normalized_source:
            bias += 2.0 if bp_hr_query else -0.25
        if "device" in normalized_source:
            bias += 2.0 if device_query else -0.25
        if "report" in normalized_source or "wording" in normalized_source:
            bias += 2.0 if report_query else -0.25
        if "family" in normalized_source:
            bias += 1.5 if family_query or report_query else 0.0

        return bias

    def _load_documents(self) -> list[tuple[str, str]]:
        if not self._knowledge_dir.exists():
            return []

        documents: list[tuple[str, str]] = []
        for path in sorted(self._knowledge_dir.rglob("*.md")):
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            relative = path.relative_to(self._knowledge_dir).as_posix()
            documents.append((relative, content))
        return documents

    def _build_chunks(self, documents: list[tuple[str, str]]) -> list[dict[str, str]]:
        chunk_size = max(240, self._settings.rag_chunk_size)
        overlap = max(0, min(self._settings.rag_chunk_overlap, chunk_size - 1))
        chunks: list[dict[str, str]] = []

        for source, content in documents:
            document_title = self._extract_doc_title(content)
            sections = self._split_sections(content)
            if not sections:
                sections = [content]
            for section_idx, section in enumerate(sections):
                start = 0
                chunk_idx = 0
                while start < len(section):
                    end = min(len(section), start + chunk_size)
                    text = section[start:end].strip()
                    if document_title and text and not text.startswith(document_title):
                        text = f"{document_title}\n{text}"
                    if text:
                        chunks.append(
                            {
                                "source": source,
                                "chunk_id": f"{source}:{section_idx}:{chunk_idx}",
                                "text": text,
                            }
                        )
                        chunk_idx += 1

                    if end >= len(section):
                        break
                    start = max(start + 1, end - overlap)
        return chunks

    def _split_sections(self, content: str) -> list[str]:
        sections: list[str] = []
        current: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and current:
                sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current).strip())
        return [section for section in sections if section]

    def _extract_doc_title(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return ""

    def _format_candidate(self, item: RetrievalCandidate) -> str:
        return f"[{item.source}] {item.text}"

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).lower() for match in self._token_pattern.finditer(text or "")]

    def _build_docs_hash(self, chunks: list[dict[str, str]]) -> str:
        digest = hashlib.sha256()
        for chunk in chunks:
            digest.update(chunk["source"].encode("utf-8"))
            digest.update(b"\n")
            digest.update(chunk["text"].encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()
