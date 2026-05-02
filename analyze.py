#!/usr/bin/env python3
"""
earnings-sage  –  Earnings call transcript analyser powered by Claude.

Usage
-----
  python analyze.py transcript.pdf                 # Markdown output (default)
  python analyze.py transcript.pdf --output json   # JSON output
  python analyze.py transcript.pdf --keep-file     # Keep uploaded file after analysis
  python analyze.py --list-files                   # List stored transcript files
  python analyze.py --delete-file <file_id>        # Delete a stored file
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Literal, Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

# ── Pydantic output schema ────────────────────────────────────────────────────


class FinancialMetric(BaseModel):
    metric: str = Field(description="e.g. Revenue, EPS, Gross Margin, Free Cash Flow")
    reported_value: str = Field(description="Actual reported figure including units")
    vs_estimate: Optional[str] = Field(
        None, description="Performance vs consensus, e.g. 'beat by 4.2%'"
    )
    vs_prior_year: Optional[str] = Field(
        None, description="Year-over-year change, e.g. '+18% YoY'"
    )


class GuidanceItem(BaseModel):
    period: str = Field(description="e.g. Q3 FY2025, Full Year 2025")
    metric: str = Field(description="e.g. Revenue, EPS, Operating Margin")
    guidance_range: str = Field(description="Guided range or midpoint with units")
    context: Optional[str] = Field(
        None, description="Relevant management colour or caveats"
    )


class QAPair(BaseModel):
    analyst: str = Field(description="Analyst name and firm, or 'Unknown Analyst'")
    question: str = Field(
        description="Analyst's question, summarised in 1-2 sentences"
    )
    answer: str = Field(
        description="Management's answer, summarised in 2-3 sentences"
    )
    sentiment: Literal["bullish", "neutral", "bearish", "mixed"] = Field(
        description="Implied sentiment of this exchange for the stock"
    )


class RiskFactor(BaseModel):
    category: Literal[
        "macro", "competitive", "operational", "regulatory", "financial", "other"
    ]
    description: str = Field(description="Concise description of the risk")
    severity: Literal["low", "medium", "high"]


class EarningsAnalysis(BaseModel):
    """Structured analysis of an earnings call transcript."""

    company_name: str
    ticker: str
    fiscal_period: str = Field(description="e.g. Q2 FY2025")
    call_date: Optional[str] = Field(
        None, description="YYYY-MM-DD if stated in the transcript"
    )

    # Financial performance
    key_metrics: list[FinancialMetric] = Field(
        description="Top 5-8 reported financial metrics"
    )
    guidance: list[GuidanceItem] = Field(
        description="All forward guidance items provided"
    )

    # Qualitative assessment
    management_tone: Literal[
        "very_positive", "positive", "neutral", "cautious", "negative"
    ]
    tone_explanation: str = Field(
        description="2-3 sentence rationale for the tone rating"
    )
    key_themes: list[str] = Field(
        description="Top 3-5 strategic themes or narratives from the call"
    )

    # Risk factors
    risk_factors: list[RiskFactor] = Field(
        description="Key risks explicitly mentioned by management"
    )

    # Analyst Q&A
    qa_pairs: list[QAPair] = Field(
        description="All analyst Q&A exchanges from the call"
    )

    # Summary
    bull_case: str = Field(
        description="Best-case narrative for the stock based on this call (2-3 sentences)"
    )
    bear_case: str = Field(
        description="Worst-case narrative for the stock based on this call (2-3 sentences)"
    )
    one_line_summary: str = Field(
        description="Single sentence capturing the overall takeaway from the call"
    )


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior equity research analyst with deep experience in earnings call analysis.
Extract structured, precise insights from the transcript provided.

Guidelines:
- Include units and time periods for all financial figures.
- Capture every distinct analyst Q&A exchange you can identify.
- Base tone assessment on management language, hedging, and certainty of forward-looking statements.
- Surface only risks that management explicitly acknowledges — do not infer.
- Keep bull/bear cases concise but substantive (2-3 sentences each).\
"""


# ── Core analysis function ────────────────────────────────────────────────────


def analyze(pdf_path: Path, keep_file: bool = False) -> EarningsAnalysis:
    client = anthropic.Anthropic()

    # 1. Upload the PDF via the Files API
    print(f"⬆  Uploading {pdf_path.name} …", file=sys.stderr)
    with open(pdf_path, "rb") as fh:
        uploaded = client.beta.files.upload(
            file=(pdf_path.name, fh, "application/pdf"),
        )
    file_id = uploaded.id
    print(f"   File ID : {file_id}", file=sys.stderr)

    try:
        # 2. Define the output tool from the Pydantic schema
        tool_def = {
            "name": "submit_analysis",
            "description": "Submit the completed structured earnings call analysis",
            "input_schema": EarningsAnalysis.model_json_schema(),
        }

        # 3. Analyse with Claude (adaptive thinking + Files API beta)
        print("🔍 Analysing transcript …", file=sys.stderr)
        response = client.beta.messages.create(
            model="claude-opus-4-7",
            max_tokens=8000,
            thinking={"type": "adaptive"},
            betas=["files-api-2025-04-14"],
            system=SYSTEM_PROMPT,
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "submit_analysis"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {"type": "file", "file_id": file_id},
                            "title": pdf_path.stem,
                        },
                        {
                            "type": "text",
                            "text": (
                                "Analyse this earnings call transcript thoroughly "
                                "and submit your structured analysis."
                            ),
                        },
                    ],
                }
            ],
        )

        # 4. Extract the tool_use block and validate into the Pydantic model
        tool_block = next(b for b in response.content if b.type == "tool_use")
        analysis = EarningsAnalysis.model_validate(tool_block.input)
        return analysis

    finally:
        if not keep_file:
            client.beta.files.delete(file_id)
            print(f"🗑  File {file_id} deleted.", file=sys.stderr)


# ── Markdown formatter ────────────────────────────────────────────────────────

_TONE_ICON = {
    "very_positive": "🟢🟢",
    "positive": "🟢",
    "neutral": "⚪",
    "cautious": "🟡",
    "negative": "🔴",
}
_SEV_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}
_SENT_ICON = {"bullish": "📈", "neutral": "➡️", "bearish": "📉", "mixed": "↔️"}


def to_markdown(a: EarningsAnalysis) -> str:
    lines: list[str] = []

    # Header
    lines += [
        f"# {a.company_name} ({a.ticker}) — {a.fiscal_period}",
        "",
    ]
    if a.call_date:
        lines += [f"**Call date:** {a.call_date}", ""]

    lines += [f"> {a.one_line_summary}", "", "---", ""]

    # Financial highlights
    lines += [
        "## Financial Highlights",
        "",
        "| Metric | Reported | vs Estimate | vs Prior Year |",
        "|--------|----------|-------------|---------------|",
    ]
    for m in a.key_metrics:
        lines.append(
            f"| {m.metric} | {m.reported_value} "
            f"| {m.vs_estimate or '—'} "
            f"| {m.vs_prior_year or '—'} |"
        )

    # Forward guidance
    if a.guidance:
        lines += [
            "",
            "## Forward Guidance",
            "",
            "| Period | Metric | Range | Notes |",
            "|--------|--------|-------|-------|",
        ]
        for g in a.guidance:
            lines.append(
                f"| {g.period} | {g.metric} | {g.guidance_range} "
                f"| {g.context or '—'} |"
            )

    # Management tone
    tone_icon = _TONE_ICON.get(a.management_tone, "")
    lines += [
        "",
        "## Management Tone",
        "",
        f"**Rating:** {tone_icon} `{a.management_tone}`",
        "",
        a.tone_explanation,
    ]

    # Key themes
    lines += ["", "## Key Themes", ""]
    for theme in a.key_themes:
        lines.append(f"- {theme}")

    # Risk factors
    if a.risk_factors:
        lines += ["", "## Risk Factors", ""]
        for r in a.risk_factors:
            icon = _SEV_ICON.get(r.severity, "")
            lines.append(
                f"- {icon} **[{r.category.upper()}]** {r.description}"
            )

    # Analyst Q&A
    if a.qa_pairs:
        lines += ["", "## Analyst Q&A", ""]
        for i, qa in enumerate(a.qa_pairs, 1):
            sent_icon = _SENT_ICON.get(qa.sentiment, "")
            lines += [
                f"### {i}. {qa.analyst} {sent_icon}",
                "",
                f"**Q:** {qa.question}",
                "",
                f"**A:** {qa.answer}",
                "",
            ]

    # Bull / Bear
    lines += [
        "---",
        "",
        "## Bull / Bear",
        "",
        f"**🐂 Bull case:** {a.bull_case}",
        "",
        f"**🐻 Bear case:** {a.bear_case}",
        "",
    ]

    return "\n".join(lines)


# ── File management helpers ───────────────────────────────────────────────────


def list_files() -> None:
    client = anthropic.Anthropic()
    files = list(client.beta.files.list())
    if not files:
        print("No files stored.")
        return
    print(f"{'File ID':<46} {'Filename':<40} {'Size':>12}")
    print("-" * 100)
    for f in files:
        size = f"{f.size_bytes:,} B" if hasattr(f, "size_bytes") and f.size_bytes else "—"
        print(f"{f.id:<46} {f.filename:<40} {size:>12}")


def delete_file(file_id: str) -> None:
    client = anthropic.Anthropic()
    client.beta.files.delete(file_id)
    print(f"Deleted {file_id}")


# ── CLI entry point ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse earnings call PDFs with Claude.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("pdf", nargs="?", help="Path to the earnings call PDF")
    parser.add_argument(
        "--output",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--keep-file",
        action="store_true",
        help="Keep the uploaded file in the Files API after analysis",
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="List files stored in the Files API and exit",
    )
    parser.add_argument(
        "--delete-file",
        metavar="FILE_ID",
        help="Delete a file from the Files API and exit",
    )

    args = parser.parse_args()

    if args.list_files:
        list_files()
        return

    if args.delete_file:
        delete_file(args.delete_file)
        return

    if not args.pdf:
        parser.error(
            "A PDF path is required (or use --list-files / --delete-file)"
        )

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    if pdf_path.suffix.lower() != ".pdf":
        print("Warning: file does not have a .pdf extension.", file=sys.stderr)

    analysis = analyze(pdf_path, keep_file=args.keep_file)

    if args.output == "json":
        print(json.dumps(analysis.model_dump(), indent=2))
    else:
        print(to_markdown(analysis))


if __name__ == "__main__":
    main()
