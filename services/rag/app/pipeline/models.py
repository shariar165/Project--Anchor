"""Pydantic data models for the Anchor AI RAG pipeline stages."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


class Intent(str, Enum):
    rights_query = "rights_query"
    complaint_draft = "complaint_draft"
    case_lookup = "case_lookup"
    emergency = "emergency"
    general = "general"


class Complexity(str, Enum):
    simple = "simple"
    medium = "medium"
    hard = "hard"


class DocumentType(str, Enum):
    statute = "statute"
    rule = "rule"
    regulation = "regulation"
    circular = "circular"
    judgment = "judgment"
    commentary = "commentary"
    template = "template"
    university_policy = "university_policy"
    workflow = "workflow"


class SafetyVerdict(str, Enum):
    safe = "safe"
    emergency = "emergency"
    crisis = "crisis"
    minor = "minor"
    coercion = "coercion"
    injection = "injection"


class ChunkMetadata(BaseModel):
    chunk_id: str
    document_id: str
    document_type: DocumentType = DocumentType.statute
    jurisdiction: str = "bangladesh"
    authority_rank: int = 3
    act_name: str = ""
    chapter: str = ""
    section: str = ""
    effective_date: str = ""
    amendment_status: str = "current"
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    language: str = "en"
    tenant_scope: str = "national"
    topics: list[str] = Field(default_factory=list)


class QueryAnalysis(BaseModel):
    intent: Intent = Intent.general
    intent_confidence: float = 0.5
    lang: str = "en"
    needs_retrieval: bool = True
    complexity: Complexity = Complexity.medium
    is_workflow_query: bool = False
    historical_law: bool = False
    clarification_needed: Optional[str] = None
    entities: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float = 0.0
    metadata: ChunkMetadata
    source: str = "corpus"  # corpus | web


class VerificationResult(BaseModel):
    claim: str
    label: str  # supported | unsupported | contradicted
    evidence: str = ""


class PipelineResult(BaseModel):
    answer: str
    citations: list[dict[str, str]] = Field(default_factory=list)
    confidence: float = 0.0
    exit_ramp: bool = False
    exit_ramp_reason: str = ""
    lawyer_referral: bool = False
    verification: list[VerificationResult] = Field(default_factory=list)
    lang: str = "en"
    stage_log: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: str = "national"          # campus | national
    lang: str = "EN"                # EN | BN
    tenant_id: Optional[str] = None
    conversation_id: Optional[str] = None
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict[str, str]]
    confidence: float
    exit_ramp: bool
    lawyer_referral: bool
    lang: str
    conversation_id: str
    # Which generator produced the answer: "gemini" | "ollama" | "stub" | "".
    # degraded=True means it fell to the deterministic stub (Gemini + Ollama both
    # down) — the answer is generic boilerplate, so clients can flag it.
    engine: str = ""
    degraded: bool = False
