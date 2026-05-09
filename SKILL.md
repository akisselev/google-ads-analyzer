---
name: google-ads-analyzer
version: 0.8.3
author: Andrey Kisselev <andrey@addimarketing.com>
description: Analyzes Google Ads CSV exports — campaigns, ad groups, keywords, search terms, change history, AND Merchant Center product exports (.zip or .tsv). When a change history CSV is provided alongside a performance CSV, cross-references both to explain metric movements. Use when user provides a Google Ads report CSV, Merchant Center product download, or asks to analyze Google Ads / Merchant Center data.
allowed-tools: Read, Write, Bash, Glob
---

# CSV Analyzer for Ads

Analyzes Google Ads CSV exports and Merchant Center product downloads. Produces metrics + charts without asking questions first.

## ⚠️ CRITICAL BEHAVIOR

**DO NOT ask what the user wants. DO NOT offer options. Immediately run the analysis.**

---

## Performance Reports (ad group / keyword / search term / campaign)

**Run:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/analyze.py "<file_path>"
```

**Output:** spend, impressions, clicks, conversions, conv value, CPC, cost/conv, ROAS, CTR, conv rate — by campaign and by item. Charts saved next to the CSV:
- `top_items_by_spend.png`
- `campaign_performance.png` (4-panel)
- `status_distribution.png`
- `cost_vs_conversions.png`

---

## Change History Reports

Auto-detected when the CSV has `Old value` / `New value` columns (standard Google Ads change history download).

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/analyze.py "<file_path>"
```
Output: change count, date range, breakdown by type and campaign, timeline, recent changes list. Charts: `changes_by_type.png`, `changes_by_campaign.png`, `changes_timeline.png`.

## Using Change History Alongside a Performance Report

When the user provides **both** a performance CSV and a change history CSV, run `analyze.py` on each file separately, then present the outputs together:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/analyze.py "<performance_file>"
python3 ${CLAUDE_SKILL_DIR}/scripts/analyze.py "<change_history_file>"
```

In your narrative, cross-reference the two: tie specific changes (from the change history output) to metric movements (from the performance output). The performance data shows WHAT the metrics are; the change history shows WHAT was changed during the period.

If no change history CSV is provided, skip this step entirely — do not prompt the user for one.

---

## File Format

**Performance reports** — standard Google Ads UI export:
- Row 0: report name, Row 1: date range, Row 2+: headers + data
- Footer rows starting with `Total:` are stripped automatically

**Change history** — exported directly from Google Ads Change History tab:
- May or may not have the 2-row preamble; auto-detected by column names

## Merchant Center Product Exports

**Run** (accepts `.zip` or `.tsv` directly — auto-detected):
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/analyze.py "<file_path>"
```

**Output:** Catalogue overview (total, in-stock, on sale, variants), click performance (paid vs unpaid/free listings), top 10 by all clicks, top 10 by unpaid clicks, feed quality (GTIN coverage flagged if <80%, missing images/descriptions), by product type, by Google product category, out-of-stock list. Charts: `mc_clicks_by_product.png`, `mc_by_product_type.png`, `mc_price_distribution.png`.

**Detection:** File has `unpaid clicks`, `all clicks`, and `availability` columns (standard Merchant Center product download format).

**File format:** Tab-separated (.tsv) inside a zip. Export from Merchant Center → Products → Actions → Download.

**When writing your analysis narrative:**
- Flag GTIN gaps as a feed quality issue that can limit auction eligibility
- Note paid vs unpaid click split — high unpaid % means the free listing programme is performing well independently
- `update type: merge` means these are partial product updates, not the full catalogue
- One product with `identifier exists: no` is a feed warning; track which SKU and fix upstream

---

## Report Type Detection

The script inspects column headers and routes accordingly:
- `Old value` + `New value` → change history
- Any column containing `(Compare to)` → comparison / period-over-period report
- `Search term` → search term report
- `Keyword` → keyword report
- `Ad group` → ad group report
- Otherwise → campaign-level report

## Seasonality Context

When the account currency maps to a supported locale (CHF → Switzerland, GBP → UK, USD → US), the script automatically prints a `SEASONALITY CONTEXT` section showing holidays and gifting/shopping peaks within (or within ±14 days of) the report period. For comparison reports, it also flags when the two periods contain different holidays — which can explain metric differences.

**When writing your analysis narrative:** Reference the seasonality context explicitly. If Good Friday or a public holiday falls in the current period but not the previous, note that reduced traffic or closed businesses may have affected performance. If a gifting peak (Mother's Day, Valentine's) or shopping peak (Black Friday, Advent Sunday) is in range, reference elevated purchase intent as a contributing factor to any conversion uplift or spend shift.

To override the auto-detected locale, pass `--locale CH` (or US, GB):
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/analyze.py "<file>" --locale CH
```

## Timing Alignment (Change History only)

After the `RECENT CHANGES` section, the script prints a `TIMING ALIGNMENT` table showing each change date, the number of days remaining in the period at that point, and an impact tier:
- **High** — >60% of the period remained; the change had ample time to influence results
- **Medium** — 30–60% remaining
- **Limited** — 10–30% remaining; meaningful window but constrained
- **Minimal** — <10% remaining; performance metrics are unlikely to reflect this change yet

A note flags if a significant share of changes landed in the final third of the period.

**When writing your analysis narrative:** Use the timing alignment to contextualize effectiveness. If critical changes were made late in the period (Limited/Minimal tier), explicitly caveat that the data does not yet reflect their full impact. Distinguish between "the change didn't work" and "the change had insufficient runway to show results."

---

## Changelog

### 0.8.3 — 2026-05-09
- Path portability: replaced hard-coded `.claude/skills/google-ads-analyzer/scripts/...` paths with `${CLAUDE_SKILL_DIR}/scripts/...` so the skill resolves correctly regardless of where it's installed (Claude Code project, Claude Code personal, or Claude Cowork desktop)
- Repositioned as primarily a Claude Cowork skill (Claude Code still supported)

### 0.8.2 — 2026-05-09
- Removed internal Google Sheet dependency from Change History flow
- Change history CSV is now optional: if provided alongside a performance CSV, both are analyzed and cross-referenced; if absent, the step is skipped silently

### 0.8.1 — 2026-05-06
- Comparison report: replaced wide cramped table with 2-line per-campaign block format showing Spend/Conv/ROAS/CPA with ▲/▼ change indicators and previous-period context
- Comparison report: added `comparison_campaigns.png` — 4-panel chart (Spend, Conv, ROAS, CPA) all campaigns current vs previous in one figure

### 0.8.0 — 2026-05-06
- Added Merchant Center product export analysis (`.zip` / `.tsv`): catalogue overview, paid vs unpaid clicks, feed quality flags, by product type, by Google category, out-of-stock list; 3 charts
- Added locale-aware seasonality context (`seasonality.py`): CH/US/GB holiday calendars, gifting/shopping peaks, ±14-day lookahead, comparison period asymmetry detection
- Added change timing alignment: impact tier table (High/Medium/Limited/Minimal) showing days remaining per change date, with late-period warning note
- Added `--locale XX` CLI override; locale auto-detected from CSV currency (CHF→CH, GBP→GB, USD→US)
- Upgraded entry point to argparse (`--version`, `--locale`, `--help`)
