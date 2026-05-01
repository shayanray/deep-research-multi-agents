# 🔬 Deep Research Agent System

A MVP multi-agent research system built with **LangChain** and **LangGraph** that conducts iterative, evidence-backed deep research on any topic and produces structured reports.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Pipeline                        │
│                                                             │
│  ┌──────────┐    ┌────────────┐    ┌──────────────────┐    │
│  │ Planner  │───▶│ Researcher │◀──┐│ Conflict Analyzer│    │
│  │  Agent   │    │   Agent    │   ││                  │    │
│  └──────────┘    └─────┬──────┘   │└────────┬─────────┘    │
│                        │          │         │               │
│                   (loop while     │   ┌─────▼──────┐        │
│                   pending +       │   │Synthesizer │        │
│                   depth > 0)      │   │   Agent    │        │
│                        │          │   └─────┬──────┘        │
│                        └──────────┘         │               │
│                                       ┌─────▼──────┐        │
│                                       │   Report   │        │
│                                       │   Writer   │        │
│                                       └────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Agents

| Agent | Role |
|-------|------|
| **Planner** | Decomposes topic into themed research threads & prioritized queries |
| **Researcher** | Executes queries across Web, Wikipedia, arXiv; extracts evidence; generates follow-ups |
| **Conflict Analyzer** | Detects contradictions between sources; attempts resolution |
| **Synthesizer** | Cross-thread synthesis; identifies key findings; assesses confidence |
| **Report Writer** | Produces structured Markdown + JSON report |

### Research Tools

- **DuckDuckGo** — general web search (no API key needed)
- **Wikipedia** — encyclopedic background
- **arXiv** — academic papers (first iteration)

---

## Setup

### 1. Install dependencies

```bash
cd deep_research_agent
pip install -r requirements.txt
```

### 2. Configure API key

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY or OPENAI_API_KEY or NVIDIA_API_KEY(free)
# Default execution with ChatNVIDIA(model="meta/llama-3.1-70b-instruct", temperature=0.1)
 ```

### 3. Run

**Command line:**
```bash
python main.py "The impact of large language models on scientific research"

default parameter values: depth 2 and sources 5
```

**With options:**
```bash
python main.py "Quantum computing breakthroughs 2024" --depth 3 --sources 6
```

**Interactive mode:**
```bash
python main.py --interactive
```

---

## CLI Reference

```
usage: main.py [-h] [--depth DEPTH] [--sources SOURCES] [--output OUTPUT] [--interactive] [topic]

positional arguments:
  topic                 Research topic

options:
  --depth, -d    Research depth 1-4 (default: 2)
                   1 = Quick scan (1 iteration, ~X min)
                   2 = Standard  (2 iterations, ~2.5X min)
                   3 = Deep      (3 iterations, ~5X min)
                   4 = Exhaustive (4 iterations, ~10X min)
  --sources, -s  Max sources per query (default: 5)
  --output, -o   Output directory (default: output/)
  --interactive  Guided interactive mode
```

---

## Output

Reports are saved to `output/` as both:

- `research_<topic>_<timestamp>.md` — Human-readable Markdown
- `research_<topic>_<timestamp>.json` — Machine-readable structured data

### Report Structure

```
# Report Title
> Metadata (date, sources, confidence)

## Executive Summary
## Key Findings (numbered list)
## [Thematic Section 1]
   ### Subsection
## [Thematic Section 2]
   ...
## Conflicting Evidence
## Methodology
## Limitations & Caveats
## Sources (full list with credibility scores)
```

---

## Programmatic Usage

```python
from main import run_research

state = run_research(
    topic="Effects of sleep deprivation on cognitive performance",
    depth=2,
    max_sources=5,
    output_dir="my_reports",
)

# Access the report
report = state.report
print(report.executive_summary)
print(report.key_findings)
print(f"Confidence: {report.confidence_score:.0%}")
print(f"Sources: {report.total_sources}")

# Access raw evidence
for evidence in state.all_evidence[:5]:
    print(f"[{evidence.confidence:.2f}] {evidence.claim}")
```

---

## Design Decisions

### Multi-agent architecture
Each agent has a focused role and communicates through a shared `ResearchState` object. This makes it easy to swap out individual agents or add new ones (e.g., a specialized medical/legal agent).

### Iterative research with follow-ups
After each research iteration, the Researcher agent identifies evidence gaps and generates follow-up queries. These are added to the pipeline for the next iteration, simulating how a human researcher would pursue promising threads.

### Conflict detection
Contradictions between sources are explicitly identified and recorded — not silently reconciled. The report surfaces these conflicts so the reader can make informed judgments.

### Graceful degradation
Every tool call is wrapped in try/except. The pipeline continues even if individual searches or LLM calls fail, recording errors in `state.errors`.

### Source credibility weighting
- arXiv papers: 0.85
- Wikipedia: 0.75
- Web sources: 0.60

---

## Extending the System

**Add a new search tool:**
```python
# search_tools.py
def pubmed_search(query: str, max_results: int = 3) -> List[Source]:
    ...
```

**Add a new agent node:**
```python
# fact_checker.py
def run_fact_checker(state: ResearchState) -> ResearchState:
    ...

# pipeline.py
graph.add_node("fact_checker", fact_checker_node)
graph.add_edge("conflict_analyzer", "fact_checker")
graph.add_edge("fact_checker", "synthesizer")
```

**Swap LLM provider:**
```bash
# .env
OPENAI_API_KEY=sk-...   
```
