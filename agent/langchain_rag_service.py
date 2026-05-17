from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")
os.environ.setdefault("CHROMA_PRODUCT_TELEMETRY_IMPL", "chromadb.telemetry.product.noop.NoOpProductTelemetryClient")

from chromadb.config import Settings as ChromaClientSettings
from langchain_community.document_compressors import DashScopeRerank
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import Settings


@dataclass(slots=True)
class RetrievalCandidate:
    source: str
    text: str
    score: float
    chunk_id: str = ""
    title: str = ""


@dataclass(slots=True)
class KnowledgeDocument:
    source: str
    title: str
    content: str
    fingerprint: str
    size_bytes: int
    modified_at: float


@dataclass(slots=True)
class DocumentFingerprint:
    source: str
    title: str
    sha256: str
    size_bytes: int
    modified_at: float
    chunk_count: int


class LocalOverlapReranker:
    def __init__(self, token_pattern: re.Pattern[str], top_n: int) -> None:
        self._token_pattern = token_pattern
        self._top_n = top_n

    def compress_documents(self, documents: list[Document], query: str) -> list[Document]:
        query_tokens = {match.group(0).lower() for match in self._token_pattern.finditer(query or "")}
        ranked = sorted(
            documents,
            key=lambda doc: self._score(query_tokens, doc.page_content),
            reverse=True,
        )
        return ranked[: self._top_n]

    def _score(self, query_tokens: set[str], text: str) -> float:
        if not query_tokens:
            return 0.0
        tokens = {match.group(0).lower() for match in self._token_pattern.finditer(text or "")}
        overlap = len(query_tokens.intersection(tokens))
        density = overlap / max(len(tokens), 1)
        return float(overlap) + density


class LangChainRAGService:
    """Hybrid local knowledge retrieval with incremental file-level fingerprinting and ChromaDB."""

    def __init__(self, settings: Settings, knowledge_dir: Path) -> None:
        self._settings = settings
        self._knowledge_dir = knowledge_dir
        self._token_pattern = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(320, self._settings.rag_chunk_size),
            chunk_overlap=max(40, min(self._settings.rag_chunk_overlap, max(320, self._settings.rag_chunk_size) - 1)),
            separators=["\n## ", "\n### ", "\n", "。", "！", "？", ".", " "],
        )
        
        knowledge_dir_identity = hashlib.sha256(str(self._knowledge_dir.resolve()).encode("utf-8")).hexdigest()[:10]
        self._vector_collection_name = f"health_knowledge_base_{knowledge_dir_identity}"
        self._chroma_root = Path(self._settings.chroma_path)
        self._manifest_path = self._chroma_root / "rag_manifest.json"
        self._chunks_cache_path = self._chroma_root / "chunks_cache.json"
        
        # Incremental loading
        self._documents, self._chunks, self._file_fingerprints = self._load_incremental()
        self._docs_hash = self._calculate_global_hash(self._file_fingerprints)
        self._local_vectorizer: TfidfVectorizer | None = None
        self._local_vector_matrix = None
        
        # Build retrievers
        self._bm25_retriever = self._build_bm25()
        self._vector_store = self._build_vector_store()
        self._reranker = self._build_reranker()
        if self._vector_store is None:
            self._local_vectorizer, self._local_vector_matrix = self._build_local_vector_index()

    def search(
        self,
        query: str,
        top_k: int = 3,
        *,
        network_online: bool = False,
        allow_rerank: bool | None = None,
    ) -> list[str]:
        del network_online
        results = self.retrieve(query, top_k=top_k, allow_rerank=allow_rerank)
        return [self._format_candidate(item) for item in results]

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        *,
        allow_rerank: bool | None = None,
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query or not self._chunks:
            return []

        limit = max(1, top_k)
        fetch_k = max(limit, self._settings.rag_fetch_k)
        candidates = self._keyword_retrieve(query, fetch_k)
        candidates.extend(self._bm25_retrieve(query, fetch_k))
        candidates.extend(self._vector_retrieve(query, fetch_k))
        merged = self._merge_candidates(candidates)
        rerank_enabled = self._reranker is not None if allow_rerank is None else bool(allow_rerank and self._reranker)

        if rerank_enabled and merged:
            try:
                reranked = self._reranker.compress_documents(
                    documents=[item["document"] for item in merged],
                    query=query,
                )
                ordered = []
                index_by_chunk = {
                    str(item["document"].metadata.get("chunk_id", "")): item for item in merged
                }
                for rank, document in enumerate(reranked):
                    chunk_id = str(document.metadata.get("chunk_id", ""))
                    record = index_by_chunk.get(chunk_id)
                    if record is None:
                        continue
                    ordered.append(
                        {
                            **record,
                            "score": float(record["score"]) + float(max(0.1, limit - rank)) * 0.25,
                        }
                    )
                if ordered:
                    merged = ordered
            except Exception:
                pass

        merged.sort(key=lambda item: item["score"], reverse=True)
        payloads: list[dict[str, Any]] = []
        for item in merged[:limit]:
            document: Document = item["document"]
            payloads.append(
                {
                    "id": str(document.metadata.get("chunk_id", "")),
                    "title": str(document.metadata.get("title", "")),
                    "source_path": str(document.metadata.get("source", "")),
                    "chunk_id": str(document.metadata.get("chunk_id", "")),
                    "snippet": document.page_content.strip(),
                    "score": round(float(item["score"]), 4),
                }
            )
        return payloads

    def stats(self) -> dict[str, object]:
        return {
            "retrieval_mode": "hybrid",
            "document_count": len(self._documents),
            "file_count": len(self._file_fingerprints),
            "chunk_count": len(self._chunks),
            "docs_hash": self._docs_hash,
            "knowledge_dir": str(self._knowledge_dir),
            "vector_collection": self._vector_collection_name,
            "vector_enabled": self._vector_store is not None or self._local_vectorizer is not None,
            "bm25_enabled": self._bm25_retriever is not None,
            "rerank_enabled": self._reranker is not None,
            "vector_backend": "dashscope_chroma" if self._vector_store is not None else ("local_tfidf" if self._local_vectorizer is not None else "disabled"),
            "rerank_backend": "dashscope_rerank" if isinstance(self._reranker, DashScopeRerank) else ("local_overlap" if self._reranker is not None else "disabled"),
            "fingerprint_manifest": str(self._manifest_path),
            "files": [asdict(f) for f in self._file_fingerprints],
        }

    def _load_incremental(self) -> tuple[list[KnowledgeDocument], list[Document], list[DocumentFingerprint]]:
        """Perform recursive directory scan and identify dirty files for incremental update."""
        if not self._knowledge_dir.exists():
            return [], [], []

        # 1. Load manifest
        old_manifest = self._read_manifest()
        previous_dir = str(old_manifest.get("knowledge_dir") or "").strip()
        current_dir = str(self._knowledge_dir)
        if previous_dir and previous_dir != current_dir:
            old_manifest = {}
            try:
                if self._manifest_path.exists():
                    self._manifest_path.unlink()
            except Exception:
                pass
            try:
                if self._chunks_cache_path.exists():
                    self._chunks_cache_path.unlink()
            except Exception:
                pass
        raw_files = old_manifest.get("files", {})
        if isinstance(raw_files, list):
            old_files = {f["source"]: f for f in raw_files if "source" in f}
        else:
            old_files = raw_files
        
        # 2. Scan disk
        current_files: dict[str, dict[str, Any]] = {}
        for path in sorted(self._knowledge_dir.rglob("*.md")):
            stat = path.stat()
            source = path.relative_to(self._knowledge_dir).as_posix()
            current_files[source] = {
                "mtime": float(stat.st_mtime),
                "size": int(stat.st_size),
                "path": path
            }

        # 3. Identify changes
        deleted_sources = set(old_files.keys()) - set(current_files.keys())
        
        new_docs: list[KnowledgeDocument] = []
        existing_docs_metadata: dict[str, dict[str, Any]] = {} # For re-building the state
        
        dirty_sources: set[str] = set(deleted_sources)
        
        for source, info in current_files.items():
            old_info = old_files.get(source)
            # Use mtime/size as first pass hint
            if old_info and old_info.get("mtime") == info["mtime"] and old_info.get("size") == info["size"]:
                existing_docs_metadata[source] = old_info
                continue
            
            # If hint fails, check hash
            path = info["path"]
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            
            fingerprint = self._hash_text(content)
            if old_info and old_info.get("sha256") == fingerprint:
                existing_docs_metadata[source] = old_info
                continue
                
            # File is truly dirty
            dirty_sources.add(source)
            new_docs.append(
                KnowledgeDocument(
                    source=source,
                    title=self._extract_doc_title(content) or path.stem,
                    content=content,
                    fingerprint=fingerprint,
                    size_bytes=info["size"],
                    modified_at=info["mtime"],
                )
            )

        # 4. Load chunks for clean files
        cached_chunks = self._read_chunks_cache()
        clean_chunks = [c for c in cached_chunks if c.metadata.get("source") in existing_docs_metadata]
        
        # 5. Build chunks for new/dirty files
        p_new_chunks = self._build_chunks(new_docs)
        
        # 6. Final merged state
        all_chunks = clean_chunks + p_new_chunks
        
        # Log summary
        print(f"RAG Incremental Load: {len(clean_chunks)} clean chunks, {len(p_new_chunks)} new chunks. Dirty: {len(dirty_sources)}, Deleted: {len(deleted_sources)}")
        
        # Re-build knowledge documents list (partially populated for stats if needed)
        # Note: we don't hold full text of clean documents in memory to save RAM
        final_docs = new_docs # + we could add placeholders for clean ones
        
        # Re-build fingerprints
        final_fingerprints = self._build_file_fingerprints_incremental(
            existing_docs_metadata, new_docs, all_chunks
        )
        
        # 7. Persist manifest and chunks early if something changed
        if dirty_sources or deleted_sources:
            # We will finalize vector store update in _build_vector_store
            # but we need to track what to delete
            self._dirty_sources = dirty_sources
            self._deleted_sources = deleted_sources
            self._chroma_root.mkdir(parents=True, exist_ok=True)
            self._write_fingerprint_manifest(final_fingerprints)
            self._write_chunks_cache(all_chunks)
        else:
            self._dirty_sources = set()
            self._deleted_sources = set()

        return final_docs, all_chunks, final_fingerprints

    def _build_vector_store(self) -> Chroma | None:
        if not self._chunks or not self._settings.tongyi_embedding_configured:
            return None
        try:
            embeddings = DashScopeEmbeddings(
                model=self._settings.tongyi_embedding_model,
                dashscope_api_key=self._settings.dashscope_api_key,
            )
            self._chroma_root.mkdir(parents=True, exist_ok=True)
            store = Chroma(
                collection_name=self._vector_collection_name,
                embedding_function=embeddings,
                persist_directory=str(self._chroma_root),
                client_settings=ChromaClientSettings(anonymized_telemetry=False, is_persistent=True),
            )
            
            # Incremental Update to ChromaDB
            if self._dirty_sources or self._deleted_sources:
                dirty_chunks = [c for c in self._chunks if c.metadata.get("source") in self._dirty_sources]
                print(
                    "Updating ChromaDB: deleting %d sources, adding %d chunks.",
                    len(self._dirty_sources | self._deleted_sources),
                    len(dirty_chunks),
                )
                for source in self._dirty_sources | self._deleted_sources:
                    # LangChain Chroma doesn't have a direct 'delete by metadata' easily in one line without exposing client
                    # but we can use the underlying collection
                    store.delete(where={"source": source})
                
                # Add only the chunks from dirty_sources (which are in self._documents/new_chunks)
                # But here we already have self._chunks as the FULL set.
                # We should only add chunks that belong to the new/dirty docs.
                if dirty_chunks:
                    store.add_documents(
                        dirty_chunks,
                        ids=[str(chunk.metadata.get("chunk_id", "")) for chunk in dirty_chunks],
                    )
            
            return store
        except Exception:
            return None

    def _read_manifest(self) -> dict[str, Any]:
        if not self._manifest_path.exists():
            return {}
        try:
            return json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_fingerprint_manifest(self, fingerprints: list[DocumentFingerprint]) -> None:
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "docs_hash": self._calculate_global_hash(fingerprints),
            "vector_collection": self._vector_collection_name,
            "knowledge_dir": str(self._knowledge_dir),
            "files": {f.source: asdict(f) for f in fingerprints},
            "last_indexed": datetime.now().isoformat()
        }
        self._manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_chunks_cache(self) -> list[Document]:
        if not self._chunks_cache_path.exists():
            return []
        try:
            data = json.loads(self._chunks_cache_path.read_text(encoding="utf-8"))
            return [Document(page_content=d["text"], metadata=d["metadata"]) for d in data]
        except Exception:
            return []

    def _write_chunks_cache(self, chunks: list[Document]) -> None:
        self._chunks_cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"text": c.page_content, "metadata": c.metadata} for c in chunks]
        self._chunks_cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _calculate_global_hash(self, fingerprints: list[DocumentFingerprint]) -> str:
        digest = hashlib.sha256()
        for f in sorted(fingerprints, key=lambda x: x.source):
            digest.update(f.source.encode("utf-8"))
            digest.update(f.sha256.encode("utf-8"))
        return digest.hexdigest()

    def _build_bm25(self) -> BM25Retriever | None:
        if not self._chunks:
            return None
        try:
            retriever = BM25Retriever.from_documents(self._chunks)
            retriever.k = max(4, self._settings.rag_fetch_k)
            return retriever
        except Exception:
            return None

    def _build_reranker(self) -> DashScopeRerank | None:
        if self._settings.qwen_enable_rerank and self._settings.tongyi_rerank_configured:
            try:
                return DashScopeRerank(
                    model=self._settings.tongyi_rerank_model,
                    api_key=self._settings.dashscope_api_key,
                    top_n=max(3, self._settings.rag_top_k),
                )
            except Exception:
                pass
        if not self._chunks:
            return None
        try:
            return LocalOverlapReranker(self._token_pattern, max(3, self._settings.rag_top_k))
        except Exception:
            return None

    def _build_local_vector_index(self) -> tuple[TfidfVectorizer | None, Any]:
        if not self._chunks:
            return None, None
        try:
            vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 4),
                min_df=1,
                max_features=12000,
            )
            matrix = vectorizer.fit_transform([chunk.page_content for chunk in self._chunks])
            return vectorizer, matrix
        except Exception:
            return None, None

    def _vector_retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        if self._vector_store is not None:
            try:
                docs_with_scores = self._vector_store.similarity_search_with_relevance_scores(query, k=top_k)
            except Exception:
                docs_with_scores = []
            candidates: list[RetrievalCandidate] = []
            for document, score in docs_with_scores:
                candidates.append(
                    RetrievalCandidate(
                        source=str(document.metadata.get("source", "")),
                        text=document.page_content,
                        score=float(score or 0.5) + 1.0,
                        chunk_id=str(document.metadata.get("chunk_id", "")),
                        title=str(document.metadata.get("title", "")),
                    )
                )
            if candidates:
                return candidates
        if self._local_vectorizer is None or self._local_vector_matrix is None:
            return []
        try:
            query_vec = self._local_vectorizer.transform([query])
            similarities = cosine_similarity(query_vec, self._local_vector_matrix).ravel()
        except Exception:
            return []
        top_indices = similarities.argsort()[::-1][:top_k]
        candidates = []
        for index in top_indices:
            score = float(similarities[index])
            if score <= 0:
                continue
            document = self._chunks[int(index)]
            candidates.append(
                RetrievalCandidate(
                    source=str(document.metadata.get("source", "")),
                    text=document.page_content,
                    score=score + 0.75,
                    chunk_id=str(document.metadata.get("chunk_id", "")),
                    title=str(document.metadata.get("title", "")),
                )
            )
        return candidates

    def _bm25_retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        if self._bm25_retriever is None:
            return []
        try:
            documents = self._bm25_retriever.invoke(query)
        except Exception:
            return []
        candidates: list[RetrievalCandidate] = []
        for rank, document in enumerate(documents[:top_k]):
            candidates.append(
                RetrievalCandidate(
                    source=str(document.metadata.get("source", "")),
                    text=document.page_content,
                    score=float(max(1, top_k - rank)) * 0.65,
                    chunk_id=str(document.metadata.get("chunk_id", "")),
                    title=str(document.metadata.get("title", "")),
                )
            )
        return candidates

    def _keyword_retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return []

        scored: list[RetrievalCandidate] = []
        for chunk in self._chunks:
            text = chunk.page_content
            tokens = set(self._tokenize(text))
            overlap = len(query_tokens.intersection(tokens))
            if overlap <= 0:
                continue
            heading_bonus = self._heading_overlap_score(query_tokens, text)
            source_bias = self._source_bias(query, str(chunk.metadata.get("source", "")))
            scored.append(
                RetrievalCandidate(
                    source=str(chunk.metadata.get("source", "")),
                    text=text,
                    score=float(overlap) + heading_bonus + source_bias,
                    chunk_id=str(chunk.metadata.get("chunk_id", "")),
                    title=str(chunk.metadata.get("title", "")),
                )
            )
        scored.sort(key=lambda item: (item.score, len(item.text)), reverse=True)
        return scored[:top_k]

    def _merge_candidates(self, candidates: list[RetrievalCandidate]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in candidates:
            chunk_id = item.chunk_id or f"{item.source}:{hash(item.text)}"
            existing = merged.get(chunk_id)
            if existing is None:
                document = next(
                    (
                        chunk
                        for chunk in self._chunks
                        if str(chunk.metadata.get("chunk_id", "")) == chunk_id
                    ),
                    None,
                )
                if document is None:
                    document = Document(
                        page_content=item.text,
                        metadata={
                            "source": item.source,
                            "title": item.title or Path(item.source).stem,
                            "chunk_id": chunk_id,
                        },
                    )
                merged[chunk_id] = {
                    "document": document,
                    "score": float(item.score),
                }
                continue
            existing["score"] = max(float(existing["score"]), float(item.score)) + 0.1
        return list(merged.values())

    def _build_chunks(self, documents: list[KnowledgeDocument]) -> list[Document]:
        chunks: list[Document] = []
        for document in documents:
            for index, chunk in enumerate(self._splitter.split_text(document.content)):
                text = chunk.strip()
                if not text:
                    continue
                chunks.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": document.source,
                            "title": document.title,
                            "chunk_id": f"{document.source}:{index}:{document.fingerprint[:12]}",
                            "source_fingerprint": document.fingerprint,
                        },
                    )
                )
        return chunks

    def _extract_doc_title(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return ""

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
        checks = {
            "community": ("社区", "值守", "巡查", "随访", "养老"),
            "sos": ("sos", "急救", "求救", "紧急呼叫"),
            "oxygen": ("血氧", "低氧", "氧饱和度", "spo2"),
            "fever": ("发热", "体温", "高热", "低热"),
            "pressure": ("血压", "心率", "脉搏", "高压", "低压"),
            "device": ("设备", "电量", "掉线", "离线", "链路"),
            "report": ("报告", "总结", "交班", "模板", "表述"),
            "family": ("家属", "家庭", "照护", "看护"),
            "fall": ("跌倒", "倒地", "摔倒", "滑倒", "坠地"),
            "posture": ("姿态", "体态", "倾斜", "静止", "坍坐"),
            "camera": ("摄像头", "视频", "画面", "黑屏", "卡顿", "rtsp"),
            "alarm": ("告警", "报警", "分诊", "优先级", "预警"),
            "review": ("复核", "人工复核", "核查", "排查", "检查清单"),
            "event": ("事件", "记录", "模板", "处置", "经过"),
        }
        bias = 0.0
        if "community" in normalized_source:
            bias += 2.0 if any(term in normalized_query for term in checks["community"]) else -0.25
        if "sos" in normalized_source:
            bias += 2.0 if any(term in normalized_query for term in checks["sos"]) else -0.25
        if "oxygen" in normalized_source:
            bias += 2.0 if any(term in normalized_query for term in checks["oxygen"]) else 0.0
        if "fever" in normalized_source:
            bias += 1.5 if any(term in normalized_query for term in checks["fever"]) else 0.0
        if "pressure" in normalized_source or "heart-rate" in normalized_source:
            bias += 1.5 if any(term in normalized_query for term in checks["pressure"]) else 0.0
        if "device" in normalized_source:
            bias += 1.0 if any(term in normalized_query for term in checks["device"]) else 0.0
        if "report" in normalized_source or "wording" in normalized_source:
            bias += 1.0 if any(term in normalized_query for term in checks["report"]) else 0.0
        if "family" in normalized_source:
            bias += 0.75 if any(term in normalized_query for term in checks["family"]) else 0.0
        if "fall" in normalized_source:
            bias += 2.0 if any(term in normalized_query for term in checks["fall"]) else 0.0
        if "posture" in normalized_source:
            bias += 1.75 if any(term in normalized_query for term in checks["posture"]) else 0.0
        if "camera" in normalized_source:
            bias += 1.75 if any(term in normalized_query for term in checks["camera"]) else 0.0
        if "alarm" in normalized_source:
            bias += 1.5 if any(term in normalized_query for term in checks["alarm"]) else 0.0
        if "review" in normalized_source or "checklist" in normalized_source:
            bias += 1.5 if any(term in normalized_query for term in checks["review"]) else 0.0
        if "event" in normalized_source:
            bias += 1.25 if any(term in normalized_query for term in checks["event"]) else 0.0
        return bias

    def _format_candidate(self, item: dict[str, Any]) -> str:
        return f"[{item['source_path']}] {item['snippet']}"

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).lower() for match in self._token_pattern.finditer(text or "")]

    def _build_file_fingerprints_incremental(
        self,
        clean_docs_meta: dict[str, dict[str, Any]],
        new_docs: list[KnowledgeDocument],
        all_chunks: list[Document]
    ) -> list[DocumentFingerprint]:
        chunk_counts: dict[str, int] = {}
        for chunk in all_chunks:
            source = str(chunk.metadata.get("source", ""))
            if not source:
                continue
            chunk_counts[source] = chunk_counts.get(source, 0) + 1
            
        fingerprints: list[DocumentFingerprint] = []
        
        # Clean docs
        for source, meta in clean_docs_meta.items():
            fingerprints.append(
                DocumentFingerprint(
                    source=source,
                    title=meta.get("title", source),
                    sha256=meta.get("sha256", ""),
                    size_bytes=meta.get("size", 0),
                    modified_at=meta.get("mtime", 0.0),
                    chunk_count=chunk_counts.get(source, 0)
                )
            )
            
        # New docs
        for doc in new_docs:
            fingerprints.append(
                DocumentFingerprint(
                    source=doc.source,
                    title=doc.title,
                    sha256=doc.fingerprint,
                    size_bytes=doc.size_bytes,
                    modified_at=doc.modified_at,
                    chunk_count=chunk_counts.get(doc.source, 0)
                )
            )
            
        return fingerprints

    @staticmethod
    def _hash_text(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
