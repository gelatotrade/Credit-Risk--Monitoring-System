#!/usr/bin/env python3
"""
Generate documentation visualizations for the Credit Risk Monitoring System.
Creates example charts for the four main dashboard views.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from pathlib import Path

# Set style for consistent look
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.labelcolor'] = '#333333'
plt.rcParams['xtick.color'] = '#333333'
plt.rcParams['ytick.color'] = '#333333'

OUTPUT_DIR = Path(__file__).parent / 'docs' / 'images'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_risk_heatmap():
    """Generate Risk Heatmap: Customer distribution by rating and risk class."""

    # Define ratings and risk classes
    ratings = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'CC', 'C']
    risk_classes = ['niedrig', 'mittel', 'erhöht', 'hoch', 'sehr_hoch']

    # Create sample data (customer counts)
    np.random.seed(42)
    data = np.zeros((len(risk_classes), len(ratings)))

    # Realistic distribution: low risk ratings have low risk classes
    for i, rating in enumerate(ratings):
        for j, risk_class in enumerate(risk_classes):
            # Higher probability for matching risk levels
            if i <= 2:  # AAA, AA, A
                if j <= 1:
                    data[j, i] = np.random.randint(30, 80)
                else:
                    data[j, i] = np.random.randint(0, 10)
            elif i <= 4:  # BBB, BB
                if j in [1, 2]:
                    data[j, i] = np.random.randint(40, 100)
                else:
                    data[j, i] = np.random.randint(5, 25)
            else:  # B, CCC, CC, C
                if j >= 2:
                    data[j, i] = np.random.randint(20, 60)
                else:
                    data[j, i] = np.random.randint(0, 8)

    fig, ax = plt.subplots(figsize=(14, 8))

    # Create heatmap with custom colormap (green to red)
    cmap = plt.cm.RdYlGn_r
    im = ax.imshow(data, cmap=cmap, aspect='auto')

    # Set ticks
    ax.set_xticks(np.arange(len(ratings)))
    ax.set_yticks(np.arange(len(risk_classes)))
    ax.set_xticklabels(ratings, fontsize=12, fontweight='bold')
    ax.set_yticklabels([rc.replace('_', ' ').title() for rc in risk_classes], fontsize=11)

    # Rotate x labels
    plt.setp(ax.get_xticklabels(), rotation=0, ha="center")

    # Add text annotations
    for i in range(len(risk_classes)):
        for j in range(len(ratings)):
            value = int(data[i, j])
            text_color = 'white' if data[i, j] > 40 else 'black'
            ax.text(j, i, value, ha="center", va="center", color=text_color,
                   fontsize=11, fontweight='bold')

    # Labels and title
    ax.set_xlabel('Kreditrating', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_ylabel('Risikoklasse', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_title('Risk Heatmap: Kundenverteilung nach Rating und Risikoklasse',
                 fontsize=16, fontweight='bold', pad=20)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Anzahl Kunden', fontsize=12, labelpad=10)

    # Add grid lines
    ax.set_xticks(np.arange(-.5, len(ratings), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(risk_classes), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle='-', linewidth=2)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'risk_heatmap.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print("Generated: risk_heatmap.png")


def generate_portfolio_quality_trend():
    """Generate Portfolio Quality Trend: NPL development over time."""

    # Generate 24 months of data
    months = pd.date_range(start='2023-01-01', periods=24, freq='M')
    month_labels = [m.strftime('%b %Y') for m in months]

    np.random.seed(42)

    # NPL ratio with slight upward trend and seasonal variation
    base_npl = 2.5
    trend = np.linspace(0, 0.8, 24)
    seasonal = 0.3 * np.sin(np.linspace(0, 4*np.pi, 24))
    noise = np.random.normal(0, 0.15, 24)
    npl_ratio = base_npl + trend + seasonal + noise
    npl_ratio = np.clip(npl_ratio, 1.5, 5.0)

    # NPL volume (in millions)
    total_exposure = 850  # Million EUR
    npl_volume = (npl_ratio / 100) * total_exposure

    # Create figure with two y-axes
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Plot NPL ratio (left axis)
    color1 = '#1e40af'
    ax1.fill_between(range(24), npl_ratio, alpha=0.3, color=color1)
    line1, = ax1.plot(range(24), npl_ratio, color=color1, linewidth=3,
                      marker='o', markersize=6, label='NPL Quote (%)')
    ax1.set_xlabel('Monat', fontsize=13, fontweight='bold')
    ax1.set_ylabel('NPL Quote (%)', color=color1, fontsize=13, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_ylim(0, 6)

    # Add threshold line
    ax1.axhline(y=3.0, color='#dc2626', linestyle='--', linewidth=2,
                label='Warnschwelle (3%)')

    # Create second y-axis for volume
    ax2 = ax1.twinx()
    color2 = '#059669'
    line2, = ax2.plot(range(24), npl_volume, color=color2, linewidth=2.5,
                      linestyle='--', marker='s', markersize=5, label='NPL Volumen (Mio EUR)')
    ax2.set_ylabel('NPL Volumen (Mio EUR)', color=color2, fontsize=13, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim(0, 50)

    # X-axis labels
    ax1.set_xticks(range(0, 24, 2))
    ax1.set_xticklabels([month_labels[i] for i in range(0, 24, 2)], rotation=45, ha='right')

    # Title
    ax1.set_title('Portfolio Quality Trend: NPL-Entwicklung über Zeit',
                  fontsize=16, fontweight='bold', pad=20)

    # Combined legend
    lines = [line1, line2]
    labels = [l.get_label() for l in lines]
    lines.append(plt.Line2D([0], [0], color='#dc2626', linestyle='--', linewidth=2))
    labels.append('Warnschwelle (3%)')
    ax1.legend(lines, labels, loc='upper left', fontsize=11, framealpha=0.95)

    # Grid
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(-0.5, 23.5)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'portfolio_quality_trend.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print("Generated: portfolio_quality_trend.png")


def generate_limit_alerts():
    """Generate Limit Alerts: Current limit utilization warnings."""

    # Sample limit data
    limits = [
        ('Einzelkunde: TechCorp GmbH', 98.5, 'ÜBERSCHRITTEN'),
        ('Branche: Automobilbau', 94.2, 'KRITISCH'),
        ('Region: Bayern', 88.7, 'WARNUNG'),
        ('Einzelkunde: Industrial AG', 85.3, 'WARNUNG'),
        ('Branche: Immobilien', 82.1, 'WARNUNG'),
        ('Einzelkunde: FinanzService', 79.8, 'WARNUNG'),
        ('Region: Nordrhein-Westfalen', 76.4, 'OK'),
        ('Branche: Baugewerbe', 72.3, 'OK'),
    ]

    fig, ax = plt.subplots(figsize=(14, 8))

    names = [l[0] for l in limits]
    values = [l[1] for l in limits]
    statuses = [l[2] for l in limits]

    # Color mapping
    colors = []
    for status in statuses:
        if status == 'ÜBERSCHRITTEN':
            colors.append('#7f1d1d')  # Dark red
        elif status == 'KRITISCH':
            colors.append('#dc2626')  # Red
        elif status == 'WARNUNG':
            colors.append('#f59e0b')  # Orange
        else:
            colors.append('#22c55e')  # Green

    # Create horizontal bars
    y_pos = np.arange(len(names))
    bars = ax.barh(y_pos, values, color=colors, height=0.7, edgecolor='white', linewidth=1)

    # Add threshold lines
    ax.axvline(x=80, color='#f59e0b', linestyle='--', linewidth=2, label='Warnschwelle (80%)')
    ax.axvline(x=95, color='#dc2626', linestyle='--', linewidth=2, label='Kritisch (95%)')
    ax.axvline(x=100, color='#7f1d1d', linestyle='-', linewidth=3, label='Limit (100%)')

    # Add value labels
    for i, (bar, value, status) in enumerate(zip(bars, values, statuses)):
        ax.text(value + 1, i, f'{value:.1f}%', va='center', ha='left',
               fontsize=11, fontweight='bold')
        # Add status badge
        badge_color = colors[i]
        ax.text(105, i, status, va='center', ha='left', fontsize=10,
               fontweight='bold', color=badge_color,
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor=badge_color, linewidth=2))

    # Configure axes
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel('Auslastung (%)', fontsize=13, fontweight='bold')
    ax.set_xlim(0, 130)
    ax.set_title('Limit Alerts: Aktuelle Limitauslastung',
                 fontsize=16, fontweight='bold', pad=20)

    ax.legend(loc='lower right', fontsize=10, framealpha=0.95)
    ax.grid(axis='x', alpha=0.3)

    # Invert y-axis so highest values are at top
    ax.invert_yaxis()

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'limit_alerts.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print("Generated: limit_alerts.png")


def generate_concentration_matrix():
    """Generate Concentration Matrix: Industry × Region exposure matrix."""

    # Top industries and regions
    industries = ['Automobilbau', 'Maschinenbau', 'Immobilien', 'IT/Technologie',
                  'Handel', 'Baugewerbe', 'Energie']
    regions = ['Bayern', 'NRW', 'Baden-W.', 'Hessen', 'Niedersachsen', 'Berlin']

    np.random.seed(42)

    # Create exposure matrix (in millions EUR)
    data = np.random.exponential(scale=15, size=(len(industries), len(regions)))

    # Make some cells larger (concentration hotspots)
    data[0, 0] = 85  # Auto in Bayern
    data[1, 0] = 72  # Maschinenbau in Bayern
    data[2, 1] = 68  # Immobilien in NRW
    data[3, 5] = 55  # IT in Berlin
    data[4, 1] = 48  # Handel in NRW

    # Calculate totals
    row_totals = data.sum(axis=1)
    col_totals = data.sum(axis=0)
    grand_total = data.sum()

    # Normalize for color intensity
    data_normalized = data / data.max()

    fig, ax = plt.subplots(figsize=(14, 10))

    # Custom colormap
    cmap = plt.cm.YlOrRd
    im = ax.imshow(data_normalized, cmap=cmap, aspect='auto')

    # Set ticks
    ax.set_xticks(np.arange(len(regions)))
    ax.set_yticks(np.arange(len(industries)))
    ax.set_xticklabels(regions, fontsize=12, fontweight='bold')
    ax.set_yticklabels(industries, fontsize=12)

    # Add text annotations with exposure values
    for i in range(len(industries)):
        for j in range(len(regions)):
            value = data[i, j]
            text_color = 'white' if data_normalized[i, j] > 0.5 else 'black'
            ax.text(j, i, f'{value:.1f}M', ha="center", va="center",
                   color=text_color, fontsize=10, fontweight='bold')

    # Add row totals (right side)
    for i, total in enumerate(row_totals):
        ax.text(len(regions) + 0.3, i, f'{total:.1f}M', ha="left", va="center",
               fontsize=11, fontweight='bold', color='#1e40af')

    # Add column totals (bottom)
    for j, total in enumerate(col_totals):
        ax.text(j, len(industries) + 0.3, f'{total:.1f}M', ha="center", va="top",
               fontsize=11, fontweight='bold', color='#1e40af')

    # Labels and title
    ax.set_xlabel('Region', fontsize=14, fontweight='bold', labelpad=25)
    ax.set_ylabel('Branche', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_title('Concentration Matrix: Branchen × Regionen Exposure (Mio EUR)',
                 fontsize=16, fontweight='bold', pad=20)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.7, pad=0.15)
    cbar.set_label('Relative Konzentration', fontsize=12, labelpad=10)

    # Add grid
    ax.set_xticks(np.arange(-.5, len(regions), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(industries), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle='-', linewidth=2)

    # Add annotation for row/column totals
    ax.text(len(regions) + 0.3, -0.7, 'Summe', ha="left", va="bottom",
           fontsize=11, fontweight='bold', color='#1e40af', style='italic')
    ax.text(-0.7, len(industries) + 0.3, 'Summe', ha="right", va="top",
           fontsize=11, fontweight='bold', color='#1e40af', style='italic', rotation=90)

    # Grand total
    ax.text(len(regions) + 0.3, len(industries) + 0.3, f'Gesamt:\n{grand_total:.1f}M',
           ha="left", va="top", fontsize=11, fontweight='bold', color='#7c3aed')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'concentration_matrix.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print("Generated: concentration_matrix.png")


def generate_system_overview():
    """Generate a system architecture overview diagram."""

    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis('off')

    # Title
    ax.text(8, 11.5, 'Kreditrisiko-Überwachungssystem', fontsize=20,
            fontweight='bold', ha='center', color='#1e3a5f')
    ax.text(8, 11, 'Systemarchitektur & Dashboard-Übersicht', fontsize=14,
            ha='center', color='#666666', style='italic')

    # Define boxes
    box_style = dict(boxstyle='round,pad=0.5', facecolor='white',
                    edgecolor='#1e3a5f', linewidth=2)
    header_style = dict(fontsize=12, fontweight='bold', color='#1e3a5f')

    # Data Sources (left column)
    ax.add_patch(plt.Rectangle((0.5, 6), 3.5, 4, fill=True,
                facecolor='#e0f2fe', edgecolor='#0284c7', linewidth=2,
                linestyle='-', alpha=0.5, zorder=1))
    ax.text(2.25, 9.7, 'DATENQUELLEN', fontsize=11, fontweight='bold',
            ha='center', color='#0284c7')

    sources = ['Kunden', 'Verträge', 'Zahlungen', 'Wirtschaftsdaten']
    for i, src in enumerate(sources):
        ax.text(2.25, 9.0 - i*0.8, f'   {src}', fontsize=10, ha='center',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor='#0284c7', linewidth=1))

    # Analytics Core (center)
    ax.add_patch(plt.Rectangle((5, 4), 6, 6.5, fill=True,
                facecolor='#fef3c7', edgecolor='#d97706', linewidth=3,
                linestyle='-', alpha=0.5, zorder=1))
    ax.text(8, 10.2, 'ANALYTICS ENGINE', fontsize=12, fontweight='bold',
            ha='center', color='#d97706')

    modules = [
        ('Risk Analytics', '#22c55e'),
        ('Early Warning', '#f59e0b'),
        ('Stress Testing', '#ef4444'),
        ('IFRS 9 / Basel III', '#8b5cf6'),
    ]
    for i, (mod, color) in enumerate(modules):
        ax.text(8, 9.2 - i*1.1, mod, fontsize=11, ha='center', fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.4', facecolor=color,
                        edgecolor='white', linewidth=2, alpha=0.8),
               color='white')

    # Dashboard Views (right column)
    ax.add_patch(plt.Rectangle((12, 4), 3.5, 6.5, fill=True,
                facecolor='#dcfce7', edgecolor='#16a34a', linewidth=2,
                linestyle='-', alpha=0.5, zorder=1))
    ax.text(13.75, 10.2, 'DASHBOARD VIEWS', fontsize=11, fontweight='bold',
            ha='center', color='#16a34a')

    views = [
        'Risk Heatmap',
        'Portfolio Trend',
        'Limit Alerts',
        'Concentration Matrix'
    ]
    for i, view in enumerate(views):
        ax.text(13.75, 9.2 - i*1.1, view, fontsize=10, ha='center',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor='#16a34a', linewidth=1))

    # Arrows
    arrow_style = dict(arrowstyle='->', color='#64748b', lw=2)
    ax.annotate('', xy=(5, 7.5), xytext=(4, 7.5), arrowprops=arrow_style)
    ax.annotate('', xy=(12, 7.5), xytext=(11, 7.5), arrowprops=arrow_style)

    # Output section (bottom)
    ax.add_patch(plt.Rectangle((3, 0.5), 10, 2.5, fill=True,
                facecolor='#f3e8ff', edgecolor='#9333ea', linewidth=2,
                linestyle='-', alpha=0.5, zorder=1))
    ax.text(8, 2.7, 'OUTPUT & REPORTING', fontsize=11, fontweight='bold',
            ha='center', color='#9333ea')

    outputs = ['HTML Dashboard', 'Excel Reports', 'Chart Images', 'Regulatory Reports']
    for i, out in enumerate(outputs):
        ax.text(4.2 + i*2.7, 1.5, out, fontsize=9, ha='center',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor='#9333ea', linewidth=1))

    # Arrow from center to bottom
    ax.annotate('', xy=(8, 3), xytext=(8, 4), arrowprops=arrow_style)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'system_overview.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print("Generated: system_overview.png")


if __name__ == "__main__":
    print("Generating documentation visualizations...")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    generate_system_overview()
    generate_risk_heatmap()
    generate_portfolio_quality_trend()
    generate_limit_alerts()
    generate_concentration_matrix()

    print()
    print(f"All visualizations generated in: {OUTPUT_DIR}")
