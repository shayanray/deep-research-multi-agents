"""
Pydantic schemas for the Deep Research Agent System.
All data structures used across agents are defined here.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


# ---------------------------------------------------------------------------
# Source & Evidence primitives
# ---------------------------------------------------------------------------

class Source(BaseModel):
    """A single retrieved source."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    url: str = ""
    title: str = ""
    content: str = ""
    source_type: Literal["web", "wikipedia", "arxiv", "news", "manual"] = "web"
    credibility_score: float = Field(0.5, ge=0.0, le=1.0,
                                     description="0-1 credibility estimate")
    retrieved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """A piece of evidence extracted from one or more sources."""
    claim: str
    supporting_sources: List[str] = Field(default_factory=list,
                                          description="Source IDs that back this claim")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    conflicting_sources: List[str] = Field(default_factory=list,
                                           description="Source IDs that contradict this claim")


# ---------------------------------------------------------------------------
# Research thread / sub-query structures
# ---------------------------------------------------------------------------

class ResearchQuery(BaseModel):
    """A single research sub-question to investigate."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str
    rationale: str = ""
    priority: int = Field(1, ge=1, le=5, description="1=highest priority")
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    depth: int = Field(0, description="Nesting depth for follow-up queries")


class ResearchThread(BaseModel):
    """A cluster of related queries forming one research thread."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    theme: str
    queries: List[ResearchQuery] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    summary: str = ""
    status: Literal["pending", "in_progress", "completed"] = "pending"
    iteration: int = 0


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

class ConflictRecord(BaseModel):
    """Represents a detected contradiction between sources."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str
    claim_a: str
    source_ids_a: List[str]
    claim_b: str
    source_ids_b: List[str]
    resolution: str = ""
    resolution_confidence: float = 0.0
    resolved: bool = False


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

class ReportSection(BaseModel):
    """One section of the final research report."""
    title: str
    content: str
    evidence_ids: List[str] = Field(default_factory=list)
    subsections: List["ReportSection"] = Field(default_factory=list)


ReportSection.model_rebuild()


class ResearchReport(BaseModel):
    """The final structured research report."""
    title: str
    topic: str
    executive_summary: str = ""
    sections: List[ReportSection] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    conflicts_identified: List[ConflictRecord] = Field(default_factory=list)
    methodology: str = ""
    limitations: str = ""
    sources: List[Source] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    total_sources: int = 0
    research_iterations: int = 0


# ---------------------------------------------------------------------------
# Overall agent state (LangGraph state dict)
# ---------------------------------------------------------------------------

class ResearchState(BaseModel):
    """Full mutable state passed between LangGraph nodes."""
    # Core inputs
    topic: str
    research_depth: int = Field(2, ge=1, le=4,
                                description="Max iterations of follow-up research")
    max_sources_per_query: int = 5

    # Planning
    research_plan: str = ""
    threads: List[ResearchThread] = Field(default_factory=list)
    all_queries: List[ResearchQuery] = Field(default_factory=list)

    # Gathered knowledge
    all_sources: Dict[str, Source] = Field(default_factory=dict,
                                           description="Keyed by source id")
    all_evidence: List[Evidence] = Field(default_factory=list)
    conflicts: List[ConflictRecord] = Field(default_factory=list)

    # Synthesis
    synthesis_notes: str = ""
    key_findings: List[str] = Field(default_factory=list)

    # Report
    report: Optional[ResearchReport] = None

    # Control flow
    current_iteration: int = 0
    iteration_summaries: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    status: Literal["planning", "researching", "analyzing",
                    "synthesizing", "writing", "complete", "error"] = "planning"

    # Metadata
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        arbitrary_types_allowed = True
