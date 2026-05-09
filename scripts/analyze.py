#!/usr/bin/env python3
"""
Google Ads CSV Analyzer — supports ad group, keyword, search term, campaign,
comparison (period-over-period), change history, and Merchant Center product exports.
Usage: python3 analyze.py <path_to_csv_or_zip>
"""

__version__ = '0.8.1'
__author__  = 'Andrey Kisselev <andrey@addimarketing.com>'

import sys
import os
import re
import zipfile
import tempfile
from datetime import timedelta
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['figure.dpi'] = 150
plt.rcParams['axes.facecolor'] = '#f8f8f8'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.color'] = 'white'
plt.rcParams['grid.linewidth'] = 1.0

import sys as _sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)
from seasonality import get_seasonality_context


# ── helpers ──────────────────────────────────────────────────────────────────

def clean_numeric(series):
    return (series.astype(str)
            .str.replace(',', '', regex=False)
            .str.replace('--', '0', regex=False)
            .str.strip()
            .pipe(pd.to_numeric, errors='coerce')
            .fillna(0))


def clean_percent(series):
    return (series.astype(str)
            .str.replace('%', '', regex=False)
            .str.replace('--', '0', regex=False)
            .str.strip()
            .pipe(pd.to_numeric, errors='coerce')
            .fillna(0))


def clean_change_pct(series):
    """Clean change % columns — strip %, +, commas."""
    return (series.astype(str)
            .str.replace('%', '', regex=False)
            .str.replace('+', '', regex=False)
            .str.replace(',', '', regex=False)
            .str.replace('--', '0', regex=False)
            .str.strip()
            .pipe(pd.to_numeric, errors='coerce')
            .fillna(0))


def detect_currency(df):
    if 'Currency code' in df.columns:
        code = df['Currency code'].dropna().iloc[0] if not df['Currency code'].dropna().empty else 'USD'
        symbols = {'USD': '$', 'GBP': '£', 'EUR': '€', 'CAD': 'C$', 'AUD': 'A$'}
        return symbols.get(str(code).strip(), str(code).strip() + ' ')
    return '$'


def get_currency_code(df):
    """Return raw ISO currency code from DataFrame ('CHF', 'USD', etc.)."""
    if 'Currency code' in df.columns:
        vals = df['Currency code'].dropna()
        if not vals.empty:
            return str(vals.iloc[0]).strip().upper()
    return 'USD'


def get_locale_from_currency(currency_code):
    """Map ISO currency code to supported locale (CH, US, GB) or None."""
    mapping = {'CHF': 'CH', 'GBP': 'GB', 'USD': 'US'}
    return mapping.get(str(currency_code).strip().upper(), None)


def is_merchant_center(columns):
    cols = [c.lower() for c in columns]
    return 'unpaid clicks' in cols and 'all clicks' in cols and 'availability' in cols


def is_change_history(columns):
    cols = [c.lower() for c in columns]
    return 'old value' in cols and 'new value' in cols


def is_comparison_report(columns):
    return any('(Compare to)' in c for c in columns)


def detect_report_type(columns):
    if 'Search term' in columns:
        return 'search_term', 'Search term'
    if 'Keyword' in columns:
        return 'keyword', 'Keyword'
    if 'Ad group' in columns:
        return 'ad_group', 'Ad group'
    return 'campaign', 'Campaign'


def load_csv(file_path):
    """Load a Google Ads export. Handles both 2-row header and plain CSV formats."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        first_line = f.readline().strip().strip('"')

    if first_line.count(',') < 3:
        df = pd.read_csv(file_path, skiprows=2, encoding='utf-8-sig')
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        date_range = lines[1].strip().strip('"') if len(lines) > 1 else ''
    else:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        date_range = ''

    # Remove all footer rows (Total: Campaigns, Total: Account, Total: Search, etc.)
    first_col = df.columns[0]
    df = df[~df[first_col].astype(str).str.startswith('Total:')]
    df = df.dropna(how='all')

    return df, date_range


# ── performance report analysis ───────────────────────────────────────────────

def analyze_performance(file_path, locale_override=None):
    df, date_range = load_csv(file_path)
    out_dir = os.path.dirname(os.path.abspath(file_path))

    report_type, item_col = detect_report_type(df.columns)
    currency = detect_currency(df)

    numeric_cols = ['Impr.', 'Clicks', 'Interactions', 'Cost', 'Avg. cost',
                    'Avg. CPC', 'Conversions', 'Conv. value', 'Conv. value / cost',
                    'Cost / conv.', 'Search impr. share']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = clean_numeric(df[col])

    pct_cols = ['Interaction rate', 'Conv. rate', 'CTR']
    for col in pct_cols:
        if col in df.columns:
            df[col] = clean_percent(df[col])

    status_col = next((c for c in ['Ad group status', 'Status', 'Campaign status',
                                    'Keyword status'] if c in df.columns), None)
    active = df[df[status_col].str.lower().isin(['enabled', 'active'])] if status_col else df

    cost = active['Cost'].sum() if 'Cost' in active.columns else 0
    clicks = active['Clicks'].sum() if 'Clicks' in active.columns else 0
    impr = active['Impr.'].sum() if 'Impr.' in active.columns else 0
    conv = active['Conversions'].sum() if 'Conversions' in active.columns else 0
    conv_val = active['Conv. value'].sum() if 'Conv. value' in active.columns else 0

    print('=' * 80)
    print(f'GOOGLE ADS {report_type.upper().replace("_", " ")} REPORT ANALYSIS')
    if date_range:
        print(f'Period: {date_range}')
    print('=' * 80)

    currency_code = get_currency_code(df)
    locale = locale_override or get_locale_from_currency(currency_code)
    if date_range:
        seasonality = get_seasonality_context(locale, date_range)
        if seasonality:
            print()
            print(seasonality)

    print(f'\nDATASET OVERVIEW')
    print(f'Total rows: {len(df)}')
    if status_col:
        print(f'Active: {len(active)} | Other: {len(df) - len(active)}')

    print(f'\nSPEND & VOLUME')
    print(f'Spend:         {currency}{cost:,.2f}')
    print(f'Impressions:   {impr:,.0f}')
    print(f'Clicks:        {clicks:,.0f}')
    print(f'Conversions:   {conv:,.2f}')
    print(f'Conv. Value:   {currency}{conv_val:,.2f}')

    print(f'\nEFFICIENCY METRICS')
    if clicks > 0:
        print(f'CPC:           {currency}{cost / clicks:.2f}')
    if conv > 0:
        print(f'Cost/Conv:     {currency}{cost / conv:.2f}')
    if cost > 0 and conv_val > 0:
        print(f'ROAS:          {conv_val / cost:.2f}x')
    if impr > 0:
        print(f'CTR:           {clicks / impr * 100:.2f}%')
    if clicks > 0 and conv > 0:
        print(f'Conv. Rate:    {conv / clicks * 100:.2f}%')

    if 'Campaign' in active.columns and report_type != 'campaign':
        print(f'\nBY CAMPAIGN (active)')
        camp = active.groupby('Campaign').agg(
            Cost=('Cost', 'sum'),
            Clicks=('Clicks', 'sum') if 'Clicks' in active.columns else ('Cost', 'count'),
            Conv=('Conversions', 'sum') if 'Conversions' in active.columns else ('Cost', 'count'),
            ConvVal=('Conv. value', 'sum') if 'Conv. value' in active.columns else ('Cost', 'count'),
        )
        for name, row in camp.iterrows():
            roas = row['ConvVal'] / row['Cost'] if row['Cost'] > 0 else 0
            cpc = row['Cost'] / row['Clicks'] if row['Clicks'] > 0 else 0
            cpa = row['Cost'] / row['Conv'] if row['Conv'] > 0 else 0
            print(f'\n  {name[:60]}')
            print(f'    Spend: {currency}{row["Cost"]:,.2f} | Conv: {row["Conv"]:.1f} | '
                  f'ROAS: {roas:.2f}x | CPC: {currency}{cpc:.2f} | Cost/Conv: {currency}{cpa:.2f}')

    if item_col in active.columns and 'Conversions' in active.columns:
        print(f'\nTOP 10 BY CONVERSIONS ({item_col})')
        for _, row in active.nlargest(10, 'Conversions').iterrows():
            if row['Conversions'] > 0:
                roas = row['Conv. value'] / row['Cost'] if 'Conv. value' in row and row['Cost'] > 0 else 0
                print(f'  {str(row[item_col])[:55]}')
                print(f'    Conv: {row["Conversions"]:.1f} | Spend: {currency}{row["Cost"]:,.2f} | ROAS: {roas:.2f}x')

        print(f'\nTOP 10 BY SPEND ({item_col})')
        for _, row in active.nlargest(10, 'Cost').iterrows():
            if row['Cost'] > 0:
                roas = row['Conv. value'] / row['Cost'] if 'Conv. value' in row and row['Cost'] > 0 else 0
                print(f'  {str(row[item_col])[:55]}')
                print(f'    Spend: {currency}{row["Cost"]:,.2f} | Conv: {row["Conversions"]:.1f} | ROAS: {roas:.2f}x')

    print(f'\nDATA QUALITY')
    if 'Impr.' in active.columns:
        print(f'Zero impressions: {len(active[active["Impr."] == 0])}')
    if 'Conversions' in active.columns:
        print(f'Spend with no conversions: {len(active[(active["Cost"] > 0) & (active["Conversions"] == 0)])} items')

    print(f'\nGENERATING CHARTS...')
    _make_performance_charts(active, item_col, currency, out_dir, status_col, df)

    print(f'\n{"=" * 80}')
    print('ANALYSIS COMPLETE')
    print(f'Charts saved to: {out_dir}')
    print('=' * 80)


def _make_performance_charts(active, item_col, currency, out_dir, status_col, full_df):
    if item_col in active.columns and 'Cost' in active.columns:
        fig, ax = plt.subplots(figsize=(12, 8))
        top15 = active.nlargest(15, 'Cost')
        has_conv = 'Conversions' in top15.columns
        colors = ['#2ecc71' if (has_conv and c > 0) else '#e74c3c'
                  for c in (top15['Conversions'] if has_conv else [0] * len(top15))]
        labels = [str(n)[:45] + ('…' if len(str(n)) > 45 else '') for n in top15[item_col]]
        ax.barh(range(len(top15)), top15['Cost'], color=colors)
        ax.set_yticks(range(len(top15)))
        ax.set_yticklabels(labels)
        ax.set_xlabel(f'Cost ({currency})')
        ax.set_title('Top 15 by Spend\nGreen = has conversions | Red = no conversions', fontweight='bold')
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'top_items_by_spend.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ top_items_by_spend.png')

    if 'Campaign' in active.columns and 'Cost' in active.columns:
        camp = active.groupby('Campaign').agg({
            'Cost': 'sum',
            **({'Conversions': 'sum'} if 'Conversions' in active.columns else {}),
            **({'Conv. value': 'sum'} if 'Conv. value' in active.columns else {}),
        })
        if 'Conversions' in camp.columns and 'Conv. value' in camp.columns:
            camp['ROAS'] = camp['Conv. value'] / camp['Cost'].replace(0, float('nan'))
            camp['CPA'] = camp['Cost'] / camp['Conversions'].replace(0, float('nan'))
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            for ax, (col, label, color) in zip(axes.flat, [
                ('Cost', 'Spend', '#3498db'), ('Conversions', 'Conversions', '#2ecc71'),
                ('ROAS', 'ROAS (x)', '#9b59b6'), ('CPA', f'Cost/Conv ({currency})', '#e67e22'),
            ]):
                camp[col].plot(kind='bar', ax=ax, color=color)
                ax.set_title(label, fontweight='bold')
                ax.tick_params(axis='x', rotation=45)
                ax.grid(True, alpha=0.3, axis='y')
                if col == 'ROAS':
                    ax.axhline(y=1.0, color='r', linestyle='--', linewidth=0.8)
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, 'campaign_performance.png'), bbox_inches='tight')
            plt.close()
            print('  ✓ campaign_performance.png')

    if status_col and status_col in full_df.columns:
        counts = full_df[status_col].value_counts()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(counts, labels=counts.index, autopct='%1.1f%%', startangle=90,
               textprops={'fontsize': 11, 'fontweight': 'bold'})
        ax.set_title('Status Distribution', fontweight='bold')
        plt.savefig(os.path.join(out_dir, 'status_distribution.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ status_distribution.png')

    if 'Cost' in active.columns and 'Conversions' in active.columns and 'Conv. value' in active.columns:
        plot_data = active[active['Cost'] > 0].copy()
        fig, ax = plt.subplots(figsize=(12, 8))
        scatter = ax.scatter(
            plot_data['Cost'], plot_data['Conversions'],
            s=plot_data['Conv. value'] * 2 + 20, alpha=0.6,
            c=plot_data['Conv. value'], cmap='viridis',
            edgecolors='black', linewidth=0.4
        )
        if item_col in plot_data.columns:
            for _, row in plot_data.nlargest(5, 'Conversions').iterrows():
                ax.annotate(str(row[item_col])[:25], (row['Cost'], row['Conversions']),
                            xytext=(8, 8), textcoords='offset points', fontsize=8, alpha=0.75,
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.3))
        ax.set_xlabel(f'Cost ({currency})')
        ax.set_ylabel('Conversions')
        ax.set_title('Cost vs Conversions (bubble = conv value)', fontweight='bold')
        ax.grid(True, alpha=0.3)
        plt.colorbar(scatter, ax=ax, label=f'Conv. Value ({currency})')
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'cost_vs_conversions.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ cost_vs_conversions.png')


# ── comparison report analysis ────────────────────────────────────────────────

def parse_comparison_periods(date_range_str):
    """Split 'Period A compared to Period B' into (current, previous)."""
    m = re.split(r'\s+compared to\s+', date_range_str, flags=re.IGNORECASE)
    if len(m) == 2:
        return m[0].strip(), m[1].strip()
    return date_range_str, ''


def col_curr(base):
    """Return the current-period column name (just the base name)."""
    return base


def col_prev(base):
    return f'{base} (Compare to)'


def col_chg(base):
    return f'{base} (Change)'


def col_pct(base):
    return f'{base} (Change %)'


def get_val(df_row, col):
    return df_row[col] if col in df_row.index else 0


def analyze_comparison(file_path, locale_override=None):
    df, date_range = load_csv(file_path)
    out_dir = os.path.dirname(os.path.abspath(file_path))
    currency = detect_currency(df)
    current_period, prev_period = parse_comparison_periods(date_range)

    # Detect item column (Campaign, Ad group, etc.)
    _, item_col = detect_report_type(df.columns)

    # Filter to enabled/active rows only if a status column exists
    status_col = next((c for c in ['Campaign status', 'Ad group status', 'Status',
                                    'Keyword status'] if c in df.columns), None)
    active = df[df[status_col].str.lower().isin(['enabled', 'active', 'eligible',
                                                  'eligible (limited)'])] if status_col else df

    # Clean all numeric columns — both current and compare variants
    base_metrics = ['Cost', 'Clicks', 'Conversions', 'Conv. value',
                    'Conv. value / cost', 'Cost / conv.', 'Impr.',
                    'Conv. value (by conv. time)', 'Conversions (by conv. time)']
    for base in base_metrics:
        for variant in [col_curr(base), col_prev(base), col_chg(base)]:
            if variant in df.columns:
                df[variant] = clean_numeric(df[variant])
        pct_col = col_pct(base)
        if pct_col in df.columns:
            df[pct_col] = clean_change_pct(df[pct_col])

    # Recalculate active after cleaning
    active = df[df[status_col].str.lower().isin(['enabled', 'active', 'eligible',
                                                  'eligible (limited)'])] if status_col else df

    # ── summary totals ────────────────────────────────────────────────────────

    def total(col):
        return active[col].sum() if col in active.columns else 0

    curr_cost  = total('Cost')
    prev_cost  = total('Cost (Compare to)')
    curr_conv  = total('Conversions')
    prev_conv  = total('Conversions (Compare to)')
    curr_val   = total('Conv. value')
    prev_val   = total('Conv. value (Compare to)')
    curr_clicks = total('Clicks')
    prev_clicks = total('Clicks (Compare to)')

    curr_roas = curr_val / curr_cost if curr_cost > 0 else 0
    prev_roas = prev_val / prev_cost if prev_cost > 0 else 0
    curr_cpa  = curr_cost / curr_conv if curr_conv > 0 else 0
    prev_cpa  = prev_cost / prev_conv if prev_conv > 0 else 0

    def pct_chg(curr, prev):
        if prev == 0:
            return float('inf') if curr > 0 else 0.0
        return (curr - prev) / abs(prev) * 100

    def fmt_chg(val, is_currency=False, is_x=False):
        prefix = '+' if val >= 0 else ''
        if is_currency:
            return f'{prefix}{currency}{val:,.2f}'
        if is_x:
            return f'{prefix}{val:.2f}x'
        return f'{prefix}{val:,.2f}'

    def fmt_pct(val):
        prefix = '+' if val >= 0 else ''
        if val == float('inf'):
            return 'new'
        return f'{prefix}{val:.1f}%'

    print('=' * 80)
    print('GOOGLE ADS COMPARISON REPORT')
    print(f'Current:  {current_period}')
    if prev_period:
        print(f'Previous: {prev_period}')
    print('=' * 80)

    currency_code = get_currency_code(df)
    locale = locale_override or get_locale_from_currency(currency_code)
    if date_range:
        seasonality = get_seasonality_context(locale, date_range)
        if seasonality:
            print()
            print(seasonality)

    print(f'\nDATASET')
    print(f'Campaigns: {len(df)} total, {len(active)} enabled')

    W = 14
    print(f'\n{"METRIC":<22} {"CURRENT":>{W}} {"PREVIOUS":>{W}} {"CHANGE":>{W}} {"CHANGE %":>{W}}')
    print('─' * (22 + W * 4 + 3))

    rows = [
        ('Spend',       curr_cost,  prev_cost,  curr_cost - prev_cost,   pct_chg(curr_cost, prev_cost),   True,  False),
        ('Clicks',      curr_clicks, prev_clicks, curr_clicks - prev_clicks, pct_chg(curr_clicks, prev_clicks), False, False),
        ('Conversions', curr_conv,  prev_conv,  curr_conv - prev_conv,   pct_chg(curr_conv, prev_conv),   False, False),
        ('Conv. Value', curr_val,   prev_val,   curr_val - prev_val,     pct_chg(curr_val, prev_val),     True,  False),
        ('ROAS',        curr_roas,  prev_roas,  curr_roas - prev_roas,   pct_chg(curr_roas, prev_roas),   False, True),
        ('Cost/Conv',   curr_cpa,   prev_cpa,   curr_cpa - prev_cpa,     pct_chg(curr_cpa, prev_cpa),     True,  False),
    ]
    for label, curr, prev, chg, pct, is_cur, is_x in rows:
        if is_cur:
            c_s = f'{currency}{curr:,.2f}'
            p_s = f'{currency}{prev:,.2f}'
        elif is_x:
            c_s = f'{curr:.2f}x'
            p_s = f'{prev:.2f}x'
        else:
            c_s = f'{curr:,.2f}'
            p_s = f'{prev:,.2f}'
        chg_s = fmt_chg(chg, is_cur, is_x)
        pct_s = fmt_pct(pct)
        print(f'{label:<22} {c_s:>{W}} {p_s:>{W}} {chg_s:>{W}} {pct_s:>{W}}')

    # ── per-campaign breakdown ────────────────────────────────────────────────

    if item_col in active.columns:
        print(f'\nCAMPAIGN PERFORMANCE BREAKDOWN  (sorted by spend, current period)')
        print('─' * 80)

        def _arrow(pct, lower_is_better=False):
            if pct == float('inf') or pct > 0:
                return '▼' if lower_is_better else '▲'
            if pct < 0:
                return '▲' if lower_is_better else '▼'
            return ' '

        for _, row in active.sort_values('Cost', ascending=False).iterrows():
            name = str(row[item_col])[:75]
            print(f'\n  {name}')

            spend_c = row.get('Cost', 0) or 0
            spend_p = row.get('Cost (Compare to)', 0) or 0
            spend_pct = row.get('Cost (Change %)', 0) or 0

            conv_c = row.get('Conversions', 0) or 0
            conv_p = row.get('Conversions (Compare to)', 0) or 0
            conv_pct = row.get('Conversions (Change %)', 0) or 0

            roas_c = row.get('Conv. value / cost', 0) or 0
            roas_p = row.get('Conv. value / cost (Compare to)', 0) or 0
            roas_pct = row.get('Conv. value / cost (Change %)', 0) or 0

            cpa_c = row.get('Cost / conv.', 0) or 0
            cpa_p = row.get('Cost / conv. (Compare to)', 0) or 0
            cpa_pct = row.get('Cost / conv. (Change %)', 0) or 0

            line1 = (
                f'    Spend: {currency}{spend_c:>8,.0f}  (prev {currency}{spend_p:,.0f})'
                f'  {_arrow(spend_pct)}{fmt_pct(spend_pct):>7}'
                f'    │    Conv: {conv_c:>6,.1f}  (prev {conv_p:,.1f})'
                f'  {_arrow(conv_pct)}{fmt_pct(conv_pct):>7}'
            )
            line2 = (
                f'    ROAS:  {roas_c:>7.2f}x  (prev {roas_p:.2f}x)'
                f'  {_arrow(roas_pct)}{fmt_pct(roas_pct):>7}'
                f'    │    CPA:  {currency}{cpa_c:>6,.0f}  (prev {currency}{cpa_p:,.0f})'
                f'  {_arrow(cpa_pct, lower_is_better=True)}{fmt_pct(cpa_pct):>7}'
            )
            print(line1)
            print(line2)

        print(f'\n{"─" * 80}')

    # ── biggest movers ────────────────────────────────────────────────────────

    if item_col in active.columns and 'Conversions (Change %)' in active.columns:
        movers = active[active['Cost (Compare to)'].fillna(0) > 0].copy()
        movers = movers.sort_values('Conversions (Change %)', ascending=False)

        print(f'\nBIGGEST MOVERS — Conversion change % (campaigns with prior spend)')
        print(f'  {"Campaign":<40} {"Conv Chg%":>10}  {"ROAS Chg%":>10}  {"Spend Chg%":>10}')
        print('  ' + '─' * 74)
        for _, row in movers.iterrows():
            name = str(row[item_col])[:39]
            conv_pct = row.get('Conversions (Change %)', 0) or 0
            roas_pct = row.get('Conv. value / cost (Change %)', 0) or 0
            spend_pct = row.get('Cost (Change %)', 0) or 0
            print(f'  {name:<40} {fmt_pct(conv_pct):>10}  {fmt_pct(roas_pct):>10}  {fmt_pct(spend_pct):>10}')

    print(f'\nGENERATING CHARTS...')
    _make_comparison_charts(active, item_col, currency, out_dir, current_period, prev_period)

    print(f'\n{"=" * 80}')
    print('ANALYSIS COMPLETE')
    print(f'Charts saved to: {out_dir}')
    print('=' * 80)


def _make_comparison_charts(active, item_col, currency, out_dir, current_period, prev_period):
    if item_col not in active.columns:
        return

    # ── 4-panel per-campaign breakdown chart ─────────────────────────────────
    metrics = [
        ('Cost', 'Cost (Compare to)', f'Spend ({currency})', '#3498db', False),
        ('Conversions', 'Conversions (Compare to)', 'Conversions', '#2ecc71', False),
        ('Conv. value / cost', 'Conv. value / cost (Compare to)', 'ROAS (x)', '#9b59b6', True),
        ('Cost / conv.', 'Cost / conv. (Compare to)', f'CPA ({currency})', '#e67e22', True),
    ]
    available = [(c, p, lbl, col, x_fmt) for c, p, lbl, col, x_fmt in metrics
                 if c in active.columns and p in active.columns]
    if available:
        sorted_df = active.sort_values('Cost', ascending=False) if 'Cost' in active.columns else active
        camp_names = [str(n)[:28] + ('…' if len(str(n)) > 28 else '') for n in sorted_df[item_col]]
        n = len(camp_names)
        fig, axes = plt.subplots(2, 2, figsize=(max(14, n * 1.2), 10))
        for ax, (curr_col, prev_col, label, color, _) in zip(axes.flat, available):
            curr_vals = sorted_df[curr_col].fillna(0)
            prev_vals = sorted_df[prev_col].fillna(0)
            xi = range(n)
            w = 0.35
            ax.bar([i - w/2 for i in xi], curr_vals, w,
                   label=current_period[:25] or 'Current', color=color, alpha=0.9)
            ax.bar([i + w/2 for i in xi], prev_vals, w,
                   label=prev_period[:25] or 'Previous', color='#bdc3c7', alpha=0.8)
            ax.set_xticks(list(xi))
            ax.set_xticklabels(camp_names, rotation=35, ha='right', fontsize=8)
            ax.set_title(label, fontweight='bold')
            ax.legend(fontsize=7)
            ax.grid(True, alpha=0.3, axis='y')
        plt.suptitle('Campaign Performance Breakdown: Current vs Previous', fontweight='bold', fontsize=13)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'comparison_campaigns.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ comparison_campaigns.png')

    names = [str(n)[:30] for n in active[item_col]]
    x = range(len(names))
    width = 0.35

    # 1. Spend: current vs previous
    if 'Cost' in active.columns and 'Cost (Compare to)' in active.columns:
        fig, ax = plt.subplots(figsize=(max(10, len(names) * 2), 6))
        ax.bar([i - width/2 for i in x], active['Cost'], width, label=current_period[:30], color='#3498db')
        ax.bar([i + width/2 for i in x], active['Cost (Compare to)'], width, label=prev_period[:30] or 'Previous', color='#95a5a6')
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=30, ha='right')
        ax.set_ylabel(f'Cost ({currency})')
        ax.set_title('Spend: Current vs Previous', fontweight='bold')
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'comparison_spend.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ comparison_spend.png')

    # 2. Conversions: current vs previous
    conv_curr_col = next((c for c in ['Conversions', 'Conversions (by conv. time)']
                          if c in active.columns), None)
    conv_prev_col = next((c for c in ['Conversions (Compare to)', 'Conversions (by conv. time) (Compare to)']
                          if c in active.columns), None)
    if conv_curr_col and conv_prev_col:
        fig, ax = plt.subplots(figsize=(max(10, len(names) * 2), 6))
        ax.bar([i - width/2 for i in x], active[conv_curr_col], width, label=current_period[:30], color='#2ecc71')
        ax.bar([i + width/2 for i in x], active[conv_prev_col], width, label=prev_period[:30] or 'Previous', color='#95a5a6')
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=30, ha='right')
        ax.set_ylabel('Conversions')
        ax.set_title('Conversions: Current vs Previous', fontweight='bold')
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'comparison_conversions.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ comparison_conversions.png')

    # 3. Change % bar chart (sorted by conv change %)
    if 'Conversions (Change %)' in active.columns:
        sorted_df = active.sort_values('Conversions (Change %)', ascending=True)
        sorted_names = [str(n)[:35] for n in sorted_df[item_col]]
        vals = sorted_df['Conversions (Change %)']
        colors = ['#2ecc71' if v >= 0 else '#e74c3c' for v in vals]
        fig, ax = plt.subplots(figsize=(10, max(5, len(sorted_names) * 0.6)))
        ax.barh(range(len(sorted_names)), vals, color=colors)
        ax.set_yticks(range(len(sorted_names)))
        ax.set_yticklabels(sorted_names)
        ax.axvline(x=0, color='black', linewidth=0.8)
        ax.set_xlabel('Conversion Change %')
        ax.set_title('Conversion Change % by Campaign\nGreen = improved | Red = declined', fontweight='bold')
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'comparison_conv_change.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ comparison_conv_change.png')


# ── change history analysis ───────────────────────────────────────────────────

CHANGE_TYPE_MAP = {
    'bid': 'Bid', 'budget': 'Budget', 'keyword': 'Keywords',
    'negative keyword': 'Neg Keywords', 'ad': 'Ad', 'asset': 'Assets',
    'targeting': 'Targeting', 'audience': 'Audiences', 'location': 'Targeting',
    'setting': 'Settings', 'schedule': 'Settings', 'device': 'Settings',
    'network': 'Settings', 'status': 'Structure', 'campaign': 'Structure',
    'ad group': 'Structure', 'feed': 'Product Feed', 'label': 'Structure',
    'conversion': 'Conversions', 'extension': 'Assets', 'callout': 'Assets',
    'sitelink': 'Assets', 'script': 'Scripts', 'listing group': 'Listing groups',
}


def categorize_change(change_type_str):
    if not isinstance(change_type_str, str):
        return 'Other'
    lower = change_type_str.lower()
    for key, val in CHANGE_TYPE_MAP.items():
        if key in lower:
            return val
    return 'Other'


def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def analyze_change_history(file_path, locale_override=None):
    df, _ = load_csv(file_path)
    out_dir = os.path.dirname(os.path.abspath(file_path))

    date_col    = find_col(df, ['Date', 'Change date', 'date'])
    type_col    = find_col(df, ['What changed', 'Change type', 'Type', 'Field'])
    old_col     = find_col(df, ['Old value', 'Previous value'])
    new_col     = find_col(df, ['New value', 'Updated value'])
    campaign_col = find_col(df, ['Campaign', 'Campaign name'])
    adgroup_col  = find_col(df, ['Ad group', 'Ad group name'])
    user_col    = find_col(df, ['Made by', 'User', 'Email', 'User email'])

    print('=' * 80)
    print('GOOGLE ADS CHANGE HISTORY ANALYSIS')
    print('=' * 80)

    print(f'\nDATASET OVERVIEW')
    print(f'Total changes: {len(df)}')

    if date_col:
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            valid_dates = df[date_col].dropna()
            if not valid_dates.empty:
                print(f'Date range:    {valid_dates.min().strftime("%b %-d, %Y")} → {valid_dates.max().strftime("%b %-d, %Y")}')
        except Exception:
            pass

    if user_col:
        users = df[user_col].dropna().unique()
        print(f'Made by:       {", ".join(str(u) for u in users[:5])}{"..." if len(users) > 5 else ""}')

    if type_col:
        df['_category'] = df[type_col].apply(categorize_change)
        cat_counts = df['_category'].value_counts()
        print(f'\nCHANGES BY TYPE')
        for cat, count in cat_counts.items():
            bar = '█' * min(count, 40)
            print(f'  {cat:<20} {count:>4}  {bar}')

    if campaign_col:
        camp_counts = df[campaign_col].dropna().value_counts()
        print(f'\nCHANGES BY CAMPAIGN (top 15)')
        for camp, count in camp_counts.head(15).items():
            print(f'  {str(camp)[:55]:<56} {count:>4}')

    if date_col and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        daily = df.groupby(df[date_col].dt.date).size()
        print(f'\nDAILY ACTIVITY (top 10 busiest days)')
        for day, count in daily.sort_values(ascending=False).head(10).items():
            print(f'  {str(day)}  {count:>3} changes')

    print(f'\nRECENT CHANGES (last 20)')
    recent = df.sort_values(date_col, ascending=False).head(20) if date_col else df.head(20)
    for _, row in recent.iterrows():
        parts = []
        if date_col and pd.notna(row.get(date_col)):
            try:
                parts.append(row[date_col].strftime('%-m/%-d'))
            except Exception:
                parts.append(str(row[date_col])[:10])
        if campaign_col:
            parts.append(str(row[campaign_col])[:30])
        if type_col:
            parts.append(f'[{str(row[type_col])[:30]}]')
        if old_col and new_col:
            old_v = str(row.get(old_col, ''))[:25]
            new_v = str(row.get(new_col, ''))[:25]
            parts.append(f'{old_v} → {new_v}')
        print('  ' + '  |  '.join(parts))

    # ── timing alignment ──────────────────────────────────────────────────────
    if date_col and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        valid = df[date_col].dropna()
        if not valid.empty:
            min_date = valid.min().date()
            max_date = valid.max().date()
            total_days = (max_date - min_date).days

            if total_days > 0:
                period_str = (f'{min_date.strftime("%b %-d")} – '
                              f'{max_date.strftime("%b %-d, %Y")}')
                print(f'\nTIMING ALIGNMENT  (period: {period_str}, {total_days} days total)')
                print()
                header = (f'  {"Change Date":<12} | {"Changes":>7} | '
                          f'{"Days Remaining":<18} | Impact Window')
                print(header)
                print('  ' + '─' * (len(header) - 2))

                daily_counts = df.groupby(df[date_col].dt.date).size()
                total_changes = daily_counts.sum()
                late_third_start = min_date + timedelta(days=total_days * 2 // 3)
                late_count = 0
                late_start_date = None

                for change_date, count in sorted(daily_counts.items()):
                    days_remaining = (max_date - change_date).days
                    pct_remaining = days_remaining / total_days * 100
                    if pct_remaining > 60:
                        tier, bar = 'High',    '■■■■'
                    elif pct_remaining > 30:
                        tier, bar = 'Medium',  '■■■ '
                    elif pct_remaining > 10:
                        tier, bar = 'Limited', '■   '
                    else:
                        tier, bar = 'Minimal', '·   '
                    days_str = f'{days_remaining} days ({pct_remaining:.0f}%)'
                    date_str = change_date.strftime('%b %-d')
                    print(f'  {date_str:<12} | {count:>7} | {days_str:<18} | {bar} {tier}')
                    if change_date >= late_third_start:
                        late_count += count
                        if late_start_date is None:
                            late_start_date = change_date

                if late_count > 0:
                    late_pct = late_count / total_changes * 100
                    print()
                    print(f'Note: {late_count} changes ({late_pct:.0f}%) were made in the final '
                          f'third of the period, limiting their time to show measurable impact.')
                    if late_start_date:
                        print(f'Changes from {late_start_date.strftime("%b %-d")} onward had '
                              f'limited runway; performance metrics may not yet reflect their impact.')
            else:
                print(f'\nTIMING ALIGNMENT')
                print('  Single-day change history — all changes have equivalent timing.')

    # ── seasonality context (derived from change history date range) ──────────
    if date_col and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        valid = df[date_col].dropna()
        if not valid.empty:
            min_dt = valid.min().date()
            max_dt = valid.max().date()
            ch_date_range = (f'{min_dt.strftime("%b %-d, %Y")} – '
                             f'{max_dt.strftime("%b %-d, %Y")}')
            currency_code = get_currency_code(df)
            locale = locale_override or get_locale_from_currency(currency_code)
            seasonality = get_seasonality_context(locale, ch_date_range)
            if seasonality:
                print()
                print(seasonality)

    print(f'\n{"─" * 80}')
    print('ACCOUNT CHANGES SHEET CONTEXT')
    print('Run the following to pull strategy/hypothesis/expectation from your log:')
    print(f'  node .claude/skills/google-ads-analyzer/scripts/fetch-sheet-context.cjs \\')
    print(f'       --days 90')
    print('Add --client <name> to filter by client.')
    print('─' * 80)

    print(f'\nGENERATING CHARTS...')
    _make_change_history_charts(df, type_col, campaign_col, date_col, out_dir)

    print(f'\n{"=" * 80}')
    print('ANALYSIS COMPLETE')
    print(f'Charts saved to: {out_dir}')
    print('=' * 80)


def _make_change_history_charts(df, type_col, campaign_col, date_col, out_dir):
    if type_col and '_category' in df.columns:
        cat_counts = df['_category'].value_counts()
        fig, ax = plt.subplots(figsize=(10, 6))
        cat_counts.plot(kind='bar', ax=ax, color='#3498db')
        ax.set_title('Changes by Type', fontweight='bold')
        ax.set_xlabel('Type')
        ax.set_ylabel('Count')
        ax.tick_params(axis='x', rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'changes_by_type.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ changes_by_type.png')

    if campaign_col:
        camp_counts = df[campaign_col].dropna().value_counts().head(15)
        fig, ax = plt.subplots(figsize=(12, 7))
        camp_counts[::-1].plot(kind='barh', ax=ax, color='#9b59b6')
        ax.set_title('Changes by Campaign (top 15)', fontweight='bold')
        ax.set_xlabel('Number of Changes')
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'changes_by_campaign.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ changes_by_campaign.png')

    if date_col and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        daily = df.groupby(df[date_col].dt.date).size()
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.bar(range(len(daily)), daily.values, color='#2ecc71', alpha=0.8)
        ax.set_xticks(range(len(daily)))
        ax.set_xticklabels([str(d) for d in daily.index], rotation=45, ha='right', fontsize=8)
        ax.set_title('Changes per Day', fontweight='bold')
        ax.set_ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'changes_timeline.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ changes_timeline.png')


# ── merchant center analysis ─────────────────────────────────────────────────

def _parse_mc_price(series):
    """Parse MC price column: '1250.00 USD' → (float_series, currency_str)."""
    clean = series.astype(str).str.extract(r'^([\d.]+)\s*([A-Z]{3})?', expand=True)
    prices = pd.to_numeric(clean[0], errors='coerce').fillna(0)
    codes = clean[1].dropna()
    currency_code = codes.iloc[0] if not codes.empty else 'USD'
    symbols = {'USD': '$', 'GBP': '£', 'EUR': '€', 'CHF': 'CHF ', 'CAD': 'C$', 'AUD': 'A$'}
    symbol = symbols.get(str(currency_code).strip(), str(currency_code) + ' ')
    return prices, symbol, str(currency_code).strip()


def analyze_merchant_center(file_path, locale_override=None, _out_dir=None):
    if file_path.lower().endswith('.zip'):
        out_dir = os.path.dirname(os.path.abspath(file_path))
        with zipfile.ZipFile(file_path, 'r') as z:
            tsv_names = [n for n in z.namelist() if n.lower().endswith('.tsv')]
            if not tsv_names:
                print('ERROR: No .tsv file found inside zip.')
                return
            with tempfile.TemporaryDirectory() as tmp:
                z.extract(tsv_names[0], tmp)
                actual_path = os.path.join(tmp, tsv_names[0])
                return analyze_merchant_center(actual_path, locale_override=locale_override, _out_dir=out_dir)

    df = pd.read_csv(file_path, sep='\t', dtype=str, encoding='utf-8-sig')
    out_dir = _out_dir or os.path.dirname(os.path.abspath(file_path))

    df.columns = [c.strip().lower() for c in df.columns]

    for col in ['unpaid clicks', 'all clicks']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    prices, currency, currency_code = _parse_mc_price(df['price']) if 'price' in df.columns else (pd.Series([0]*len(df)), '$', 'USD')
    df['_price'] = prices

    sale_prices = pd.Series([0.0] * len(df))
    if 'sale price' in df.columns:
        sale_prices, _, _ = _parse_mc_price(df['sale price'])
    df['_sale_price'] = sale_prices
    on_sale = (sale_prices > 0) & (sale_prices < prices)

    locale = locale_override or {'USD': 'US', 'GBP': 'GB', 'CHF': 'CH'}.get(currency_code, None)

    export_date = ''
    m = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(file_path))
    if m:
        export_date = m.group(1)

    total = len(df)
    avail_col = 'availability' if 'availability' in df.columns else None
    in_stock = (df[avail_col].str.lower() == 'in stock').sum() if avail_col else total
    out_of_stock = total - in_stock

    total_clicks = int(df['all clicks'].sum()) if 'all clicks' in df.columns else 0
    unpaid_clicks = int(df['unpaid clicks'].sum()) if 'unpaid clicks' in df.columns else 0
    paid_clicks = total_clicks - unpaid_clicks

    print('=' * 80)
    print('MERCHANT CENTER PRODUCTS REPORT')
    if export_date:
        print(f'Export date: {export_date}')
    print(f'File: {os.path.basename(file_path)}')
    print('=' * 80)

    print(f'\nCATALOGUE OVERVIEW')
    print(f'Total products:      {total}')
    print(f'In stock:            {in_stock}  ({in_stock/total*100:.0f}%)')
    if out_of_stock:
        print(f'Out of stock:        {out_of_stock}  ← ACTION NEEDED')
    print(f'On sale:             {on_sale.sum()}  ({on_sale.sum()/total*100:.0f}%)')
    if 'item group id' in df.columns:
        groups = df['item group id'].notna().sum()
        print(f'Has item group ID:   {groups} / {total}  (product variants)')

    print(f'\nCLICK PERFORMANCE')
    print(f'Total clicks:        {total_clicks:,}')
    if total_clicks > 0:
        print(f'Paid (Shopping ads): {paid_clicks:,}  ({paid_clicks/total_clicks*100:.0f}%)')
        print(f'Unpaid (free lists): {unpaid_clicks:,}  ({unpaid_clicks/total_clicks*100:.0f}%)')
    else:
        print('No click data in this export.')

    if 'all clicks' in df.columns and total_clicks > 0:
        print(f'\nTOP 10 BY ALL CLICKS')
        top = df.nlargest(10, 'all clicks')
        for _, row in top.iterrows():
            title = str(row.get('title', row.get('id', '')))[:60]
            ac = int(row['all clicks'])
            uc = int(row.get('unpaid clicks', 0))
            price_str = f'{currency}{row["_price"]:,.2f}' if row['_price'] > 0 else '–'
            print(f'  {title}')
            print(f'    Clicks: {ac} total  |  {uc} unpaid  |  Price: {price_str}')

    if 'unpaid clicks' in df.columns and unpaid_clicks > 0:
        print(f'\nTOP 10 BY UNPAID CLICKS (free listings)')
        top_u = df[df['unpaid clicks'] > 0].nlargest(10, 'unpaid clicks')
        for _, row in top_u.iterrows():
            title = str(row.get('title', row.get('id', '')))[:60]
            uc = int(row['unpaid clicks'])
            ac = int(row['all clicks'])
            print(f'  {title}')
            print(f'    Unpaid: {uc}  |  All: {ac}')

    print(f'\nFEED QUALITY')
    gtin_col = 'gtin' if 'gtin' in df.columns else None
    if gtin_col:
        gtin_filled = df[gtin_col].notna() & (df[gtin_col].str.strip() != '')
        gtin_pct = gtin_filled.sum() / total * 100
        flag = '  ← below 80% target' if gtin_pct < 80 else ''
        print(f'GTIN coverage:       {gtin_filled.sum()} / {total}  ({gtin_pct:.0f}%){flag}')
    if 'identifier exists' in df.columns:
        id_counts = df['identifier exists'].value_counts().to_dict()
        print(f'Identifier exists:   {id_counts}')
    if 'image link' in df.columns:
        missing_img = df['image link'].isna() | (df['image link'].str.strip() == '')
        if missing_img.sum():
            print(f'Missing main image:  {missing_img.sum()}  ← ACTION NEEDED')
    if 'description' in df.columns:
        missing_desc = df['description'].isna() | (df['description'].str.strip() == '')
        if missing_desc.sum():
            print(f'Missing description: {missing_desc.sum()}  ← ACTION NEEDED')
    if 'update type' in df.columns:
        ut = df['update type'].value_counts().to_dict()
        print(f'Update type:         {ut}')

    if 'product type' in df.columns:
        pt = df['product type'].dropna()
        if not pt.empty:
            print(f'\nBY PRODUCT TYPE')
            pt_counts = pt.value_counts()
            for ptype, count in pt_counts.items():
                pt_clicks = int(df.loc[df['product type'] == ptype, 'all clicks'].sum()) if 'all clicks' in df.columns else 0
                print(f'  {str(ptype)[:55]:<56} {count:>3} products  {pt_clicks:>5} clicks')

    if 'google product category' in df.columns:
        gpc = df['google product category'].dropna()
        if not gpc.empty:
            print(f'\nBY GOOGLE PRODUCT CATEGORY')
            for cat, count in gpc.value_counts().items():
                cat_clicks = int(df.loc[df['google product category'] == cat, 'all clicks'].sum()) if 'all clicks' in df.columns else 0
                print(f'  {str(cat)[:60]:<61} {count:>3} products  {cat_clicks:>5} clicks')

    if avail_col and out_of_stock > 0:
        print(f'\nOUT OF STOCK PRODUCTS')
        oos = df[df[avail_col].str.lower() != 'in stock']
        for _, row in oos.iterrows():
            print(f'  [{row.get(avail_col, "?")}]  {str(row.get("title", row.get("id", "")))[:70]}')

    print(f'\nGENERATING CHARTS...')
    _make_mc_charts(df, currency, out_dir)

    print(f'\n{"=" * 80}')
    print('ANALYSIS COMPLETE')
    print(f'Charts saved to: {out_dir}')
    print('=' * 80)


def _make_mc_charts(df, currency, out_dir):
    if 'all clicks' in df.columns and df['all clicks'].sum() > 0:
        top15 = df.nlargest(15, 'all clicks').copy()
        labels = [str(t)[:40] + ('…' if len(str(t)) > 40 else '')
                  for t in top15.get('title', top15.get('id', top15.index))]
        fig, ax = plt.subplots(figsize=(12, 8))
        width = 0.4
        x = range(len(top15))
        paid = top15['all clicks'] - top15.get('unpaid clicks', 0)
        ax.barh([i + width/2 for i in x], paid, width, label='Paid', color='#3498db')
        ax.barh([i - width/2 for i in x], top15.get('unpaid clicks', 0), width, label='Unpaid', color='#2ecc71')
        ax.set_yticks(list(x))
        ax.set_yticklabels(labels)
        ax.set_xlabel('Clicks')
        ax.set_title('Top 15 Products by Clicks\nBlue = Paid | Green = Unpaid (free listings)', fontweight='bold')
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'mc_clicks_by_product.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ mc_clicks_by_product.png')

    if 'product type' in df.columns and '_price' in df.columns and 'all clicks' in df.columns:
        pt_agg = df.groupby('product type').agg(
            count=('title', 'count'),
            clicks=('all clicks', 'sum'),
            avg_price=('_price', 'mean'),
        ).sort_values('clicks', ascending=False)
        if len(pt_agg) > 1:
            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            labels = [str(l)[:30] for l in pt_agg.index]
            pt_agg['clicks'].plot(kind='barh', ax=axes[0], color='#9b59b6')
            axes[0].set_yticklabels(labels)
            axes[0].set_title('Clicks by Product Type', fontweight='bold')
            axes[0].set_xlabel('All Clicks')
            pt_agg['count'].plot(kind='barh', ax=axes[1], color='#e67e22')
            axes[1].set_yticklabels(labels)
            axes[1].set_title('Product Count by Type', fontweight='bold')
            axes[1].set_xlabel('Products')
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, 'mc_by_product_type.png'), bbox_inches='tight')
            plt.close()
            print('  ✓ mc_by_product_type.png')

    if '_price' in df.columns and df['_price'].sum() > 0:
        prices = df[df['_price'] > 0]['_price']
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(prices, bins=min(20, len(prices)), color='#1abc9c', edgecolor='white')
        ax.set_xlabel(f'Price ({currency})')
        ax.set_ylabel('Products')
        ax.set_title('Price Distribution', fontweight='bold')
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'mc_price_distribution.png'), bbox_inches='tight')
        plt.close()
        print('  ✓ mc_price_distribution.png')


# ── entry point ───────────────────────────────────────────────────────────────

def analyze(file_path, locale_override=None):
    if file_path.lower().endswith('.zip'):
        analyze_merchant_center(file_path, locale_override=locale_override)
        return
    if file_path.lower().endswith('.tsv'):
        df = pd.read_csv(file_path, sep='\t', dtype=str, encoding='utf-8-sig', nrows=1)
        df.columns = [c.strip().lower() for c in df.columns]
        if is_merchant_center(df.columns):
            analyze_merchant_center(file_path, locale_override=locale_override)
            return
    df, _ = load_csv(file_path)
    if is_merchant_center(df.columns):
        analyze_merchant_center(file_path, locale_override=locale_override)
    elif is_change_history(df.columns):
        analyze_change_history(file_path, locale_override=locale_override)
    elif is_comparison_report(df.columns):
        analyze_comparison(file_path, locale_override=locale_override)
    else:
        analyze_performance(file_path, locale_override=locale_override)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Google Ads CSV Analyzer')
    parser.add_argument('file', nargs='?', help='Path to Google Ads CSV / Merchant Center zip export')
    parser.add_argument('--locale', metavar='XX', default=None,
                        help='Locale override (CH, US, GB). Auto-detected from currency if omitted.')
    parser.add_argument('--version', action='version',
                        version=f'google-ads-analyzer {__version__}  |  {__author__}')
    args = parser.parse_args()
    if not args.file:
        parser.print_help()
        sys.exit(1)
    analyze(args.file, locale_override=args.locale.upper() if args.locale else None)
