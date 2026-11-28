"""Validate the curated articles and rank them with local sparse TF-IDF vectors."""

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from diagnostic_state import Category, SpecializedCategory


DATA_PATH = Path(__file__).with_name("data") / "knowledge_base.json"
MAX_REFERENCES = 3
MIN_SIMILARITY = 0.18
STRONG_DIRECT_SIMILARITY = 0.45
DISCONFIRMING_SIMILARITY = 0.26
STOP_WORDS = set(
    "about after all also am an and any are as at be been but by can could did do does for from "
    "get going had has have how in is it just keeps like me my near no not now of on one only or our "
    "out same say see should so some still than that the their then there these they this those through "
    "to too try up use used very was were what when where which while why will with work works would you your "
    "computer computers desktop laptop laptops pc pcs windows issue issues problem problems happen happens "
    "wrong help fix check start need thing something stopped working".split()
)
TERM_ALIASES = {
    "application": "app", "applications": "app", "apps": "app", "audio": "sound",
    "disconnected": "disconnect", "disconnecting": "disconnect", "disconnects": "disconnect",
    "drop": "disconnect", "drops": "disconnect", "dropping": "disconnect",
    "freezes": "freeze", "freezing": "freeze", "hung": "freeze", "hangs": "freeze",
    "mic": "microphone", "ram": "memory", "processor": "cpu", "processors": "cpu",
    "sluggish": "slow", "slower": "slow", "slowdown": "slow",
    "overheats": "overheat", "overheating": "overheat",
}
FOLLOW_UP = re.compile(
    r"^\s*(?:(?:it|this|that) (?:still|also|keeps|happens|did not|didn't)|"
    r"still (?:happens|the same)|same (?:issue|problem)|no change|nothing changed|"
    r"still having|unable to complete|(?:only|both) (?:this|the|my|devices?))\b",
    re.IGNORECASE,
)
CLAUSE_BREAK = re.compile(r"\s+\b(?:and|but)\b\s+|[;\n]|[,.!?](?=\s|$)", re.IGNORECASE)
FREE_CAPACITY = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(gb|tb)\s+(?:of\s+)?(?:(?:disk space|storage)\s+)?(?:free|available)\b",
    re.IGNORECASE,
)
CAPACITY_QUALIFIERS = re.compile(
    r"\b(?:don't have|do not have|doesn't have|does not have|less than|under|if|had|need|requires?)\b",
    re.IGNORECASE,
)
NO_SPACE_WARNING = re.compile(
    r"\b(?:plenty of (?:free |available )?(?:disk space|storage|space)|no low (?:disk space|storage) warning)\b",
    re.IGNORECASE,
)
RULED_OUT_CAUSE = re.compile(
    r"\b(?:I|we) (?:have |already )?ruled out\s+(.+)|"
    r"^(.+?)\s+(?:isn't|is not|wasn't|was not)\s+(?:the cause|the problem|an issue)\b",
    re.IGNORECASE,
)
CAPACITY_TOPIC = "Low free disk space on the system drive or Windows Update needs more space"
GENERIC_TERMS = {
    "app", "available", "call", "connect", "connected", "disk", "disconnect", "drive", "error", "free",
    "freeze", "gb", "gets", "install", "more", "need", "says", "slow", "space", "storage", "time", "update", "usb",
}
SINGLE_TERM_CLUES = {
    "bluetooth", "ethernet", "fps", "internet", "lowspace", "microphone", "onedrive", "overheat", "sound", "wifi",
}
NonemptyText = Annotated[str, Field(min_length=1)]
TextItems = Annotated[tuple[NonemptyText, ...], Field(min_length=1)]


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: NonemptyText
    title: NonemptyText
    category: SpecializedCategory
    symptoms: TextItems
    possible_causes: TextItems
    diagnostic_steps: TextItems
    safety: NonemptyText
    source_organization: NonemptyText
    source_title: NonemptyText
    source_url: Annotated[str, Field(pattern=r"^https://[^/\s]+/\S+$")]


class KnowledgeBaseError(Exception):
    """The local collection cannot be read or validated."""


@dataclass(frozen=True)
class RetrievalResult:
    documents: tuple[KnowledgeDocument, ...] = ()
    available: bool = True


def _tokens(text: str) -> list[str]:
    text = re.sub(r"\bwi[\s\-‑–]?fi\b", "wifi", text.lower())
    text = re.sub(r"\bc\s*:\s*(?:drive\b)?", " cdrive ", text)
    text = re.sub(r"\bc drive\b", "cdrive", text)
    text = re.sub(r"\bframe rates?\b", "fps", text)
    text = re.sub(
        r"\b(?:needs? (?:more|additional)|not enough|running out of|low) (?:disk |drive )?(?:space|storage)\b",
        "lowspace",
        text,
    )
    tokens = []
    for term in re.findall(r"[a-z][a-z0-9]+", text):
        if term in STOP_WORDS:
            continue
        normalized = TERM_ALIASES.get(term, term)
        if len(normalized) > 4 and normalized.endswith("s") and not normalized.endswith(("ss", "us", "fps")):
            normalized = normalized[:-1]
        tokens.append(normalized)
    return tokens


def _similarity(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(weight * right.get(term, 0) for term, weight in left.items())


def _specific_overlap(query: dict[str, float], document: dict[str, float]) -> bool:
    common = query.keys() & document.keys()
    return bool(common & SINGLE_TERM_CLUES or (len(common) >= 2 and common - GENERIC_TERMS))


def _separate_findings(text: str) -> tuple[list[str], list[str]]:
    """Keep observations that argue against a cause out of the positive query."""
    clues, disconfirmed = [], []
    for clause in CLAUSE_BREAK.split(text):
        # Ample reported free space lowers relevance for capacity advice. It does not verify the drive.
        capacity = FREE_CAPACITY.search(clause)
        ample = capacity and float(capacity[1]) * (1024 if capacity[2].lower() == "tb" else 1) >= 64
        explicit = NO_SPACE_WARNING.search(clause)
        observation = (capacity if ample else None) or explicit
        ruled_out = RULED_OUT_CAUSE.search(clause)
        if observation and not CAPACITY_QUALIFIERS.search(clause[:observation.start()]):
            disconfirmed.append(CAPACITY_TOPIC)
        elif ruled_out:
            disconfirmed.append(ruled_out[1] or ruled_out[2])
        elif clause.strip():
            clues.append(clause)
    return clues, disconfirmed


class KnowledgeBase:
    def __init__(self, documents: tuple[KnowledgeDocument, ...]):
        self.documents = documents
        terms = [Counter(_tokens(" ".join((doc.title, *doc.symptoms)))) for doc in documents]
        document_frequency = Counter(term for counts in terms for term in counts)
        self._idf = {
            term: 1 + math.log((1 + len(documents)) / (1 + frequency))
            for term, frequency in document_frequency.items()
        }
        self._vectors = [self._vector(counts) for counts in terms]

    def _vector(self, counts: Counter) -> dict[str, float]:
        weights = {
            term: (1 + math.log(count)) * self._idf[term]
            for term, count in counts.items()
            if term in self._idf
        }
        length = math.sqrt(sum(weight * weight for weight in weights.values()))
        return {term: weight / length for term, weight in weights.items()}

    def _clear_category(self, text: str) -> SpecializedCategory | None:
        """Recognize confident categories in separate symptom clauses."""
        query = self._vector(Counter(_tokens(text)))
        scores = {}
        for doc, vector in zip(self.documents, self._vectors, strict=True):
            if _specific_overlap(query, vector):
                score = _similarity(query, vector)
                scores[doc.category] = max(score, scores.get(doc.category, 0))
        if not scores:
            return None
        ranked = sorted(scores.items(), key=lambda item: -item[1])
        category, best = ranked[0]
        if best >= MIN_SIMILARITY and all(score < 0.76 * best for _, score in ranked[1:]):
            return category
        return None

    def search(
        self,
        latest: str,
        *,
        original: str = "",
        category: Category | None = None,
        session_context: tuple[str, ...] = (),
        findings: tuple[str, ...] = (),
    ) -> tuple[KnowledgeDocument, ...]:
        """Rank current evidence, using an explicit category selection only as a preference."""
        clauses, disconfirmed = _separate_findings(latest)
        if len(clauses) > 1:
            detected = {self._clear_category(clause) for clause in clauses} - {None}
            if len(detected) > 1 and category not in detected:
                return ()

        retained_clues, retained_disconfirmed = _separate_findings("\n".join((original, *session_context)))
        for finding in findings:
            _, rejected = _separate_findings(finding)
            retained_disconfirmed.extend(rejected)
        negative_queries = [
            self._vector(Counter(_tokens(text)))
            for text in dict.fromkeys((*disconfirmed, *retained_disconfirmed))
        ]
        newest = self._vector(Counter(_tokens(" ".join(clauses))))
        context = self._vector(Counter(_tokens(" ".join(retained_clues))))
        follow_up = bool(original and latest != original and FOLLOW_UP.search(latest))
        scores = []
        for doc, vector in zip(self.documents, self._vectors, strict=True):
            direct = _similarity(newest, vector)
            retained = _similarity(context, vector)
            if direct < STRONG_DIRECT_SIMILARITY and any(
                _similarity(query, vector) >= DISCONFIRMING_SIMILARITY for query in negative_queries
            ):
                continue
            if direct >= MIN_SIMILARITY and _specific_overlap(newest, vector):
                score = direct + 0.18 * retained
            elif follow_up and (direct > 0 or not newest) and _specific_overlap(context, vector):
                score = 0.65 * retained + direct
            else:
                continue
            if score >= MIN_SIMILARITY:
                scores.append((score * (1.10 if doc.category == category else 1), doc))

        scores.sort(key=lambda item: (-item[0], item[1].id))
        if not scores:
            return ()
        best_score, best_doc = scores[0]
        if best_doc.category != category and any(
            doc.category != best_doc.category and score >= 0.76 * best_score for score, doc in scores[1:]
        ):
            return ()
        return tuple(
            doc for score, doc in scores
            if doc.category == best_doc.category and score >= 0.60 * best_score
        )[:MAX_REFERENCES]


@lru_cache(maxsize=4)
def load_knowledge_base(path: Path = DATA_PATH) -> KnowledgeBase:
    """Build a reusable index from the bundled data without a network connection."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not data:
            raise ValueError("Expected a non-empty document list.")
        documents = tuple(KnowledgeDocument.model_validate(item) for item in data)
        if len({doc.id for doc in documents}) != len(documents):
            raise ValueError("Document IDs must be unique.")
    except (OSError, ValueError):
        raise KnowledgeBaseError("The local knowledge base is missing or invalid.") from None
    return KnowledgeBase(documents)


def retrieve_references(
    latest: str,
    *,
    original: str = "",
    category: Category | None = None,
    session_context: tuple[str, ...] = (),
    findings: tuple[str, ...] = (),
) -> RetrievalResult:
    try:
        index = load_knowledge_base()
    except KnowledgeBaseError:
        return RetrievalResult(available=False)
    return RetrievalResult(index.search(
        latest, original=original, category=category, session_context=session_context, findings=findings
    ))


def resolve_citations(ids: list[str], retrieved: tuple[KnowledgeDocument, ...]) -> tuple[KnowledgeDocument, ...]:
    """Resolve only IDs that were supplied for this specific turn."""
    by_id = {document.id: document for document in retrieved}
    return tuple(by_id[doc_id] for doc_id in dict.fromkeys(ids) if doc_id in by_id)


if __name__ == "__main__":
    try:
        index = load_knowledge_base()
    except KnowledgeBaseError as error:
        raise SystemExit(str(error)) from None
    print(f"Indexed {len(index.documents)} troubleshooting entries.")
