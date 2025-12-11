#!/usr/bin/env python3
"""
Kreditrisiko-Überwachungssystem (Credit Risk Monitoring System)
Main Application Entry Point

This system provides comprehensive credit risk monitoring with:
- Portfolio analytics and concentration risk analysis
- Early warning system for potential defaults
- Stress testing scenarios
- IFRS 9 ECL calculations
- Basel III/IV capital requirements
- Dashboard generation and reporting
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import (
    BASE_DIR, DATA_DIR, DEMO_DATA_DIR, REAL_DATA_DIR,
    DASHBOARDS_DIR, REPORTS_DIR, EXCEL_DIR
)


def setup_demo_system():
    """Initialize the system with demo data."""
    print("=" * 70)
    print("KREDITRISIKO-ÜBERWACHUNGSSYSTEM - DEMO SETUP")
    print("=" * 70)

    from src.database import init_demo_database
    from src.demo_data_generator import populate_demo_database

    print("\n1. Initializing demo database...")
    db = init_demo_database(force_recreate=True)

    print("\n2. Populating with demo data...")
    populate_demo_database(db)

    print("\n3. Generating Excel templates...")
    from src.excel_handler import ExcelTemplateGenerator
    template_gen = ExcelTemplateGenerator()
    template_gen.generate_all_templates()

    print("\nDemo system setup complete!")
    print(f"Database location: {db.db_path}")
    return db


def setup_real_system():
    """Initialize the system for real data."""
    print("=" * 70)
    print("KREDITRISIKO-ÜBERWACHUNGSSYSTEM - REAL DATA SETUP")
    print("=" * 70)

    from src.database import init_real_database

    print("\n1. Initializing production database...")
    db = init_real_database(force_recreate=False)

    print("\n2. Generating Excel templates for data import...")
    from src.excel_handler import ExcelTemplateGenerator
    template_gen = ExcelTemplateGenerator()
    template_gen.generate_all_templates()

    print("\n3. Fetching economic data from web sources...")
    from src.economic_data_fetcher import populate_real_economic_data
    populate_real_economic_data(db)

    print("\nReal data system setup complete!")
    print(f"Database location: {db.db_path}")
    print(f"\nImport your data using the Excel templates in: {EXCEL_DIR}")
    return db


def run_analysis(mode: str = 'demo'):
    """Run comprehensive risk analysis."""
    print("=" * 70)
    print("KREDITRISIKO-ANALYSE")
    print("=" * 70)

    from src.database import get_demo_db, get_real_db
    from src.risk_analytics import RiskAnalytics, run_portfolio_analysis

    db = get_demo_db() if mode == 'demo' else get_real_db()
    analytics = RiskAnalytics(db)

    # Portfolio Summary
    print("\n" + "-" * 50)
    print("PORTFOLIO ÜBERSICHT")
    print("-" * 50)
    summary = analytics.get_portfolio_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:,.2f}")
        else:
            print(f"  {key}: {value:,}")

    # Rating Distribution
    print("\n" + "-" * 50)
    print("RATING VERTEILUNG")
    print("-" * 50)
    rating_df = analytics.get_rating_distribution()
    if not rating_df.empty:
        print(rating_df[['kreditrating', 'anzahl_kunden', 'exposure', 'exposure_anteil']].to_string(index=False))

    # Top Exposures
    print("\n" + "-" * 50)
    print("TOP 10 EXPOSURES")
    print("-" * 50)
    top_exp = analytics.get_top_exposures(10)
    if not top_exp.empty:
        print(top_exp[['name', 'branche', 'gesamt_exposure', 'portfolio_anteil']].to_string(index=False))

    # NPL Metrics
    print("\n" + "-" * 50)
    print("NPL METRIKEN")
    print("-" * 50)
    npl = analytics.calculate_npl_ratio()
    for key, value in npl.items():
        print(f"  {key}: {value:,.2f}")

    return analytics


def run_early_warning(mode: str = 'demo'):
    """Run early warning system checks."""
    print("=" * 70)
    print("FRÜHWARNSYSTEM")
    print("=" * 70)

    from src.database import get_demo_db, get_real_db
    from src.early_warning import EarlyWarningSystem

    db = get_demo_db() if mode == 'demo' else get_real_db()
    ews = EarlyWarningSystem(db)

    alerts = ews.run_all_checks()
    summary = ews.get_alerts_summary()

    print(f"\nGesamt Alerts: {summary['total_alerts']}")
    print("\nNach Schweregrad:")
    for severity, count in summary['by_severity'].items():
        print(f"  {severity}: {count}")

    print("\n" + "-" * 50)
    print("TOP 10 ALERTS")
    print("-" * 50)

    for alert in alerts[:10]:
        print(f"\n[{alert.severity.value}] {alert.title}")
        print(f"  {alert.description[:100]}...")
        print(f"  Empfehlung: {alert.recommended_action[:80]}...")

    return ews


def run_stress_tests(mode: str = 'demo'):
    """Run stress testing scenarios."""
    print("=" * 70)
    print("STRESS TESTING")
    print("=" * 70)

    from src.database import get_demo_db, get_real_db
    from src.stress_testing import StressTesting, print_stress_test_result

    db = get_demo_db() if mode == 'demo' else get_real_db()
    stress_tester = StressTesting(db)

    print("\nVerfügbare Szenarien:")
    for name, scenario in stress_tester.PREDEFINED_SCENARIOS.items():
        print(f"  - {name}: {scenario.name}")

    print("\n" + "-" * 50)
    print("SZENARIO VERGLEICH")
    print("-" * 50)

    results = stress_tester.run_all_scenarios()

    print(f"\n{'Szenario':<35} {'ECL Anstieg':>15} {'% Änderung':>12}")
    print("-" * 65)

    for name, result in results.items():
        print(f"{result.scenario.name:<35} {result.ecl_increase:>15,.0f} {result.ecl_increase_percent:>11.1f}%")

    # Print detailed result for severe recession
    if 'recession_severe' in results:
        print_stress_test_result(results['recession_severe'])

    return stress_tester


def run_regulatory_reports(mode: str = 'demo'):
    """Generate regulatory reports."""
    print("=" * 70)
    print("REGULATORISCHE BERICHTE")
    print("=" * 70)

    from src.database import get_demo_db, get_real_db
    from src.regulatory_reporting import RegulatoryReporting

    db = get_demo_db() if mode == 'demo' else get_real_db()
    reporting = RegulatoryReporting(db)

    # Print summaries
    reporting.print_capital_summary()
    reporting.print_ifrs9_summary()

    # Generate report file
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f'regulatory_report_{datetime.now().strftime("%Y%m%d")}.xlsx'
    reporting.generate_regulatory_report(report_path)

    return reporting


def generate_dashboards(mode: str = 'demo'):
    """Generate all dashboard outputs."""
    print("=" * 70)
    print("DASHBOARD GENERIERUNG")
    print("=" * 70)

    from src.database import get_demo_db, get_real_db
    from src.dashboard import generate_all_dashboards

    db = get_demo_db() if mode == 'demo' else get_real_db()
    generate_all_dashboards(db)

    print(f"\nDashboards verfügbar unter: {DASHBOARDS_DIR}")
    print(f"  - dashboard.html (HTML Dashboard)")
    print(f"  - dashboard_data.xlsx (Daten Export)")


def run_full_report(mode: str = 'demo'):
    """Generate comprehensive report with all analyses."""
    print("=" * 70)
    print("VOLLSTÄNDIGER RISIKOBERICHT")
    print(f"Modus: {'DEMO' if mode == 'demo' else 'PRODUKTION'}")
    print(f"Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 70)

    # Run all analyses
    run_analysis(mode)
    run_early_warning(mode)
    run_stress_tests(mode)
    run_regulatory_reports(mode)
    generate_dashboards(mode)

    print("\n" + "=" * 70)
    print("BERICHT ABGESCHLOSSEN")
    print("=" * 70)
    print(f"\nAlle Ausgaben wurden generiert:")
    print(f"  - Dashboards: {DASHBOARDS_DIR}")
    print(f"  - Reports: {REPORTS_DIR}")
    print(f"  - Excel Templates: {EXCEL_DIR}")


def interactive_menu():
    """Run interactive menu."""
    while True:
        print("\n" + "=" * 50)
        print("KREDITRISIKO-ÜBERWACHUNGSSYSTEM")
        print("=" * 50)
        print("\n1. Demo System einrichten")
        print("2. Produktionssystem einrichten")
        print("3. Portfolio Analyse")
        print("4. Frühwarnsystem")
        print("5. Stress Testing")
        print("6. Regulatorische Berichte")
        print("7. Dashboards generieren")
        print("8. Vollständiger Bericht")
        print("9. Beenden")

        try:
            choice = input("\nAuswahl (1-9): ").strip()

            if choice == '1':
                setup_demo_system()
            elif choice == '2':
                setup_real_system()
            elif choice == '3':
                mode = input("Modus (demo/real) [demo]: ").strip() or 'demo'
                run_analysis(mode)
            elif choice == '4':
                mode = input("Modus (demo/real) [demo]: ").strip() or 'demo'
                run_early_warning(mode)
            elif choice == '5':
                mode = input("Modus (demo/real) [demo]: ").strip() or 'demo'
                run_stress_tests(mode)
            elif choice == '6':
                mode = input("Modus (demo/real) [demo]: ").strip() or 'demo'
                run_regulatory_reports(mode)
            elif choice == '7':
                mode = input("Modus (demo/real) [demo]: ").strip() or 'demo'
                generate_dashboards(mode)
            elif choice == '8':
                mode = input("Modus (demo/real) [demo]: ").strip() or 'demo'
                run_full_report(mode)
            elif choice == '9':
                print("\nAuf Wiedersehen!")
                break
            else:
                print("Ungültige Auswahl")

        except KeyboardInterrupt:
            print("\n\nAbgebrochen.")
            break
        except Exception as e:
            print(f"\nFehler: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Kreditrisiko-Überwachungssystem (Credit Risk Monitoring System)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python main.py setup-demo          # Demo System mit Testdaten einrichten
  python main.py setup-real          # Produktionssystem einrichten
  python main.py analyze             # Portfolio Analyse ausführen
  python main.py early-warning       # Frühwarnsystem prüfen
  python main.py stress-test         # Stress Tests durchführen
  python main.py regulatory          # Regulatorische Berichte erstellen
  python main.py dashboard           # Dashboards generieren
  python main.py full-report         # Vollständigen Bericht erstellen
  python main.py interactive         # Interaktives Menü
        """
    )

    parser.add_argument('command', nargs='?', default='interactive',
                       choices=['setup-demo', 'setup-real', 'analyze', 'early-warning',
                               'stress-test', 'regulatory', 'dashboard', 'full-report',
                               'interactive'],
                       help='Auszuführender Befehl')

    parser.add_argument('--mode', '-m', choices=['demo', 'real'], default='demo',
                       help='Daten-Modus (demo oder real)')

    args = parser.parse_args()

    try:
        if args.command == 'setup-demo':
            setup_demo_system()
        elif args.command == 'setup-real':
            setup_real_system()
        elif args.command == 'analyze':
            run_analysis(args.mode)
        elif args.command == 'early-warning':
            run_early_warning(args.mode)
        elif args.command == 'stress-test':
            run_stress_tests(args.mode)
        elif args.command == 'regulatory':
            run_regulatory_reports(args.mode)
        elif args.command == 'dashboard':
            generate_dashboards(args.mode)
        elif args.command == 'full-report':
            run_full_report(args.mode)
        else:
            interactive_menu()

    except Exception as e:
        print(f"\nFehler: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
