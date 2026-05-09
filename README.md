# Google Ads Analyzer — Claude Code Skill

**Version:** 0.8.2 · **Author:** Andrey Kisselev · andrey@addimarketing.com

A Claude Code skill that analyzes Google Ads and Merchant Center CSV exports. Drop in a report, get metrics, charts, and a written analysis — no setup, no prompting required.

---

## What it analyzes

| Report type | How to export |
|---|---|
| Campaign / ad group / keyword / search term | Google Ads UI → Reports → download CSV |
| Change history | Google Ads → Change History → download CSV |
| Period-over-period comparison | Google Ads UI → add comparison date range → download CSV |
| Merchant Center products | Merchant Center → Products → Actions → Download (.zip or .tsv) |

---

## What you get

**Performance reports** — spend, impressions, clicks, conversions, conv value, CPC, cost/conv, ROAS, CTR, conv rate — broken down by campaign and by item. Four charts saved next to your CSV: top items by spend, campaign performance (4-panel), status distribution, cost vs conversions.

**Change history** — change count, date range, breakdown by type and campaign, timing alignment table (how much of the period remained after each change — High / Medium / Limited / Minimal impact window).

**Comparison reports** — current vs previous period with ▲/▼ indicators per campaign for Spend, Conv, ROAS, CPA. One 4-panel chart comparing all campaigns side by side.

**Merchant Center** — catalogue overview (total, in-stock, on sale, variants), paid vs unpaid click split, top 10 by clicks, feed quality flags (GTIN coverage, missing images/descriptions), by product type and Google category, out-of-stock list. Three charts.

**Seasonality context** — for CH, US, and GB accounts, the script automatically surfaces holidays and gifting/shopping peaks within the report period (or within ±14 days).

---

## Requirements

- [Claude Code](https://claude.ai/code) (CLI)
- Python 3.9+
- Python packages: `pip install pandas matplotlib`

---

## Installation

1. Copy the `google-ads-analyzer` folder into your Claude Code skills directory:

```
your-project/
  .claude/
    skills/
      google-ads-analyzer/   ← paste here
        SKILL.md
        scripts/
          analyze.py
          seasonality.py
```

2. That's it. Claude Code picks up the skill automatically.

---

## Usage

Once installed, just hand Claude a CSV or zip file:

> "Analyze this" + attach your Google Ads CSV

Claude runs the analysis immediately without asking follow-up questions.

**Locale override** (if auto-detection is wrong):

When chatting with Claude, you can mention: *"Use locale CH"* — or the script accepts `--locale CH` / `--locale US` / `--locale GB` directly.

---

## Changelog

### 0.8.2 — 2026-05-09
- Removed internal Google Sheet dependency from Change History flow
- Change history CSV is now optional: if provided alongside a performance CSV, both are analyzed and cross-referenced; if absent, the step is skipped silently

### 0.8.1 — 2026-05-06
- Comparison report: replaced wide cramped table with 2-line per-campaign block format with ▲/▼ change indicators
- Comparison report: added `comparison_campaigns.png` — 4-panel chart (Spend, Conv, ROAS, CPA)

### 0.8.0 — 2026-05-06
- Added Merchant Center product export analysis (`.zip` / `.tsv`)
- Added locale-aware seasonality context (CH/US/GB)
- Added change timing alignment table (High / Medium / Limited / Minimal)
- Added `--locale XX` CLI override; auto-detected from CSV currency

---

## Questions or feedback

andrey@addimarketing.com
