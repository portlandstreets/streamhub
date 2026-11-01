import asyncio
import json
import logging
import math
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("core.search")

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
LOCAL_ELASTICSEARCH_URL = os.getenv("LOCAL_ELASTICSEARCH_URL", "http://127.0.0.1:9200")
INDEX_NAME = "streams_index"


def is_port_open(url: str, timeout: float = 0.2) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        if host == "localhost":
            host = "127.0.0.1"
        port = parsed.port or 9200

        # On Windows host, non-IP hosts like 'elasticsearch' stall on NetBIOS/DNS resolution
        if os.name == "nt" and not re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
            return False

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False


def tokenize(text: str) -> List[str]:
    """Tokenize and normalize text into clean words."""
    if not text:
        return []
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [word for word in cleaned.split() if len(word) >= 2]


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance for fuzzy matching."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


class EmbeddedLuceneIndex:
    """
    In-memory Lucene-compatible Inverted Index implementing:
    - Inverted posting lists
    - Lucene BM25 scoring formula (k1=1.2, b=0.75)
    - Field-specific weight multipliers (title^3, owner^2, description^1)
    - Fuzzy match fallback (Levenshtein distance <= 2 for words >= 4 chars)
    - Text snippet highlighting (<mark>...</mark>)
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: Dict[int, Dict[str, Any]] = {}
        # Inverted index: term -> {doc_id: term_frequency}
        self.inverted_index: Dict[str, Dict[int, int]] = {}
        # Document field lengths for BM25 normalization
        self.doc_lengths: Dict[int, int] = {}
        self.total_tokens: int = 0

    def clear(self):
        self.documents.clear()
        self.inverted_index.clear()
        self.doc_lengths.clear()
        self.total_tokens = 0

    def add_document(self, doc_id: int, data: Dict[str, Any]):
        self.remove_document(doc_id)
        self.documents[doc_id] = data

        title_tokens = tokenize(data.get("title", ""))
        desc_tokens = tokenize(data.get("description", ""))
        owner_tokens = tokenize(data.get("owner", ""))

        # Weighted tokens (title weight 3x, owner 2x, desc 1x)
        field_tokens: List[Tuple[str, int]] = []
        for t in title_tokens:
            field_tokens.append((t, 3))
        for t in owner_tokens:
            field_tokens.append((t, 2))
        for t in desc_tokens:
            field_tokens.append((t, 1))

        doc_len = len(field_tokens)
        self.doc_lengths[doc_id] = doc_len
        self.total_tokens += doc_len

        tf_map: Dict[str, int] = {}
        for token, weight in field_tokens:
            tf_map[token] = tf_map.get(token, 0) + weight

        for token, weighted_tf in tf_map.items():
            if token not in self.inverted_index:
                self.inverted_index[token] = {}
            self.inverted_index[token][doc_id] = weighted_tf

    def remove_document(self, doc_id: int):
        if doc_id in self.documents:
            del self.documents[doc_id]
            doc_len = self.doc_lengths.pop(doc_id, 0)
            self.total_tokens -= doc_len
            for token in list(self.inverted_index.keys()):
                if doc_id in self.inverted_index[token]:
                    del self.inverted_index[token][doc_id]
                    if not self.inverted_index[token]:
                        del self.inverted_index[token]

    def search(self, query: str, fuzzy: bool = True, limit: int = 20) -> List[Dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens or not self.documents:
            return []

        num_docs = len(self.documents)
        avg_doc_len = (self.total_tokens / num_docs) if num_docs > 0 else 1.0

        scores: Dict[int, float] = {}
        matched_tokens: Dict[int, Set[str]] = {}

        for q_token in query_tokens:
            # Find candidate index terms: exact match or fuzzy match
            candidate_terms: List[Tuple[str, float]] = []
            if q_token in self.inverted_index:
                candidate_terms.append((q_token, 1.0))
            elif fuzzy and len(q_token) >= 3:
                for term in self.inverted_index.keys():
                    if abs(len(term) - len(q_token)) <= 2:
                        dist = levenshtein_distance(q_token, term)
                        max_allowed = 1 if len(q_token) <= 4 else 2
                        if dist <= max_allowed:
                            # Fuzzy penalty
                            penalty = 1.0 / (1.0 + dist * 0.4)
                            candidate_terms.append((term, penalty))

            for term, term_factor in candidate_terms:
                postings = self.inverted_index.get(term, {})
                df = len(postings)
                # Lucene BM25 IDF: ln(1 + (N - df + 0.5) / (df + 0.5))
                idf = math.log(1.0 + (num_docs - df + 0.5) / (df + 0.5))
                if idf <= 0:
                    idf = 0.1

                for doc_id, tf in postings.items():
                    doc_len = self.doc_lengths.get(doc_id, avg_doc_len)
                    # BM25 term frequency saturation
                    num = tf * (self.k1 + 1.0)
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_doc_len))
                    term_score = idf * (num / denom) * term_factor

                    scores[doc_id] = scores.get(doc_id, 0.0) + term_score
                    if doc_id not in matched_tokens:
                        matched_tokens[doc_id] = set()
                    matched_tokens[doc_id].add(term)

        # Sort documents by score descending
        sorted_hits = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        results = []
        for doc_id, score in sorted_hits:
            doc = self.documents[doc_id]
            terms = matched_tokens.get(doc_id, set())

            # Highlight occurrences
            title = doc.get("title", "")
            description = doc.get("description", "")
            highlights = {}

            hl_title = title
            hl_desc = description
            for t in terms:
                pattern = re.compile(re.escape(t), re.IGNORECASE)
                hl_title = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", hl_title)
                hl_desc = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", hl_desc)

            if "<mark>" in hl_title:
                highlights["title"] = [hl_title]
            if "<mark>" in hl_desc:
                highlights["description"] = [hl_desc]

            results.append({
                "id": doc.get("id", doc_id),
                "title": doc.get("title", ""),
                "description": doc.get("description", ""),
                "owner": doc.get("owner", ""),
                "is_live": doc.get("is_live", False),
                "viewers_count": doc.get("viewers_count", 0),
                "thumbnail_url": doc.get("thumbnail_url"),
                "score": round(score, 3),
                "highlights": highlights,
            })

        return results


class SearchManager:
    """
    Enterprise Search Engine (B4 Requirement) connecting to Elasticsearch with
    automatic fallback to Embedded Lucene Index.
    """

    def __init__(self):
        self.embedded_lucene = EmbeddedLuceneIndex()
        self.es_url: Optional[str] = None
        self.is_es_healthy: bool = False
        self._last_check_time: float = 0.0
        self._retry_delay: float = 30.0  # seconds backoff between reconnect attempts

    def _determine_es_url(self) -> Optional[str]:
        # Fast local checks: prefer localhost first if outside docker, or elasticsearch if inside
        for candidate in [LOCAL_ELASTICSEARCH_URL, ELASTICSEARCH_URL]:
            if is_port_open(candidate, timeout=0.1):
                return candidate
        return None

    def _send_es_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        timeout: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        """Synchronous HTTP request to Elasticsearch REST API."""
        if not self.es_url:
            return None
        url = f"{self.es_url.rstrip('/')}/{path.lstrip('/')}"
        data_bytes = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            logger.warning("Elasticsearch HTTP error on %s %s: %s", method, path, e)
            return None
        except Exception as e:
            logger.warning("Elasticsearch connection failed on %s %s: %s", method, path, e)
            self.is_es_healthy = False
            return None

    async def initialize(self):
        """Check Elasticsearch availability with 30s backoff."""
        now = time.time()
        if (now - self._last_check_time) < self._retry_delay:
            return

        self._last_check_time = now
        self.es_url = self._determine_es_url()

        if self.es_url:
            health = self._send_es_request("GET", "/")
            if health and "version" in health:
                self.is_es_healthy = True
                logger.info(
                    "Connected to Elasticsearch %s at %s",
                    health["version"].get("number", "unknown"),
                    self.es_url,
                )
                self._ensure_index_mapping()
                return

        self.is_es_healthy = False

    def _ensure_index_mapping(self):
        """Create streams_index with standard text analyzers and keyword sub-fields."""
        schema = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "stream_text_analyzer": {
                            "type": "standard",
                            "stopwords": "_english_",
                        }
                    }
                },
            },
            "mappings": {
                "properties": {
                    "id": {"type": "integer"},
                    "title": {
                        "type": "text",
                        "analyzer": "stream_text_analyzer",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "description": {
                        "type": "text",
                        "analyzer": "stream_text_analyzer",
                    },
                    "owner": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "is_live": {"type": "boolean"},
                    "viewers_count": {"type": "integer"},
                    "created_at": {"type": "date"},
                }
            },
        }
        exists = self._send_es_request("HEAD", INDEX_NAME)
        if exists is None:
            created = self._send_es_request("PUT", INDEX_NAME, schema)
            if created:
                logger.info("Created Elasticsearch index: %s", INDEX_NAME)

    async def index_stream(self, stream_id: int, data: Dict[str, Any]):
        """Index a stream document in both Elasticsearch and Embedded Lucene index."""
        # Always update embedded index for immediate availability
        self.embedded_lucene.add_document(stream_id, data)

        await self.initialize()
        if self.is_es_healthy:
            doc = {
                "id": stream_id,
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "owner": data.get("owner", ""),
                "is_live": data.get("is_live", False),
                "viewers_count": data.get("viewers_count", 0),
                "thumbnail_url": data.get("thumbnail_url"),
                "created_at": data.get("created_at"),
            }
            self._send_es_request("PUT", f"{INDEX_NAME}/_doc/{stream_id}", doc)

    async def remove_stream(self, stream_id: int):
        """Remove a stream document from both indices."""
        self.embedded_lucene.remove_document(stream_id)

        await self.initialize()
        if self.is_es_healthy:
            self._send_es_request("DELETE", f"{INDEX_NAME}/_doc/{stream_id}")

    async def search(self, query: str, fuzzy: bool = True, limit: int = 20) -> Dict[str, Any]:
        """
        Execute full-text query with BM25 ranking, typo tolerance, and highlights.
        """
        start_time = time.perf_counter()
        query_str = query.strip()
        if not query_str:
            return {
                "query": "",
                "total_hits": 0,
                "took_ms": 0.0,
                "engine": "Elasticsearch 8.11" if self.is_es_healthy else "Lucene (Embedded)",
                "results": [],
            }

        await self.initialize()

        if self.is_es_healthy:
            es_query = {
                "size": limit,
                "query": {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["title^3", "owner^2", "description^1"],
                                    "fuzziness": "AUTO" if fuzzy else "0",
                                    "prefix_length": 1,
                                }
                            },
                            {
                                "wildcard": {
                                    "title.keyword": {
                                        "value": f"*{query_str.lower()}*",
                                        "boost": 1.5,
                                    }
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "highlight": {
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                    "fields": {
                        "title": {},
                        "description": {},
                        "owner": {},
                    },
                },
            }

            resp = self._send_es_request("POST", f"{INDEX_NAME}/_search", es_query)
            if resp and "hits" in resp:
                took_ms = round((time.perf_counter() - start_time) * 1000, 2)
                raw_hits = resp["hits"].get("hits", [])
                results = []
                for hit in raw_hits:
                    src = hit.get("_source", {})
                    results.append({
                        "id": src.get("id"),
                        "title": src.get("title"),
                        "description": src.get("description", ""),
                        "owner": src.get("owner", ""),
                        "is_live": src.get("is_live", False),
                        "viewers_count": src.get("viewers_count", 0),
                        "thumbnail_url": src.get("thumbnail_url"),
                        "score": round(hit.get("_score", 0.0), 3),
                        "highlights": hit.get("highlight", {}),
                    })

                return {
                    "query": query_str,
                    "total_hits": resp["hits"].get("total", {}).get("value", len(results)),
                    "took_ms": took_ms,
                    "engine": "Elasticsearch 8.11",
                    "results": results,
                }

        # Embedded Lucene Engine Fallback
        results = self.embedded_lucene.search(query_str, fuzzy=fuzzy, limit=limit)
        took_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "query": query_str,
            "total_hits": len(results),
            "took_ms": took_ms,
            "engine": "Lucene (Embedded)",
            "results": results,
        }

    async def get_status(self) -> Dict[str, Any]:
        """Health check endpoint for B4 verification."""
        await self.initialize()
        return {
            "engine": "Elasticsearch 8.11" if self.is_es_healthy else "Lucene (Embedded)",
            "elasticsearch_connected": self.is_es_healthy,
            "elasticsearch_url": self.es_url,
            "index_name": INDEX_NAME,
            "embedded_documents_count": len(self.embedded_lucene.documents),
            "embedded_terms_count": len(self.embedded_lucene.inverted_index),
            "bm25_parameters": {"k1": self.embedded_lucene.k1, "b": self.embedded_lucene.b},
            "status": "ready",
        }


# Global singleton search manager instance
search_engine = SearchManager()
