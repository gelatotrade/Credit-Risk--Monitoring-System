"""
Risk Analytics Module for Credit Risk Monitoring System
Core risk calculations and analysis functions.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import RiskParameters, ConcentrationLimits, IFRS9
from src.database import DatabaseManager


class RiskAnalytics:
    """
    Core risk analytics calculations for credit portfolio analysis.
    """

    def __init__(self, db: DatabaseManager):
        """
        Initialize risk analytics with database connection.

        Args:
            db: DatabaseManager instance
        """
        self.db = db

    # =========================================================================
    # PORTFOLIO OVERVIEW
    # =========================================================================

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get high-level portfolio summary statistics.

        Returns:
            Dictionary with portfolio metrics
        """
        query = """
        SELECT
            COUNT(DISTINCT v.vertrag_id) as anzahl_vertraege,
            COUNT(DISTINCT v.kunden_id) as anzahl_kunden,
            SUM(v.kreditlimit) as gesamt_limit,
            SUM(v.ausgenutztes_limit) as gesamt_auslastung,
            SUM(v.restschuld) as gesamt_exposure,
            SUM(v.sicherheiten_wert) as gesamt_sicherheiten,
            AVG(v.zinssatz) as durchschnitt_zinssatz,
            AVG(v.laufzeit_monate) as durchschnitt_laufzeit,
            SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) as npl_volumen,
            SUM(CASE WHEN v.vertrag_status = 'aktiv' THEN v.restschuld ELSE 0 END) as performing_volumen
        FROM kredit_vertraege v
        WHERE v.vertrag_status IN ('aktiv', 'ausfall', 'gekuendigt')
        """

        result = self.db.execute_query(query)

        if result:
            data = result[0]
            gesamt_exposure = data['gesamt_exposure'] or 0
            npl_volumen = data['npl_volumen'] or 0

            return {
                'anzahl_vertraege': data['anzahl_vertraege'] or 0,
                'anzahl_kunden': data['anzahl_kunden'] or 0,
                'gesamt_limit': data['gesamt_limit'] or 0,
                'gesamt_auslastung': data['gesamt_auslastung'] or 0,
                'gesamt_exposure': gesamt_exposure,
                'gesamt_sicherheiten': data['gesamt_sicherheiten'] or 0,
                'unbesichertes_exposure': max(0, gesamt_exposure - (data['gesamt_sicherheiten'] or 0)),
                'durchschnitt_zinssatz': data['durchschnitt_zinssatz'] or 0,
                'durchschnitt_laufzeit': data['durchschnitt_laufzeit'] or 0,
                'npl_volumen': npl_volumen,
                'npl_quote': (npl_volumen / gesamt_exposure * 100) if gesamt_exposure > 0 else 0,
                'performing_volumen': data['performing_volumen'] or 0
            }

        return {}

    def get_rating_distribution(self) -> pd.DataFrame:
        """
        Get portfolio distribution by credit rating.

        Returns:
            DataFrame with rating distribution
        """
        query = """
        SELECT
            k.kreditrating,
            COUNT(DISTINCT k.kunden_id) as anzahl_kunden,
            COUNT(v.vertrag_id) as anzahl_vertraege,
            SUM(v.restschuld) as exposure,
            AVG(k.bonitaetsindex) as durchschnitt_bonitaet,
            SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN 1 ELSE 0 END) as anzahl_ausfaelle
        FROM kunden k
        LEFT JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        GROUP BY k.kreditrating
        ORDER BY
            CASE k.kreditrating
                WHEN 'AAA' THEN 1 WHEN 'AA' THEN 2 WHEN 'A' THEN 3
                WHEN 'BBB' THEN 4 WHEN 'BB' THEN 5 WHEN 'B' THEN 6
                WHEN 'CCC' THEN 7 WHEN 'CC' THEN 8 WHEN 'C' THEN 9
                WHEN 'D' THEN 10 ELSE 11
            END
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            total_exposure = df['exposure'].sum()
            df['exposure_anteil'] = df['exposure'] / total_exposure * 100 if total_exposure > 0 else 0
            df['ausfallrate'] = df['anzahl_ausfaelle'] / df['anzahl_vertraege'] * 100

        return df

    # =========================================================================
    # CONCENTRATION RISK
    # =========================================================================

    def get_top_exposures(self, n: int = 10) -> pd.DataFrame:
        """
        Get top N customers by exposure.

        Args:
            n: Number of top customers

        Returns:
            DataFrame with top exposures
        """
        query = f"""
        SELECT
            k.kunden_id,
            k.name,
            k.branche,
            k.region,
            k.kreditrating,
            k.risiko_klasse,
            COUNT(v.vertrag_id) as anzahl_vertraege,
            SUM(v.kreditlimit) as gesamt_limit,
            SUM(v.restschuld) as gesamt_exposure,
            SUM(v.sicherheiten_wert) as gesamt_sicherheiten,
            SUM(v.restschuld) - SUM(v.sicherheiten_wert) as unbesichertes_exposure
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        GROUP BY k.kunden_id
        ORDER BY gesamt_exposure DESC
        LIMIT {n}
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            total = self.get_portfolio_summary()['gesamt_exposure']
            df['portfolio_anteil'] = df['gesamt_exposure'] / total * 100 if total > 0 else 0
            df['limit_auslastung'] = df['gesamt_exposure'] / df['gesamt_limit'] * 100

        return df

    def get_industry_concentration(self) -> pd.DataFrame:
        """
        Analyze concentration risk by industry.

        Returns:
            DataFrame with industry concentration
        """
        query = """
        SELECT
            k.branche,
            COUNT(DISTINCT k.kunden_id) as anzahl_kunden,
            COUNT(v.vertrag_id) as anzahl_vertraege,
            SUM(v.kreditlimit) as gesamt_limit,
            SUM(v.restschuld) as exposure,
            SUM(v.sicherheiten_wert) as sicherheiten,
            AVG(k.bonitaetsindex) as durchschnitt_bonitaet,
            SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) as npl_volumen
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        GROUP BY k.branche
        ORDER BY exposure DESC
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            total_exposure = df['exposure'].sum()
            df['konzentration_prozent'] = df['exposure'] / total_exposure * 100 if total_exposure > 0 else 0
            df['limit_ueberschritten'] = df['konzentration_prozent'] > ConcentrationLimits.INDUSTRY_MAX
            df['npl_quote'] = df['npl_volumen'] / df['exposure'] * 100

        return df

    def get_regional_concentration(self) -> pd.DataFrame:
        """
        Analyze concentration risk by region.

        Returns:
            DataFrame with regional concentration
        """
        query = """
        SELECT
            k.region,
            COUNT(DISTINCT k.kunden_id) as anzahl_kunden,
            COUNT(v.vertrag_id) as anzahl_vertraege,
            SUM(v.restschuld) as exposure,
            AVG(k.bonitaetsindex) as durchschnitt_bonitaet,
            SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) as npl_volumen
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        GROUP BY k.region
        ORDER BY exposure DESC
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            total_exposure = df['exposure'].sum()
            df['konzentration_prozent'] = df['exposure'] / total_exposure * 100 if total_exposure > 0 else 0
            df['limit_ueberschritten'] = df['konzentration_prozent'] > ConcentrationLimits.REGION_MAX

        return df

    def get_concentration_matrix(self) -> pd.DataFrame:
        """
        Generate industry x region concentration matrix.

        Returns:
            Pivot table with concentration data
        """
        query = """
        SELECT
            k.branche,
            k.region,
            SUM(v.restschuld) as exposure,
            COUNT(DISTINCT k.kunden_id) as anzahl_kunden
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        GROUP BY k.branche, k.region
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            pivot = df.pivot_table(
                index='branche',
                columns='region',
                values='exposure',
                aggfunc='sum',
                fill_value=0
            )
            return pivot

        return pd.DataFrame()

    # =========================================================================
    # PORTFOLIO QUALITY METRICS
    # =========================================================================

    def calculate_npl_ratio(self) -> Dict[str, float]:
        """
        Calculate Non-Performing Loans ratio.

        Returns:
            Dictionary with NPL metrics
        """
        query = """
        SELECT
            SUM(restschuld) as total_exposure,
            SUM(CASE WHEN vertrag_status = 'ausfall' THEN restschuld ELSE 0 END) as npl_exposure,
            SUM(CASE WHEN vertrag_status = 'ausfall' THEN sicherheiten_wert ELSE 0 END) as npl_sicherheiten
        FROM kredit_vertraege
        """

        result = self.db.execute_query(query)

        if result:
            data = result[0]
            total = data['total_exposure'] or 0
            npl = data['npl_exposure'] or 0
            npl_sicherheiten = data['npl_sicherheiten'] or 0

            return {
                'total_exposure': total,
                'npl_exposure': npl,
                'npl_ratio': (npl / total * 100) if total > 0 else 0,
                'npl_sicherheiten': npl_sicherheiten,
                'npl_unbesichert': npl - npl_sicherheiten,
                'npl_deckungsgrad': (npl_sicherheiten / npl * 100) if npl > 0 else 0
            }

        return {}

    def calculate_coverage_ratio(self) -> Dict[str, float]:
        """
        Calculate coverage ratio (provisions to NPL).

        Returns:
            Dictionary with coverage metrics
        """
        # Get NPL
        npl_data = self.calculate_npl_ratio()
        npl = npl_data.get('npl_exposure', 0)

        # Get provisions
        query = """
        SELECT
            SUM(rueckstellung_betrag) as total_provisions,
            SUM(CASE WHEN stufe = 3 THEN rueckstellung_betrag ELSE 0 END) as stage3_provisions
        FROM rueckstellungen
        WHERE stichtag = (SELECT MAX(stichtag) FROM rueckstellungen)
        """

        result = self.db.execute_query(query)

        if result:
            data = result[0]
            total_provisions = data['total_provisions'] or 0
            stage3_provisions = data['stage3_provisions'] or 0

            return {
                'npl_exposure': npl,
                'total_provisions': total_provisions,
                'stage3_provisions': stage3_provisions,
                'coverage_ratio': (total_provisions / npl * 100) if npl > 0 else 0,
                'stage3_coverage_ratio': (stage3_provisions / npl * 100) if npl > 0 else 0
            }

        return {}

    def calculate_expected_vs_actual_loss(self) -> pd.DataFrame:
        """
        Compare expected loss (from PD/LGD models) vs actual defaults.

        Returns:
            DataFrame with expected vs actual loss comparison
        """
        query = """
        SELECT
            strftime('%Y', v.vertragsdatum) as jahr,
            k.kreditrating,
            COUNT(v.vertrag_id) as anzahl_vertraege,
            SUM(v.ead_wert) as total_ead,
            AVG(v.pd_wert) as avg_pd,
            AVG(v.lgd_wert) as avg_lgd,
            SUM(v.ead_wert * v.pd_wert * v.lgd_wert) as expected_loss,
            COALESCE(SUM(a.ausgefallener_betrag), 0) as actual_loss,
            COALESCE(SUM(a.wiederherstellungs_betrag), 0) as recovered
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        LEFT JOIN ausfall_ereignisse a ON v.vertrag_id = a.vertrag_id
        GROUP BY strftime('%Y', v.vertragsdatum), k.kreditrating
        ORDER BY jahr DESC, k.kreditrating
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            df['actual_net_loss'] = df['actual_loss'] - df['recovered']
            df['el_vs_actual'] = df['expected_loss'] - df['actual_net_loss']
            df['model_accuracy'] = 1 - abs(df['el_vs_actual']) / (df['expected_loss'] + 0.01)

        return df

    # =========================================================================
    # PAYMENT ANALYSIS
    # =========================================================================

    def get_delinquency_analysis(self) -> pd.DataFrame:
        """
        Analyze payment delinquencies by bucket.

        Returns:
            DataFrame with delinquency buckets
        """
        query = """
        SELECT
            CASE
                WHEN verspaetung_tage = 0 THEN '0 Tage (aktuell)'
                WHEN verspaetung_tage BETWEEN 1 AND 30 THEN '1-30 Tage'
                WHEN verspaetung_tage BETWEEN 31 AND 60 THEN '31-60 Tage'
                WHEN verspaetung_tage BETWEEN 61 AND 90 THEN '61-90 Tage'
                WHEN verspaetung_tage BETWEEN 91 AND 180 THEN '91-180 Tage'
                ELSE '>180 Tage'
            END as bucket,
            COUNT(*) as anzahl_zahlungen,
            SUM(soll_betrag) as soll_gesamt,
            SUM(ist_betrag) as ist_gesamt,
            AVG(verspaetung_tage) as avg_verspaetung
        FROM zahlungen
        WHERE zahlungsstatus IN ('verzoegert', 'ausfall', 'offen')
        GROUP BY bucket
        ORDER BY
            CASE bucket
                WHEN '0 Tage (aktuell)' THEN 1
                WHEN '1-30 Tage' THEN 2
                WHEN '31-60 Tage' THEN 3
                WHEN '61-90 Tage' THEN 4
                WHEN '91-180 Tage' THEN 5
                ELSE 6
            END
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            df['ausstehend'] = df['soll_gesamt'] - df['ist_gesamt']
            total = df['soll_gesamt'].sum()
            df['anteil'] = df['soll_gesamt'] / total * 100 if total > 0 else 0

        return df

    def get_vintage_analysis(self) -> pd.DataFrame:
        """
        Perform vintage analysis on loan cohorts.

        Returns:
            DataFrame with vintage performance data
        """
        query = """
        SELECT
            strftime('%Y-%m', v.vertragsdatum) as kohorte,
            COUNT(DISTINCT v.vertrag_id) as anzahl_vertraege,
            SUM(v.kreditlimit) as urspruengliches_volumen,
            SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) as ausgefallen,
            AVG(JULIANDAY('now') - JULIANDAY(v.vertragsdatum)) / 30 as alter_monate
        FROM kredit_vertraege v
        GROUP BY strftime('%Y-%m', v.vertragsdatum)
        HAVING anzahl_vertraege > 5
        ORDER BY kohorte DESC
        LIMIT 24
        """

        df = self.db.execute_dataframe(query)

        if not df.empty:
            df['ausfallrate'] = df['ausgefallen'] / df['urspruengliches_volumen'] * 100

        return df

    # =========================================================================
    # RISK-WEIGHTED ASSETS
    # =========================================================================

    def calculate_rwa(self) -> Dict[str, Any]:
        """
        Calculate Risk-Weighted Assets (simplified Basel approach).

        Returns:
            Dictionary with RWA calculations
        """
        query = """
        SELECT
            k.kreditrating,
            v.produkt_typ,
            SUM(v.restschuld) as exposure,
            SUM(v.sicherheiten_wert) as sicherheiten
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        GROUP BY k.kreditrating, v.produkt_typ
        """

        df = self.db.execute_dataframe(query)

        if df.empty:
            return {}

        total_exposure = 0
        total_rwa = 0

        # Map ratings to simplified risk weights
        rating_to_weight = {
            'AAA': 0.20, 'AA': 0.20, 'A': 0.50,
            'BBB': 1.00, 'BB': 1.00, 'B': 1.50,
            'CCC': 1.50, 'CC': 1.50, 'C': 1.50, 'D': 1.50
        }

        for _, row in df.iterrows():
            exposure = row['exposure'] or 0
            sicherheiten = row['sicherheiten'] or 0

            # Net exposure after collateral (simplified)
            net_exposure = max(0, exposure - sicherheiten * 0.8)

            # Risk weight
            rw = rating_to_weight.get(row['kreditrating'], 1.0)

            # Calculate RWA
            rwa = net_exposure * rw

            total_exposure += exposure
            total_rwa += rwa

        # Capital requirement (8% of RWA for credit risk)
        capital_requirement = total_rwa * 0.08

        return {
            'total_exposure': total_exposure,
            'total_rwa': total_rwa,
            'rwa_density': (total_rwa / total_exposure * 100) if total_exposure > 0 else 0,
            'capital_requirement': capital_requirement,
            'capital_ratio_required': 8.0
        }

    # =========================================================================
    # TREND ANALYSIS
    # =========================================================================

    def get_portfolio_trend(self, months: int = 12) -> pd.DataFrame:
        """
        Get portfolio quality trend over time.

        Args:
            months: Number of months to analyze

        Returns:
            DataFrame with trend data
        """
        query = f"""
        SELECT
            strftime('%Y-%m', v.vertragsdatum) as monat,
            COUNT(v.vertrag_id) as neue_vertraege,
            SUM(v.kreditlimit) as neues_volumen,
            AVG(k.bonitaetsindex) as durchschnitt_bonitaet
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        WHERE v.vertragsdatum >= date('now', '-{months} months')
        GROUP BY strftime('%Y-%m', v.vertragsdatum)
        ORDER BY monat
        """

        return self.db.execute_dataframe(query)

    def get_default_trend(self, months: int = 24) -> pd.DataFrame:
        """
        Get default trend over time.

        Args:
            months: Number of months to analyze

        Returns:
            DataFrame with default trend
        """
        query = f"""
        SELECT
            strftime('%Y-%m', ausfall_datum) as monat,
            COUNT(*) as anzahl_ausfaelle,
            SUM(ausgefallener_betrag) as ausfall_volumen,
            AVG(wiederherstellungs_quote) as avg_recovery_rate
        FROM ausfall_ereignisse
        WHERE ausfall_datum >= date('now', '-{months} months')
        GROUP BY strftime('%Y-%m', ausfall_datum)
        ORDER BY monat
        """

        return self.db.execute_dataframe(query)


def run_portfolio_analysis(db: DatabaseManager) -> Dict[str, Any]:
    """
    Run comprehensive portfolio analysis.

    Args:
        db: DatabaseManager instance

    Returns:
        Dictionary with all analysis results
    """
    analytics = RiskAnalytics(db)

    print("Running portfolio analysis...")

    results = {
        'summary': analytics.get_portfolio_summary(),
        'rating_distribution': analytics.get_rating_distribution(),
        'top_exposures': analytics.get_top_exposures(),
        'industry_concentration': analytics.get_industry_concentration(),
        'regional_concentration': analytics.get_regional_concentration(),
        'npl_metrics': analytics.calculate_npl_ratio(),
        'coverage_metrics': analytics.calculate_coverage_ratio(),
        'delinquency': analytics.get_delinquency_analysis(),
        'rwa': analytics.calculate_rwa(),
        'vintage': analytics.get_vintage_analysis()
    }

    print("Analysis complete!")
    return results


if __name__ == "__main__":
    from src.database import get_demo_db

    db = get_demo_db()
    analytics = RiskAnalytics(db)

    print("=" * 60)
    print("PORTFOLIO SUMMARY")
    print("=" * 60)
    summary = analytics.get_portfolio_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:,.2f}")
        else:
            print(f"{key}: {value:,}")

    print("\n" + "=" * 60)
    print("TOP 10 EXPOSURES")
    print("=" * 60)
    print(analytics.get_top_exposures().to_string())

    print("\n" + "=" * 60)
    print("INDUSTRY CONCENTRATION")
    print("=" * 60)
    print(analytics.get_industry_concentration().to_string())

    print("\n" + "=" * 60)
    print("NPL METRICS")
    print("=" * 60)
    npl = analytics.calculate_npl_ratio()
    for key, value in npl.items():
        print(f"{key}: {value:,.2f}")
