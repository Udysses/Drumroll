# Drumroll

A command-line tool that feeds earnings call PDFs to Claude and returns structured, analyst-quality output.

**One command. One PDF. Full earnings call breakdown.**

---

## What it produces

Given any earnings call transcript in PDF format, `earnings-sage` returns:

| Section | Detail |
|---|---|
| **Financial highlights** | Key metrics with beat/miss and YoY comparisons |
| **Forward guidance** | All guided periods, metrics, and ranges |
| **Management tone** | Five-point scale with rationale |
| **Key themes** | Top 3-5 strategic narratives |
| **Risk factors** | Categorised and severity-rated |
| **Analyst Q&A** | Every exchange, summarised with sentiment tags |
| **Bull / Bear case** | Concise opposing narratives |
| **One-line summary** | Single-sentence takeaway |

---

## How it works

1. The PDF is uploaded to Anthropic's **Files API** — upload once, reference by ID.
2. `claude-opus-4-7` receives the document and analyses it with **adaptive thinking** enabled.
3. A structured **tool schema** (derived from Pydantic models) forces the output into a typed, validated object — no prompt engineering for JSON required.
4. The uploaded file is deleted automatically after analysis unless `--keep-file` is passed.

```
transcript.pdf → Files API → claude-opus-4-7 (adaptive thinking) → EarningsAnalysis (Pydantic)
                                                                           ↓
                                                              Markdown report  or  JSON
```

---

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/settings/keys) (claude-opus-4-7 access required)

---

## Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/earnings-sage.git
cd earnings-sage

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

---

## Usage

### Analyse a transcript

```bash
# Markdown output (default) — great for reading in the terminal
python analyze.py Q2_2025_NVDA_earnings.pdf

# JSON output — pipe to jq, write to file, or feed another program
python analyze.py Q2_2025_NVDA_earnings.pdf --output json

# Keep the uploaded file for reuse (saves re-uploading the same PDF)
python analyze.py Q2_2025_NVDA_earnings.pdf --keep-file
```

### Manage stored files

```bash
# See all files currently stored in the Files API
python analyze.py --list-files

# Delete a specific file
python analyze.py --delete-file file_01ABCDef...
```

---

## Output example

```
# NVIDIA Corporation (NVDA) — Q2 FY2026

**Call date:** 2025-08-27

> Record data centre revenue drove a second consecutive beat, with management
> signalling continued supply tightening through H2.

---

## Financial Highlights

| Metric        | Reported   | vs Estimate | vs Prior Year |
|---------------|------------|-------------|---------------|
| Revenue       | $30.0B     | beat +4.8%  | +122% YoY     |
| Data Centre   | $26.3B     | beat +6.1%  | +154% YoY     |
| EPS (adj.)    | $0.68      | beat +8.0%  | +152% YoY     |
| Gross Margin  | 75.1%      | beat +40bps | +320bps YoY   |

## Forward Guidance

| Period   | Metric  | Range        | Notes                        |
|----------|---------|--------------|------------------------------|
| Q3 FY26  | Revenue | $32.5B ±2%   | Blackwell supply constrained |
| Q3 FY26  | GM      | ~74.6%       | NRE ramp expected            |

## Management Tone

**Rating:** 🟢🟢 `very_positive`

Management conveyed strong conviction in sustained hyperscaler demand …

## Analyst Q&A

### 1. Joseph Moore, Morgan Stanley 📈

**Q:** Can you speak to the Blackwell supply trajectory into Q4?

**A:** Jensen confirmed CoWoS packaging is the primary bottleneck …

---

## Bull / Bear

**🐂 Bull case:** …
**🐻 Bear case:** …
```

---

## Output schema

The full typed output (available with `--output json`) follows this structure:

```jsonc
{
  "company_name": "NVIDIA Corporation",
  "ticker": "NVDA",
  "fiscal_period": "Q2 FY2026",
  "call_date": "2025-08-27",
  "key_metrics": [
    {
      "metric": "Revenue",
      "reported_value": "$30.0B",
      "vs_estimate": "beat by 4.8%",
      "vs_prior_year": "+122% YoY"
    }
  ],
  "guidance": [
    {
      "period": "Q3 FY2026",
      "metric": "Revenue",
      "guidance_range": "$32.5B ±2%",
      "context": "Supply constrained by CoWoS packaging capacity"
    }
  ],
  "management_tone": "very_positive",
  "tone_explanation": "...",
  "key_themes": ["Blackwell ramp", "Sovereign AI", "..."],
  "risk_factors": [
    {
      "category": "operational",
      "description": "CoWoS packaging capacity constraining Blackwell shipments",
      "severity": "medium"
    }
  ],
  "qa_pairs": [
    {
      "analyst": "Joseph Moore, Morgan Stanley",
      "question": "...",
      "answer": "...",
      "sentiment": "bullish"
    }
  ],
  "bull_case": "...",
  "bear_case": "...",
  "one_line_summary": "..."
}
```

### Sentiment scale (Q&A)

| Value | Meaning |
|---|---|
| `bullish` | Exchange was positive for the stock — beat, acceleration, or strong demand |
| `neutral` | Factual exchange with no clear directional implication |
| `mixed` | Positive and negative elements present |
| `bearish` | Exchange revealed weakness, risk, or missed expectations |

### Management tone scale

| Value | Description |
|---|---|
| `very_positive` | Confident, raised guidance, minimal hedging |
| `positive` | Generally upbeat with modest caveats |
| `neutral` | Matter-of-fact, balanced |
| `cautious` | Noticeable hedging, risks flagged, softer language |
| `negative` | Guidance cut, significant headwinds, defensive tone |

---

## Design decisions

**Files API over base64** — PDFs are uploaded once and referenced by ID. If you're analysing a transcript across multiple questions (not this tool's use case, but easy to extend), you only pay the upload cost once.

**Tool use over prose JSON** — Forcing `tool_choice` means Claude must populate every schema field in a single, validated call. No prompt engineering for output format.

**Adaptive thinking** — `claude-opus-4-7` with `thinking: {type: "adaptive"}` lets the model reason through ambiguous sections (e.g., implied guidance from CFO remarks) before committing to structured output.

**Cleanup by default** — The uploaded file is deleted after analysis. Pass `--keep-file` to retain it if you plan to run multiple analyses on the same transcript.

---

## Project structure

```
earnings-sage/
├── analyze.py         # CLI + Claude integration + output formatting
├── requirements.txt
├── .env.example       # Copy to .env and fill in your API key
├── .gitignore
└── README.md
```

---

## Contributing

Pull requests are welcome. Open an issue first for larger changes.

```bash
pip install ruff
ruff check analyze.py
ruff format analyze.py
```

---

## License

MIT
