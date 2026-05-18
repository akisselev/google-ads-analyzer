# Google Ads Analyzer

A Claude skill that analyzes Google Ads CSV exports. Drop in a report, get metrics, charts, and a written analysis. No setup, no prompting required.

Works in **Claude Cowork** (desktop app) and **Claude Code** (CLI) — same skill format.

## Download

Get the latest release as a ZIP:

**→ [Latest release](https://github.com/akisselev/google-ads-analyzer/releases/latest)**

## Install

### Claude Cowork
1. Download `google-ads-analyzer-vX.Y.Z.zip` from the release page.
2. In Claude Cowork: **Customize → + → Skills tab → upload the ZIP.**

### Claude Code
1. Unzip the archive.
2. Move the `google-ads-analyzer/` folder into your project's `.claude/skills/` directory.

Full usage details, requirements, and changelog are inside the ZIP (`README.md` + `SKILL.md`).

## Requirements

- Python 3.9+ on the machine where Claude runs the skill
- `pip install pandas matplotlib`

## Questions

andrey@addimarketing.com
