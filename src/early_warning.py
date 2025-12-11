"""
Early Warning System for Credit Risk Monitoring
Identifies potential defaults and risk escalations before they occur.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import RiskParameters, ConcentrationLimits, IFRS9
from src.database import DatabaseManager


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNUNG"
    CRITICAL = "KRITISCH"
    URGENT = "DRINGEND"


@dataclass
class Alert:
    """Represents an early warning alert."""
    alert_id: str
    severity: AlertSeverity
    category: str
    title: str
    description: str
    affected_entity: str
    entity_id: Optional[int]
    metric_value: float
    threshold: float
    recommended_action: str
    created_at: datetime


class EarlyWarningSystem:
    """
    Early Warning System for identifying credit risk escalations.

    Monitors:
    - Payment delays (>30 days)
    - Rating downgrades
    - High limit utilization (>80%)
    - Concentration breaches
    - Economic indicator deterioration
    """

    def __init__(self, db: DatabaseManager):
        """
        Initialize the Early Warning System.

        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.alerts: List[Alert] = []

    def run_all_checks(self) -> List[Alert]:
        """
        Run all early warning checks.

        Returns:
            List of generated alerts
        """
        self.alerts = []

        print("Running early warning checks...")

        # Payment-related checks
        self._check_payment_delays()
        self._check_payment_deterioration()

        # Customer-related checks
        self._check_rating_downgrades()
        self._check_high_limit_utilization()
        self._check_customer_financial_deterioration()

        # Concentration checks
        self._check_concentration_breaches()

        # Limit checks
        self._check_limit_breaches()

        # Economic indicator checks
        self._check_economic_indicators()

        # Sort alerts by severity
        severity_order = {
            AlertSeverity.URGENT: 0,
            AlertSeverity.CRITICAL: 1,
            AlertSeverity.WARNING: 2,
            AlertSeverity.INFO: 3
        }
        self.alerts.sort(key=lambda x: severity_order.get(x.severity, 99))

        print(f"Generated {len(self.alerts)} alerts")
        return self.alerts

    def _check_payment_delays(self):
        """Check for contracts with significant payment delays."""
        # 30+ days delay
        query_30 = """
        SELECT DISTINCT
            v.vertrag_id,
            k.kunden_id,
            k.name as kunde,
            k.kreditrating,
            v.restschuld as exposure,
            MAX(z.verspaetung_tage) as max_verspaetung,
            COUNT(z.zahlung_id) as verzögerte_zahlungen
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        JOIN zahlungen z ON v.vertrag_id = z.vertrag_id
        WHERE z.verspaetung_tage > 30
        AND v.vertrag_status = 'aktiv'
        GROUP BY v.vertrag_id
        ORDER BY exposure DESC
        """

        results = self.db.execute_query(query_30)

        for row in results:
            if row['max_verspaetung'] > 90:
                severity = AlertSeverity.URGENT
                category = "Zahlungsverzug > 90 Tage"
            elif row['max_verspaetung'] > 60:
                severity = AlertSeverity.CRITICAL
                category = "Zahlungsverzug > 60 Tage"
            else:
                severity = AlertSeverity.WARNING
                category = "Zahlungsverzug > 30 Tage"

            self.alerts.append(Alert(
                alert_id=f"PAY_{row['vertrag_id']}_{datetime.now().strftime('%Y%m%d')}",
                severity=severity,
                category=category,
                title=f"Zahlungsverzug bei {row['kunde']}",
                description=f"Vertrag {row['vertrag_id']} hat {row['verzögerte_zahlungen']} "
                           f"verzögerte Zahlungen mit max. {row['max_verspaetung']} Tagen Verzug. "
                           f"Exposure: {row['exposure']:,.2f} EUR",
                affected_entity=row['kunde'],
                entity_id=row['kunden_id'],
                metric_value=row['max_verspaetung'],
                threshold=30,
                recommended_action="Kundenberatung einleiten, Zahlungsplan prüfen, "
                                  "ggf. Mahnverfahren starten",
                created_at=datetime.now()
            ))

    def _check_payment_deterioration(self):
        """Check for deteriorating payment behavior trends."""
        query = """
        SELECT
            v.vertrag_id,
            k.name as kunde,
            k.kunden_id,
            v.restschuld,
            COUNT(CASE WHEN z.verspaetung_tage > 0 THEN 1 END) as verzögerte_count,
            COUNT(z.zahlung_id) as total_zahlungen,
            AVG(z.verspaetung_tage) as avg_verspaetung
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        JOIN zahlungen z ON v.vertrag_id = z.vertrag_id
        WHERE z.faelligkeitsdatum >= date('now', '-6 months')
        AND v.vertrag_status = 'aktiv'
        GROUP BY v.vertrag_id
        HAVING verzögerte_count > 2 AND (verzögerte_count * 1.0 / total_zahlungen) > 0.3
        ORDER BY restschuld DESC
        """

        results = self.db.execute_query(query)

        for row in results:
            delay_ratio = row['verzögerte_count'] / row['total_zahlungen'] * 100

            self.alerts.append(Alert(
                alert_id=f"PAYTREND_{row['vertrag_id']}_{datetime.now().strftime('%Y%m%d')}",
                severity=AlertSeverity.WARNING,
                category="Verschlechterndes Zahlungsverhalten",
                title=f"Zahlungstrend-Verschlechterung bei {row['kunde']}",
                description=f"{delay_ratio:.1f}% der Zahlungen in den letzten 6 Monaten "
                           f"waren verspätet ({row['verzögerte_count']} von {row['total_zahlungen']}). "
                           f"Durchschnittliche Verspätung: {row['avg_verspaetung']:.1f} Tage",
                affected_entity=row['kunde'],
                entity_id=row['kunden_id'],
                metric_value=delay_ratio,
                threshold=30,
                recommended_action="Frühzeitige Kundenansprache, Ursachenanalyse durchführen",
                created_at=datetime.now()
            ))

    def _check_rating_downgrades(self):
        """Check for recent rating downgrades."""
        query = """
        SELECT
            rh.kunden_id,
            k.name as kunde,
            rh.altes_rating,
            rh.neues_rating,
            rh.aenderungsdatum,
            rh.aenderungsgrund,
            (SELECT SUM(restschuld) FROM kredit_vertraege
             WHERE kunden_id = k.kunden_id AND vertrag_status = 'aktiv') as exposure
        FROM rating_historie rh
        JOIN kunden k ON rh.kunden_id = k.kunden_id
        WHERE rh.aenderungsdatum >= date('now', '-90 days')
        ORDER BY rh.aenderungsdatum DESC
        """

        results = self.db.execute_query(query)

        # Rating order for comparison
        rating_order = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'CC', 'C', 'D']

        for row in results:
            old_idx = rating_order.index(row['altes_rating']) if row['altes_rating'] in rating_order else -1
            new_idx = rating_order.index(row['neues_rating']) if row['neues_rating'] in rating_order else -1

            # Check if it's a downgrade (higher index = worse rating)
            if new_idx > old_idx:
                notches = new_idx - old_idx

                if notches >= 3 or new_idx >= rating_order.index('CCC'):
                    severity = AlertSeverity.CRITICAL
                elif notches >= 2:
                    severity = AlertSeverity.WARNING
                else:
                    severity = AlertSeverity.INFO

                self.alerts.append(Alert(
                    alert_id=f"RATING_{row['kunden_id']}_{datetime.now().strftime('%Y%m%d')}",
                    severity=severity,
                    category="Rating Downgrade",
                    title=f"Rating-Herabstufung: {row['kunde']}",
                    description=f"Rating von {row['altes_rating']} auf {row['neues_rating']} "
                               f"geändert am {row['aenderungsdatum']}. "
                               f"Grund: {row['aenderungsgrund']}. "
                               f"Exposure: {row['exposure'] or 0:,.2f} EUR",
                    affected_entity=row['kunde'],
                    entity_id=row['kunden_id'],
                    metric_value=notches,
                    threshold=1,
                    recommended_action="Kredit-Review durchführen, Sicherheiten prüfen, "
                                      "PD/LGD Parameter aktualisieren",
                    created_at=datetime.now()
                ))

    def _check_high_limit_utilization(self):
        """Check for high credit limit utilization."""
        query = """
        SELECT
            v.vertrag_id,
            k.kunden_id,
            k.name as kunde,
            k.kreditrating,
            v.kreditlimit,
            v.ausgenutztes_limit,
            (v.ausgenutztes_limit * 100.0 / v.kreditlimit) as auslastung_prozent
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        WHERE v.kreditlimit > 0
        AND v.vertrag_status = 'aktiv'
        AND (v.ausgenutztes_limit * 100.0 / v.kreditlimit) > 80
        ORDER BY auslastung_prozent DESC
        """

        results = self.db.execute_query(query)

        for row in results:
            utilization = row['auslastung_prozent']

            if utilization >= 100:
                severity = AlertSeverity.CRITICAL
                category = "Limitüberschreitung"
            elif utilization >= 95:
                severity = AlertSeverity.WARNING
                category = "Kritische Limitauslastung (>95%)"
            else:
                severity = AlertSeverity.INFO
                category = "Hohe Limitauslastung (>80%)"

            self.alerts.append(Alert(
                alert_id=f"LIMIT_{row['vertrag_id']}_{datetime.now().strftime('%Y%m%d')}",
                severity=severity,
                category=category,
                title=f"Hohe Limitauslastung: {row['kunde']}",
                description=f"Vertrag {row['vertrag_id']}: {utilization:.1f}% Auslastung "
                           f"({row['ausgenutztes_limit']:,.2f} von {row['kreditlimit']:,.2f} EUR). "
                           f"Rating: {row['kreditrating']}",
                affected_entity=row['kunde'],
                entity_id=row['kunden_id'],
                metric_value=utilization,
                threshold=80,
                recommended_action="Limiterhöhung prüfen oder Rückführungsplan erstellen",
                created_at=datetime.now()
            ))

    def _check_customer_financial_deterioration(self):
        """Check for customers with multiple warning signals."""
        query = """
        SELECT
            k.kunden_id,
            k.name,
            k.kreditrating,
            k.bonitaetsindex,
            COUNT(DISTINCT v.vertrag_id) as anzahl_vertraege,
            SUM(v.restschuld) as total_exposure,
            SUM(CASE WHEN z.verspaetung_tage > 30 THEN 1 ELSE 0 END) as verzögerte_zahlungen,
            MAX(z.verspaetung_tage) as max_verspaetung
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        LEFT JOIN zahlungen z ON v.vertrag_id = z.vertrag_id
        WHERE v.vertrag_status = 'aktiv'
        AND k.bonitaetsindex < 50
        GROUP BY k.kunden_id
        HAVING verzögerte_zahlungen > 0 OR k.bonitaetsindex < 40
        ORDER BY total_exposure DESC
        """

        results = self.db.execute_query(query)

        for row in results:
            risk_score = 0
            risk_factors = []

            if row['bonitaetsindex'] < 30:
                risk_score += 3
                risk_factors.append("Sehr niedriger Bonitätsindex")
            elif row['bonitaetsindex'] < 40:
                risk_score += 2
                risk_factors.append("Niedriger Bonitätsindex")

            if row['verzögerte_zahlungen'] and row['verzögerte_zahlungen'] > 3:
                risk_score += 2
                risk_factors.append(f"{row['verzögerte_zahlungen']} verzögerte Zahlungen")

            if row['kreditrating'] in ['CCC', 'CC', 'C', 'D']:
                risk_score += 3
                risk_factors.append(f"Schwaches Rating ({row['kreditrating']})")

            if risk_score >= 4:
                severity = AlertSeverity.CRITICAL
            elif risk_score >= 2:
                severity = AlertSeverity.WARNING
            else:
                continue  # Skip low-risk

            self.alerts.append(Alert(
                alert_id=f"FIN_{row['kunden_id']}_{datetime.now().strftime('%Y%m%d')}",
                severity=severity,
                category="Finanzielle Verschlechterung",
                title=f"Multiple Risikofaktoren: {row['name']}",
                description=f"Risikofaktoren: {', '.join(risk_factors)}. "
                           f"Exposure: {row['total_exposure']:,.2f} EUR, "
                           f"Bonitätsindex: {row['bonitaetsindex']:.1f}",
                affected_entity=row['name'],
                entity_id=row['kunden_id'],
                metric_value=risk_score,
                threshold=2,
                recommended_action="Umfassende Kundenanalyse, Risikominimierung prüfen",
                created_at=datetime.now()
            ))

    def _check_concentration_breaches(self):
        """Check for concentration limit breaches."""
        # Industry concentration
        query_industry = """
        SELECT
            k.branche,
            SUM(v.restschuld) as exposure,
            (SELECT SUM(restschuld) FROM kredit_vertraege WHERE vertrag_status = 'aktiv') as total_portfolio
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        GROUP BY k.branche
        """

        results = self.db.execute_query(query_industry)

        for row in results:
            if row['total_portfolio'] and row['total_portfolio'] > 0:
                concentration = row['exposure'] / row['total_portfolio'] * 100

                if concentration > ConcentrationLimits.INDUSTRY_MAX:
                    self.alerts.append(Alert(
                        alert_id=f"CONC_IND_{row['branche']}_{datetime.now().strftime('%Y%m%d')}",
                        severity=AlertSeverity.CRITICAL,
                        category="Branchenkonzentration überschritten",
                        title=f"Branchenlimit überschritten: {row['branche']}",
                        description=f"Branche {row['branche']} hat {concentration:.1f}% "
                                   f"Portfolioanteil (Limit: {ConcentrationLimits.INDUSTRY_MAX}%). "
                                   f"Exposure: {row['exposure']:,.2f} EUR",
                        affected_entity=row['branche'],
                        entity_id=None,
                        metric_value=concentration,
                        threshold=ConcentrationLimits.INDUSTRY_MAX,
                        recommended_action="Neugeschäft in dieser Branche einschränken, "
                                          "Portfolio diversifizieren",
                        created_at=datetime.now()
                    ))
                elif concentration > ConcentrationLimits.INDUSTRY_MAX * 0.8:
                    self.alerts.append(Alert(
                        alert_id=f"CONC_IND_W_{row['branche']}_{datetime.now().strftime('%Y%m%d')}",
                        severity=AlertSeverity.WARNING,
                        category="Branchenkonzentration Warnung",
                        title=f"Branchenkonzentration hoch: {row['branche']}",
                        description=f"Branche {row['branche']} nähert sich dem Limit mit "
                                   f"{concentration:.1f}% (Limit: {ConcentrationLimits.INDUSTRY_MAX}%)",
                        affected_entity=row['branche'],
                        entity_id=None,
                        metric_value=concentration,
                        threshold=ConcentrationLimits.INDUSTRY_MAX * 0.8,
                        recommended_action="Neugeschäft beobachten, Diversifikation planen",
                        created_at=datetime.now()
                    ))

    def _check_limit_breaches(self):
        """Check for risk limit breaches from the limits table."""
        query = """
        SELECT
            limit_id,
            limit_typ,
            limit_name,
            referenz_wert,
            limit_wert,
            aktuelle_auslastung,
            auslastung_prozent,
            ueberschreitung_flag,
            ueberschreitung_betrag
        FROM risiko_limits
        WHERE ueberschreitung_flag = 1 OR auslastung_prozent > 80
        ORDER BY auslastung_prozent DESC
        """

        results = self.db.execute_query(query)

        for row in results:
            if row['ueberschreitung_flag']:
                severity = AlertSeverity.URGENT
                category = f"{row['limit_typ'].capitalize()}-Limit überschritten"
            elif row['auslastung_prozent'] > 95:
                severity = AlertSeverity.CRITICAL
                category = f"{row['limit_typ'].capitalize()}-Limit kritisch"
            else:
                severity = AlertSeverity.WARNING
                category = f"{row['limit_typ'].capitalize()}-Limit Warnung"

            self.alerts.append(Alert(
                alert_id=f"LIM_{row['limit_id']}_{datetime.now().strftime('%Y%m%d')}",
                severity=severity,
                category=category,
                title=f"Limit: {row['limit_name']}",
                description=f"Auslastung: {row['auslastung_prozent']:.1f}% "
                           f"({row['aktuelle_auslastung']:,.2f} von {row['limit_wert']:,.2f} EUR). "
                           f"Überschreitung: {row['ueberschreitung_betrag']:,.2f} EUR",
                affected_entity=row['referenz_wert'] or row['limit_name'],
                entity_id=row['limit_id'],
                metric_value=row['auslastung_prozent'],
                threshold=100,
                recommended_action="Limit-Eskalation einleiten, Genehmigung einholen",
                created_at=datetime.now()
            ))

    def _check_economic_indicators(self):
        """Check for adverse economic indicator movements."""
        query = """
        SELECT
            region,
            MAX(datum) as latest_date,
            AVG(arbeitslosenquote) as avg_unemployment,
            AVG(insolvenzquote) as avg_insolvency,
            AVG(konjunktur_index) as avg_konjunktur
        FROM wirtschaftsdaten
        WHERE datum >= date('now', '-3 months')
        AND branche IS NULL
        GROUP BY region
        HAVING avg_unemployment > 7 OR avg_insolvency > 0.015 OR avg_konjunktur < 95
        """

        results = self.db.execute_query(query)

        for row in results:
            indicators = []

            if row['avg_unemployment'] and row['avg_unemployment'] > 7:
                indicators.append(f"Hohe Arbeitslosigkeit ({row['avg_unemployment']:.1f}%)")

            if row['avg_insolvency'] and row['avg_insolvency'] > 0.015:
                indicators.append(f"Hohe Insolvenzquote ({row['avg_insolvency']*100:.2f}%)")

            if row['avg_konjunktur'] and row['avg_konjunktur'] < 95:
                indicators.append(f"Schwache Konjunktur (Index: {row['avg_konjunktur']:.1f})")

            if indicators:
                self.alerts.append(Alert(
                    alert_id=f"ECON_{row['region']}_{datetime.now().strftime('%Y%m%d')}",
                    severity=AlertSeverity.INFO,
                    category="Wirtschaftliche Warnindikatoren",
                    title=f"Wirtschaftliche Risiken: {row['region']}",
                    description=f"Region {row['region']}: {', '.join(indicators)}",
                    affected_entity=row['region'],
                    entity_id=None,
                    metric_value=row['avg_unemployment'] or 0,
                    threshold=7,
                    recommended_action="Portfolio-Exposure in dieser Region überprüfen",
                    created_at=datetime.now()
                ))

    def get_alerts_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of alerts.

        Returns:
            Dictionary with alert summary
        """
        summary = {
            'total_alerts': len(self.alerts),
            'by_severity': {},
            'by_category': {}
        }

        for severity in AlertSeverity:
            count = len([a for a in self.alerts if a.severity == severity])
            summary['by_severity'][severity.value] = count

        categories = set(a.category for a in self.alerts)
        for cat in categories:
            summary['by_category'][cat] = len([a for a in self.alerts if a.category == cat])

        return summary

    def get_alerts_dataframe(self) -> pd.DataFrame:
        """
        Convert alerts to DataFrame for reporting.

        Returns:
            DataFrame with all alerts
        """
        if not self.alerts:
            return pd.DataFrame()

        data = [{
            'alert_id': a.alert_id,
            'severity': a.severity.value,
            'category': a.category,
            'title': a.title,
            'description': a.description,
            'affected_entity': a.affected_entity,
            'entity_id': a.entity_id,
            'metric_value': a.metric_value,
            'threshold': a.threshold,
            'recommended_action': a.recommended_action,
            'created_at': a.created_at
        } for a in self.alerts]

        return pd.DataFrame(data)

    def export_alerts_report(self, output_path: Path) -> None:
        """
        Export alerts to an Excel report.

        Args:
            output_path: Path for the Excel file
        """
        df = self.get_alerts_dataframe()

        if df.empty:
            print("No alerts to export")
            return

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = self.get_alerts_summary()
            summary_df = pd.DataFrame([
                {'Metrik': 'Gesamt Alerts', 'Wert': summary_data['total_alerts']},
                {'Metrik': 'DRINGEND', 'Wert': summary_data['by_severity'].get('DRINGEND', 0)},
                {'Metrik': 'KRITISCH', 'Wert': summary_data['by_severity'].get('KRITISCH', 0)},
                {'Metrik': 'WARNUNG', 'Wert': summary_data['by_severity'].get('WARNUNG', 0)},
                {'Metrik': 'INFO', 'Wert': summary_data['by_severity'].get('INFO', 0)}
            ])
            summary_df.to_excel(writer, sheet_name='Zusammenfassung', index=False)

            # All alerts
            df.to_excel(writer, sheet_name='Alle_Alerts', index=False)

            # Critical alerts
            critical = df[df['severity'].isin(['DRINGEND', 'KRITISCH'])]
            if not critical.empty:
                critical.to_excel(writer, sheet_name='Kritische_Alerts', index=False)

        print(f"Alerts exported to: {output_path}")


def run_early_warning_check(db: DatabaseManager) -> Tuple[List[Alert], Dict[str, Any]]:
    """
    Run early warning system and return results.

    Args:
        db: DatabaseManager instance

    Returns:
        Tuple of (alerts list, summary dict)
    """
    ews = EarlyWarningSystem(db)
    alerts = ews.run_all_checks()
    summary = ews.get_alerts_summary()

    return alerts, summary


if __name__ == "__main__":
    from src.database import get_demo_db

    db = get_demo_db()
    ews = EarlyWarningSystem(db)

    print("=" * 70)
    print("EARLY WARNING SYSTEM - CREDIT RISK MONITORING")
    print("=" * 70)

    alerts = ews.run_all_checks()
    summary = ews.get_alerts_summary()

    print(f"\n{'='*70}")
    print("ALERT SUMMARY")
    print("=" * 70)
    print(f"Total Alerts: {summary['total_alerts']}")
    print("\nBy Severity:")
    for sev, count in summary['by_severity'].items():
        print(f"  {sev}: {count}")

    print(f"\n{'='*70}")
    print("TOP ALERTS")
    print("=" * 70)

    for alert in alerts[:10]:
        print(f"\n[{alert.severity.value}] {alert.title}")
        print(f"  {alert.description}")
        print(f"  Empfehlung: {alert.recommended_action}")
