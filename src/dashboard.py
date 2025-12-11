"""
Dashboard and Visualization Module for Credit Risk Monitoring System
Generates interactive dashboards and visual reports.
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import BASE_DIR, DASHBOARDS_DIR
from src.database import DatabaseManager
from src.risk_analytics import RiskAnalytics
from src.early_warning import EarlyWarningSystem
from src.regulatory_reporting import RegulatoryReporting

# Try to import visualization libraries
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available, some visualizations disabled")


class DashboardGenerator:
    """
    Generates dashboard views and reports for the Credit Risk Monitoring System.
    """

    def __init__(self, db: DatabaseManager):
        """
        Initialize the dashboard generator.

        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.analytics = RiskAnalytics(db)
        self.ews = EarlyWarningSystem(db)
        self.regulatory = RegulatoryReporting(db)

        # Ensure output directory exists
        DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # DATA RETRIEVAL FOR DASHBOARDS
    # =========================================================================

    def get_risk_heatmap_data(self) -> pd.DataFrame:
        """Get data for risk heatmap (Rating x Risk Class)."""
        query = """
        SELECT
            k.kreditrating,
            k.risiko_klasse,
            COUNT(DISTINCT k.kunden_id) as anzahl_kunden,
            SUM(v.restschuld) as exposure,
            AVG(k.bonitaetsindex) as avg_bonitaet
        FROM kunden k
        LEFT JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        GROUP BY k.kreditrating, k.risiko_klasse
        """
        return self.db.execute_dataframe(query)

    def get_portfolio_quality_trend(self) -> pd.DataFrame:
        """Get NPL trend over time."""
        query = """
        SELECT
            strftime('%Y-%m', v.vertragsdatum) as monat,
            SUM(v.restschuld) as total_exposure,
            SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) as npl_exposure,
            COUNT(v.vertrag_id) as anzahl_vertraege,
            COUNT(CASE WHEN v.vertrag_status = 'ausfall' THEN 1 END) as npl_count
        FROM kredit_vertraege v
        WHERE v.vertragsdatum >= date('now', '-24 months')
        GROUP BY strftime('%Y-%m', v.vertragsdatum)
        ORDER BY monat
        """
        df = self.db.execute_dataframe(query)
        if not df.empty:
            df['npl_quote'] = df['npl_exposure'] / df['total_exposure'] * 100
        return df

    def get_limit_alerts_data(self) -> pd.DataFrame:
        """Get current limit alerts."""
        query = """
        SELECT
            limit_typ,
            limit_name,
            referenz_wert,
            limit_wert,
            aktuelle_auslastung,
            auslastung_prozent,
            ueberschreitung_flag,
            CASE
                WHEN auslastung_prozent >= 100 THEN 'ÜBERSCHRITTEN'
                WHEN auslastung_prozent >= 95 THEN 'KRITISCH'
                WHEN auslastung_prozent >= 80 THEN 'WARNUNG'
                ELSE 'OK'
            END as status
        FROM risiko_limits
        WHERE auslastung_prozent >= 70
        ORDER BY auslastung_prozent DESC
        """
        return self.db.execute_dataframe(query)

    def get_concentration_matrix_data(self) -> pd.DataFrame:
        """Get industry x region concentration data."""
        query = """
        SELECT
            k.branche,
            k.region,
            SUM(v.restschuld) as exposure,
            COUNT(DISTINCT k.kunden_id) as kunden
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        GROUP BY k.branche, k.region
        """
        return self.db.execute_dataframe(query)

    # =========================================================================
    # DASHBOARD GENERATION
    # =========================================================================

    def generate_executive_summary(self) -> Dict[str, Any]:
        """
        Generate executive summary dashboard data.

        Returns:
            Dictionary with all dashboard metrics
        """
        summary = {}

        # Portfolio Overview
        portfolio = self.analytics.get_portfolio_summary()
        summary['portfolio'] = {
            'total_exposure': portfolio.get('gesamt_exposure', 0),
            'total_customers': portfolio.get('anzahl_kunden', 0),
            'total_contracts': portfolio.get('anzahl_vertraege', 0),
            'npl_ratio': portfolio.get('npl_quote', 0),
            'avg_rate': portfolio.get('durchschnitt_zinssatz', 0) * 100
        }

        # Risk Metrics
        npl = self.analytics.calculate_npl_ratio()
        coverage = self.analytics.calculate_coverage_ratio()
        rwa = self.analytics.calculate_rwa()

        summary['risk_metrics'] = {
            'npl_volume': npl.get('npl_exposure', 0),
            'npl_ratio': npl.get('npl_ratio', 0),
            'coverage_ratio': coverage.get('coverage_ratio', 0),
            'rwa_total': rwa.get('total_rwa', 0),
            'rwa_density': rwa.get('rwa_density', 0),
            'capital_requirement': rwa.get('capital_requirement', 0)
        }

        # Concentration
        industry = self.analytics.get_industry_concentration()
        summary['concentration'] = {
            'top_industry': industry.iloc[0]['branche'] if not industry.empty else 'N/A',
            'top_industry_share': industry.iloc[0]['konzentration_prozent'] if not industry.empty else 0,
            'industries_over_limit': len(industry[industry['limit_ueberschritten'] == True]) if not industry.empty else 0
        }

        # Early Warning
        self.ews.run_all_checks()
        ews_summary = self.ews.get_alerts_summary()
        summary['alerts'] = {
            'total': ews_summary.get('total_alerts', 0),
            'critical': ews_summary.get('by_severity', {}).get('KRITISCH', 0) +
                       ews_summary.get('by_severity', {}).get('DRINGEND', 0),
            'warnings': ews_summary.get('by_severity', {}).get('WARNUNG', 0)
        }

        # Top Exposures
        top_exp = self.analytics.get_top_exposures(5)
        summary['top_exposures'] = top_exp[['name', 'gesamt_exposure', 'portfolio_anteil']].to_dict('records') if not top_exp.empty else []

        return summary

    def generate_html_dashboard(self, output_path: Path = None) -> str:
        """
        Generate HTML dashboard.

        Args:
            output_path: Optional path to save HTML file

        Returns:
            HTML string
        """
        summary = self.generate_executive_summary()

        # Get additional data
        rating_dist = self.analytics.get_rating_distribution()
        industry_conc = self.analytics.get_industry_concentration()
        limit_alerts = self.get_limit_alerts_data()
        trend_data = self.get_portfolio_quality_trend()

        html = f"""
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kreditrisiko-Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f7fa;
            color: #333;
            padding: 20px;
        }}
        .dashboard-header {{
            background: linear-gradient(135deg, #1a365d 0%, #2d4a7c 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .dashboard-header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .dashboard-header .date {{
            opacity: 0.8;
            font-size: 14px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            font-size: 16px;
            color: #666;
            margin-bottom: 15px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .metric:last-child {{
            border-bottom: none;
        }}
        .metric-label {{
            color: #666;
            font-size: 14px;
        }}
        .metric-value {{
            font-size: 18px;
            font-weight: bold;
            color: #1a365d;
        }}
        .metric-value.positive {{ color: #22c55e; }}
        .metric-value.warning {{ color: #f59e0b; }}
        .metric-value.negative {{ color: #ef4444; }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }}
        .kpi-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .kpi-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #1a365d;
        }}
        .kpi-card .label {{
            color: #666;
            font-size: 12px;
            margin-top: 5px;
        }}
        .alert-item {{
            display: flex;
            align-items: center;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 8px;
            background: #fef2f2;
        }}
        .alert-item.critical {{
            background: #fef2f2;
            border-left: 4px solid #ef4444;
        }}
        .alert-item.warning {{
            background: #fffbeb;
            border-left: 4px solid #f59e0b;
        }}
        .alert-item.info {{
            background: #eff6ff;
            border-left: 4px solid #3b82f6;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8fafc;
            font-weight: 600;
            color: #666;
        }}
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            border-radius: 4px;
        }}
        .progress-fill.green {{ background: #22c55e; }}
        .progress-fill.yellow {{ background: #f59e0b; }}
        .progress-fill.red {{ background: #ef4444; }}
        .status-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-badge.ok {{ background: #dcfce7; color: #166534; }}
        .status-badge.warning {{ background: #fef3c7; color: #92400e; }}
        .status-badge.critical {{ background: #fee2e2; color: #991b1b; }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>Kreditrisiko-Überwachungssystem</h1>
        <div class="date">Dashboard Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="value">{summary['portfolio']['total_exposure']/1e6:,.1f}M</div>
            <div class="label">Gesamt Exposure (EUR)</div>
        </div>
        <div class="kpi-card">
            <div class="value">{summary['portfolio']['total_customers']:,}</div>
            <div class="label">Aktive Kunden</div>
        </div>
        <div class="kpi-card">
            <div class="value">{summary['risk_metrics']['npl_ratio']:.2f}%</div>
            <div class="label">NPL Quote</div>
        </div>
        <div class="kpi-card">
            <div class="value">{summary['alerts']['critical']}</div>
            <div class="label">Kritische Alerts</div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Portfolio Kennzahlen</h2>
            <div class="metric">
                <span class="metric-label">Gesamtexposure</span>
                <span class="metric-value">{summary['portfolio']['total_exposure']:,.2f} EUR</span>
            </div>
            <div class="metric">
                <span class="metric-label">Anzahl Verträge</span>
                <span class="metric-value">{summary['portfolio']['total_contracts']:,}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Durchschnittlicher Zinssatz</span>
                <span class="metric-value">{summary['portfolio']['avg_rate']:.2f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">RWA Gesamt</span>
                <span class="metric-value">{summary['risk_metrics']['rwa_total']:,.2f} EUR</span>
            </div>
        </div>

        <div class="card">
            <h2>Risiko Metriken</h2>
            <div class="metric">
                <span class="metric-label">NPL Volumen</span>
                <span class="metric-value negative">{summary['risk_metrics']['npl_volume']:,.2f} EUR</span>
            </div>
            <div class="metric">
                <span class="metric-label">NPL Quote</span>
                <span class="metric-value {'negative' if summary['risk_metrics']['npl_ratio'] > 3 else 'warning' if summary['risk_metrics']['npl_ratio'] > 1 else 'positive'}">{summary['risk_metrics']['npl_ratio']:.2f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Coverage Ratio</span>
                <span class="metric-value">{summary['risk_metrics']['coverage_ratio']:.1f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">RWA Dichte</span>
                <span class="metric-value">{summary['risk_metrics']['rwa_density']:.1f}%</span>
            </div>
        </div>

        <div class="card">
            <h2>Konzentrationsrisiko</h2>
            <div class="metric">
                <span class="metric-label">Top Branche</span>
                <span class="metric-value">{summary['concentration']['top_industry']}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Anteil größte Branche</span>
                <span class="metric-value {'warning' if summary['concentration']['top_industry_share'] > 25 else ''}">{summary['concentration']['top_industry_share']:.1f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Branchen über Limit</span>
                <span class="metric-value {'negative' if summary['concentration']['industries_over_limit'] > 0 else 'positive'}">{summary['concentration']['industries_over_limit']}</span>
            </div>
        </div>

        <div class="card">
            <h2>Frühwarnsystem</h2>
            <div class="metric">
                <span class="metric-label">Gesamt Alerts</span>
                <span class="metric-value">{summary['alerts']['total']}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Kritisch/Dringend</span>
                <span class="metric-value negative">{summary['alerts']['critical']}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Warnungen</span>
                <span class="metric-value warning">{summary['alerts']['warnings']}</span>
            </div>
        </div>
    </div>

    <div class="grid">
        <div class="card" style="grid-column: span 2;">
            <h2>Top 10 Exposures</h2>
            <table>
                <thead>
                    <tr>
                        <th>Kunde</th>
                        <th>Exposure (EUR)</th>
                        <th>Portfolio %</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f"<tr><td>{exp['name'][:30]}</td><td>{exp['gesamt_exposure']:,.2f}</td><td>{exp['portfolio_anteil']:.2f}%</td></tr>" for exp in summary['top_exposures'][:10])}
                </tbody>
            </table>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Rating Verteilung</h2>
            <table>
                <thead>
                    <tr>
                        <th>Rating</th>
                        <th>Kunden</th>
                        <th>Exposure</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f"<tr><td>{row['kreditrating']}</td><td>{row['anzahl_kunden']}</td><td>{row['exposure']:,.0f}</td></tr>" for _, row in rating_dist.head(10).iterrows()) if not rating_dist.empty else '<tr><td colspan="3">Keine Daten</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>Limit Auslastung</h2>
            <table>
                <thead>
                    <tr>
                        <th>Limit</th>
                        <th>Auslastung</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f'''<tr>
                        <td>{row['limit_name'][:25]}</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill {'red' if row['auslastung_prozent'] >= 95 else 'yellow' if row['auslastung_prozent'] >= 80 else 'green'}" style="width: {min(100, row['auslastung_prozent'])}%"></div>
                            </div>
                            {row['auslastung_prozent']:.1f}%
                        </td>
                        <td><span class="status-badge {'critical' if row['status'] in ['ÜBERSCHRITTEN', 'KRITISCH'] else 'warning' if row['status'] == 'WARNUNG' else 'ok'}">{row['status']}</span></td>
                    </tr>''' for _, row in limit_alerts.head(8).iterrows()) if not limit_alerts.empty else '<tr><td colspan="3">Keine kritischen Limits</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    <div class="card" style="margin-top: 20px;">
        <h2>Branchenkonzentration</h2>
        <table>
            <thead>
                <tr>
                    <th>Branche</th>
                    <th>Exposure</th>
                    <th>Anteil</th>
                    <th>NPL Quote</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {''.join(f'''<tr>
                    <td>{row['branche']}</td>
                    <td>{row['exposure']:,.0f} EUR</td>
                    <td>
                        <div class="progress-bar">
                            <div class="progress-fill {'red' if row['konzentration_prozent'] > 30 else 'yellow' if row['konzentration_prozent'] > 20 else 'green'}" style="width: {min(100, row['konzentration_prozent']*2)}%"></div>
                        </div>
                        {row['konzentration_prozent']:.1f}%
                    </td>
                    <td>{row['npl_quote']:.2f}%</td>
                    <td><span class="status-badge {'critical' if row['limit_ueberschritten'] else 'ok'}">{'Limit!' if row['limit_ueberschritten'] else 'OK'}</span></td>
                </tr>''' for _, row in industry_conc.head(10).iterrows()) if not industry_conc.empty else '<tr><td colspan="5">Keine Daten</td></tr>'}
            </tbody>
        </table>
    </div>

    <footer style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
        Kreditrisiko-Überwachungssystem v1.0 | Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
    </footer>
</body>
</html>
"""

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"Dashboard saved to: {output_path}")

        return html

    def export_dashboard_data(self, output_path: Path) -> None:
        """
        Export all dashboard data to Excel.

        Args:
            output_path: Path for Excel file
        """
        print("Exporting dashboard data...")

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary
            summary = self.generate_executive_summary()
            summary_flat = []
            for category, metrics in summary.items():
                if isinstance(metrics, dict):
                    for key, value in metrics.items():
                        summary_flat.append({'Kategorie': category, 'Metrik': key, 'Wert': value})
                elif isinstance(metrics, list):
                    for item in metrics:
                        summary_flat.append({'Kategorie': category, 'Metrik': str(item), 'Wert': ''})

            pd.DataFrame(summary_flat).to_excel(writer, sheet_name='Executive_Summary', index=False)

            # Rating Distribution
            self.analytics.get_rating_distribution().to_excel(
                writer, sheet_name='Rating_Verteilung', index=False
            )

            # Top Exposures
            self.analytics.get_top_exposures(20).to_excel(
                writer, sheet_name='Top_Exposures', index=False
            )

            # Industry Concentration
            self.analytics.get_industry_concentration().to_excel(
                writer, sheet_name='Branchenkonzentration', index=False
            )

            # Regional Concentration
            self.analytics.get_regional_concentration().to_excel(
                writer, sheet_name='Regionalekonzentration', index=False
            )

            # Limit Alerts
            self.get_limit_alerts_data().to_excel(
                writer, sheet_name='Limit_Alerts', index=False
            )

            # Early Warning Alerts
            self.ews.run_all_checks()
            self.ews.get_alerts_dataframe().to_excel(
                writer, sheet_name='Frühwarnung_Alerts', index=False
            )

            # Delinquency
            self.analytics.get_delinquency_analysis().to_excel(
                writer, sheet_name='Verzugsanalyse', index=False
            )

            # Vintage Analysis
            self.analytics.get_vintage_analysis().to_excel(
                writer, sheet_name='Vintage_Analyse', index=False
            )

        print(f"Dashboard data exported to: {output_path}")

    def generate_charts(self, output_dir: Path = None) -> Dict[str, Path]:
        """
        Generate chart images (if matplotlib available).

        Args:
            output_dir: Directory for chart images

        Returns:
            Dictionary mapping chart names to file paths
        """
        if not MATPLOTLIB_AVAILABLE:
            print("matplotlib not available, skipping chart generation")
            return {}

        output_dir = output_dir or DASHBOARDS_DIR / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)

        charts = {}

        # Rating Distribution Pie Chart
        rating_df = self.analytics.get_rating_distribution()
        if not rating_df.empty and 'exposure' in rating_df.columns:
            fig, ax = plt.subplots(figsize=(10, 6))
            colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(rating_df)))
            ax.pie(rating_df['exposure'], labels=rating_df['kreditrating'],
                   autopct='%1.1f%%', colors=colors)
            ax.set_title('Exposure nach Rating')
            chart_path = output_dir / 'rating_distribution.png'
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts['rating_distribution'] = chart_path

        # Industry Concentration Bar Chart
        industry_df = self.analytics.get_industry_concentration()
        if not industry_df.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            industry_df_sorted = industry_df.sort_values('exposure', ascending=True).tail(10)
            bars = ax.barh(industry_df_sorted['branche'], industry_df_sorted['exposure'] / 1e6)
            ax.axvline(x=industry_df['exposure'].sum() / 1e6 * 0.3, color='r',
                      linestyle='--', label='30% Limit')
            ax.set_xlabel('Exposure (Mio EUR)')
            ax.set_title('Top 10 Branchen nach Exposure')
            ax.legend()
            chart_path = output_dir / 'industry_concentration.png'
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts['industry_concentration'] = chart_path

        # NPL Trend Line Chart
        trend_df = self.get_portfolio_quality_trend()
        if not trend_df.empty and 'npl_quote' in trend_df.columns:
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(trend_df['monat'], trend_df['npl_quote'], marker='o', linewidth=2)
            ax.fill_between(trend_df['monat'], trend_df['npl_quote'], alpha=0.3)
            ax.set_xlabel('Monat')
            ax.set_ylabel('NPL Quote (%)')
            ax.set_title('NPL Quote Entwicklung')
            plt.xticks(rotation=45)
            chart_path = output_dir / 'npl_trend.png'
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts['npl_trend'] = chart_path

        print(f"Generated {len(charts)} charts in {output_dir}")
        return charts


def generate_all_dashboards(db: DatabaseManager, output_dir: Path = None):
    """
    Generate all dashboard outputs.

    Args:
        db: DatabaseManager instance
        output_dir: Output directory (default: dashboards/)
    """
    output_dir = output_dir or DASHBOARDS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    dashboard = DashboardGenerator(db)

    # Generate HTML dashboard
    dashboard.generate_html_dashboard(output_dir / 'dashboard.html')

    # Export dashboard data
    dashboard.export_dashboard_data(output_dir / 'dashboard_data.xlsx')

    # Generate charts
    dashboard.generate_charts(output_dir / 'charts')

    print(f"\nAll dashboards generated in: {output_dir}")


if __name__ == "__main__":
    from src.database import get_demo_db

    db = get_demo_db()
    generate_all_dashboards(db)
