"""
Regulatory Reporting Module for Credit Risk Monitoring System
IFRS 9 ECL Calculation and Basel III/IV Capital Requirements
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import RiskParameters, IFRS9, RegulatoryConfig
from src.database import DatabaseManager


class IFRS9Stage(Enum):
    """IFRS 9 Classification Stages."""
    STAGE_1 = 1  # Performing - 12-month ECL
    STAGE_2 = 2  # Underperforming - Lifetime ECL
    STAGE_3 = 3  # Non-performing/Credit-impaired - Lifetime ECL


@dataclass
class ECLResult:
    """Results of ECL calculation for a contract."""
    vertrag_id: int
    kunden_id: int
    stage: IFRS9Stage
    ead: float
    pd_12m: float
    pd_lifetime: float
    lgd: float
    ecl_12m: float
    ecl_lifetime: float
    final_ecl: float
    discount_factor: float


@dataclass
class CapitalRequirement:
    """Basel III/IV Capital Requirements."""
    total_exposure: float
    total_rwa: float
    credit_risk_rwa: float
    market_risk_rwa: float
    operational_risk_rwa: float
    cet1_requirement: float
    tier1_requirement: float
    total_capital_requirement: float
    capital_buffers: Dict[str, float]


class RegulatoryReporting:
    """
    Regulatory Reporting for Credit Risk.

    Implements:
    - IFRS 9 Expected Credit Loss (ECL) calculation
    - Basel III/IV Capital Requirements
    - Large Exposure Reporting
    - Regulatory templates
    """

    def __init__(self, db: DatabaseManager):
        """
        Initialize Regulatory Reporting.

        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.reporting_date = date.today()

    def set_reporting_date(self, reporting_date: date):
        """Set the reporting date for calculations."""
        self.reporting_date = reporting_date

    # =========================================================================
    # IFRS 9 ECL CALCULATION
    # =========================================================================

    def classify_stage(self, contract: Dict) -> IFRS9Stage:
        """
        Classify contract into IFRS 9 stage.

        Args:
            contract: Contract data dictionary

        Returns:
            IFRS9Stage classification
        """
        # Stage 3: Credit-impaired
        if contract.get('vertrag_status') == 'ausfall':
            return IFRS9Stage.STAGE_3

        # Check days past due
        dpd = contract.get('max_verspaetung', 0) or 0
        if dpd > IFRS9.STAGE_2_MAX_DPD:
            return IFRS9Stage.STAGE_3
        elif dpd > IFRS9.STAGE_1_MAX_DPD:
            return IFRS9Stage.STAGE_2

        # Check for significant increase in credit risk (SICR)
        pd_current = contract.get('pd_wert', 0.01) or 0.01
        pd_original = pd_current * 0.7  # Simplified: assume original was lower

        if pd_current - pd_original > IFRS9.SIGNIFICANT_INCREASE_THRESHOLD:
            return IFRS9Stage.STAGE_2

        # Check rating deterioration
        rating = contract.get('kreditrating', 'BBB')
        high_risk_ratings = ['CCC', 'CC', 'C', 'D']
        if rating in high_risk_ratings:
            return IFRS9Stage.STAGE_2 if rating != 'D' else IFRS9Stage.STAGE_3

        return IFRS9Stage.STAGE_1

    def calculate_lifetime_pd(self, pd_12m: float, remaining_months: int) -> float:
        """
        Calculate lifetime PD from 12-month PD.

        Args:
            pd_12m: 12-month PD
            remaining_months: Remaining contract lifetime in months

        Returns:
            Lifetime PD
        """
        if remaining_months <= 12:
            return pd_12m

        # Simplified: cumulative PD using constant hazard rate
        monthly_survival = (1 - pd_12m) ** (1/12)
        lifetime_survival = monthly_survival ** remaining_months
        lifetime_pd = 1 - lifetime_survival

        return min(1.0, lifetime_pd)

    def calculate_discount_factor(self, remaining_months: int,
                                  effective_rate: float) -> float:
        """
        Calculate discount factor for ECL.

        Args:
            remaining_months: Remaining lifetime
            effective_rate: Effective interest rate

        Returns:
            Average discount factor
        """
        if remaining_months <= 0:
            return 1.0

        monthly_rate = effective_rate / 12
        total_discount = 0

        for month in range(1, remaining_months + 1):
            total_discount += 1 / ((1 + monthly_rate) ** month)

        return total_discount / remaining_months if remaining_months > 0 else 1.0

    def calculate_ecl_single(self, contract: Dict) -> ECLResult:
        """
        Calculate ECL for a single contract.

        Args:
            contract: Contract data dictionary

        Returns:
            ECLResult with ECL details
        """
        # Determine stage
        stage = self.classify_stage(contract)

        # Get parameters
        ead = contract.get('ead_wert') or contract.get('restschuld', 0)
        pd_12m = contract.get('pd_wert', 0.01)
        lgd = contract.get('lgd_wert', 0.45)
        zinssatz = contract.get('zinssatz', 0.05)
        remaining_months = contract.get('remaining_months', 36)

        # Calculate lifetime PD
        pd_lifetime = self.calculate_lifetime_pd(pd_12m, remaining_months)

        # Calculate discount factor
        discount_factor = self.calculate_discount_factor(remaining_months, zinssatz)

        # Calculate ECL
        ecl_12m = ead * pd_12m * lgd * discount_factor
        ecl_lifetime = ead * pd_lifetime * lgd * discount_factor

        # Final ECL based on stage
        if stage == IFRS9Stage.STAGE_1:
            final_ecl = ecl_12m
        else:
            final_ecl = ecl_lifetime

        return ECLResult(
            vertrag_id=contract.get('vertrag_id', 0),
            kunden_id=contract.get('kunden_id', 0),
            stage=stage,
            ead=ead,
            pd_12m=pd_12m,
            pd_lifetime=pd_lifetime,
            lgd=lgd,
            ecl_12m=ecl_12m,
            ecl_lifetime=ecl_lifetime,
            final_ecl=final_ecl,
            discount_factor=discount_factor
        )

    def calculate_portfolio_ecl(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Calculate ECL for entire portfolio.

        Returns:
            Tuple of (DataFrame with ECL details, summary dict)
        """
        query = """
        SELECT
            v.vertrag_id,
            v.kunden_id,
            k.name as kunde,
            k.kreditrating,
            k.branche,
            v.produkt_typ,
            v.restschuld,
            v.kreditlimit,
            v.ead_wert,
            v.pd_wert,
            v.lgd_wert,
            v.zinssatz,
            v.laufzeit_monate,
            v.vertrag_status,
            v.vertragsdatum,
            MAX(z.verspaetung_tage) as max_verspaetung
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        LEFT JOIN zahlungen z ON v.vertrag_id = z.vertrag_id
        WHERE v.vertrag_status IN ('aktiv', 'gekuendigt', 'ausfall')
        GROUP BY v.vertrag_id
        """

        portfolio = self.db.execute_dataframe(query)

        if portfolio.empty:
            return pd.DataFrame(), {}

        # Calculate remaining months
        portfolio['vertragsdatum'] = pd.to_datetime(portfolio['vertragsdatum'])
        portfolio['end_date'] = portfolio['vertragsdatum'] + pd.to_timedelta(portfolio['laufzeit_monate'] * 30, unit='D')
        portfolio['remaining_months'] = ((portfolio['end_date'] - pd.Timestamp.now()).dt.days / 30).clip(lower=1).astype(int)

        # Calculate ECL for each contract
        ecl_results = []
        for _, row in portfolio.iterrows():
            result = self.calculate_ecl_single(row.to_dict())
            ecl_results.append({
                'vertrag_id': result.vertrag_id,
                'kunden_id': result.kunden_id,
                'kunde': row['kunde'],
                'branche': row['branche'],
                'kreditrating': row['kreditrating'],
                'produkt_typ': row['produkt_typ'],
                'stage': result.stage.value,
                'ead': result.ead,
                'pd_12m': result.pd_12m,
                'pd_lifetime': result.pd_lifetime,
                'lgd': result.lgd,
                'ecl_12m': result.ecl_12m,
                'ecl_lifetime': result.ecl_lifetime,
                'final_ecl': result.final_ecl
            })

        ecl_df = pd.DataFrame(ecl_results)

        # Summary statistics
        summary = {
            'reporting_date': self.reporting_date.isoformat(),
            'total_contracts': len(ecl_df),
            'total_ead': ecl_df['ead'].sum(),
            'total_ecl': ecl_df['final_ecl'].sum(),
            'ecl_ratio': ecl_df['final_ecl'].sum() / ecl_df['ead'].sum() * 100 if ecl_df['ead'].sum() > 0 else 0,
            'stage_1_count': len(ecl_df[ecl_df['stage'] == 1]),
            'stage_1_ead': ecl_df[ecl_df['stage'] == 1]['ead'].sum(),
            'stage_1_ecl': ecl_df[ecl_df['stage'] == 1]['final_ecl'].sum(),
            'stage_2_count': len(ecl_df[ecl_df['stage'] == 2]),
            'stage_2_ead': ecl_df[ecl_df['stage'] == 2]['ead'].sum(),
            'stage_2_ecl': ecl_df[ecl_df['stage'] == 2]['final_ecl'].sum(),
            'stage_3_count': len(ecl_df[ecl_df['stage'] == 3]),
            'stage_3_ead': ecl_df[ecl_df['stage'] == 3]['ead'].sum(),
            'stage_3_ecl': ecl_df[ecl_df['stage'] == 3]['final_ecl'].sum(),
            'avg_pd': ecl_df['pd_12m'].mean(),
            'avg_lgd': ecl_df['lgd'].mean()
        }

        return ecl_df, summary

    def generate_ifrs9_report(self) -> Dict[str, pd.DataFrame]:
        """
        Generate complete IFRS 9 report.

        Returns:
            Dictionary of DataFrames for different report sections
        """
        ecl_df, summary = self.calculate_portfolio_ecl()

        if ecl_df.empty:
            return {}

        # Stage distribution
        stage_dist = ecl_df.groupby('stage').agg({
            'vertrag_id': 'count',
            'ead': 'sum',
            'final_ecl': 'sum'
        }).reset_index()
        stage_dist.columns = ['Stage', 'Anzahl', 'EAD', 'ECL']
        stage_dist['Coverage Ratio %'] = stage_dist['ECL'] / stage_dist['EAD'] * 100

        # By rating
        rating_report = ecl_df.groupby('kreditrating').agg({
            'vertrag_id': 'count',
            'ead': 'sum',
            'final_ecl': 'sum',
            'pd_12m': 'mean',
            'lgd': 'mean'
        }).reset_index()
        rating_report.columns = ['Rating', 'Anzahl', 'EAD', 'ECL', 'Avg PD', 'Avg LGD']

        # By industry
        industry_report = ecl_df.groupby('branche').agg({
            'vertrag_id': 'count',
            'ead': 'sum',
            'final_ecl': 'sum'
        }).reset_index()
        industry_report.columns = ['Branche', 'Anzahl', 'EAD', 'ECL']
        industry_report['Coverage %'] = industry_report['ECL'] / industry_report['EAD'] * 100

        # Stage movement (simplified - would need historical data)
        stage_movement = pd.DataFrame({
            'Von Stage': [1, 1, 2, 2, 3],
            'Nach Stage': [2, 3, 1, 3, 2],
            'Anzahl': [0, 0, 0, 0, 0],  # Placeholder
            'EAD': [0, 0, 0, 0, 0]
        })

        return {
            'summary': pd.DataFrame([summary]),
            'stage_distribution': stage_dist,
            'rating_breakdown': rating_report,
            'industry_breakdown': industry_report,
            'stage_movement': stage_movement,
            'detail': ecl_df
        }

    # =========================================================================
    # BASEL III/IV CAPITAL REQUIREMENTS
    # =========================================================================

    def get_risk_weight(self, rating: str, exposure_type: str = 'corporate') -> float:
        """
        Get Basel III standardized risk weight.

        Args:
            rating: Credit rating
            exposure_type: Type of exposure

        Returns:
            Risk weight as decimal
        """
        # Basel III Standardized Approach risk weights
        corporate_weights = {
            'AAA': 0.20, 'AA+': 0.20, 'AA': 0.20, 'AA-': 0.20,
            'A+': 0.50, 'A': 0.50, 'A-': 0.50,
            'BBB+': 0.75, 'BBB': 1.00, 'BBB-': 1.00,
            'BB+': 1.00, 'BB': 1.00, 'BB-': 1.00,
            'B+': 1.50, 'B': 1.50, 'B-': 1.50,
            'CCC': 1.50, 'CC': 1.50, 'C': 1.50, 'D': 1.50,
            'unrated': 1.00
        }

        retail_weights = {
            'residential_mortgage': 0.35,
            'other_retail': 0.75
        }

        if exposure_type == 'retail':
            return 0.75
        elif exposure_type == 'mortgage':
            return 0.35

        return corporate_weights.get(rating, 1.00)

    def calculate_credit_risk_rwa(self) -> pd.DataFrame:
        """
        Calculate Risk-Weighted Assets for credit risk.

        Returns:
            DataFrame with RWA details
        """
        query = """
        SELECT
            v.vertrag_id,
            k.kunden_id,
            k.name,
            k.kreditrating,
            k.kunden_segment,
            v.produkt_typ,
            v.restschuld as exposure,
            v.sicherheiten_wert,
            v.sicherheiten_typ,
            v.ead_wert
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        """

        df = self.db.execute_dataframe(query)

        if df.empty:
            return pd.DataFrame()

        # Calculate net exposure (after collateral haircuts)
        collateral_haircuts = {
            'Immobilie': 0.30,
            'Finanzielle_Sicherheit': 0.10,
            'Buergschaft': 0.20,
            'Warenlager': 0.40,
            'Forderungen': 0.35,
            'Keine': 1.00,
            'Sonstige': 0.50
        }

        df['collateral_haircut'] = df['sicherheiten_typ'].map(collateral_haircuts).fillna(0.50)
        df['eligible_collateral'] = df['sicherheiten_wert'] * (1 - df['collateral_haircut'])
        df['net_exposure'] = (df['ead_wert'] - df['eligible_collateral']).clip(lower=0)

        # Determine exposure type
        df['exposure_type'] = df.apply(
            lambda row: 'mortgage' if row['produkt_typ'] == 'Hypothek'
                       else ('retail' if row['kunden_segment'] == 'retail' else 'corporate'),
            axis=1
        )

        # Get risk weights
        df['risk_weight'] = df.apply(
            lambda row: self.get_risk_weight(row['kreditrating'], row['exposure_type']),
            axis=1
        )

        # Calculate RWA
        df['rwa'] = df['net_exposure'] * df['risk_weight']

        return df[['vertrag_id', 'kunden_id', 'name', 'kreditrating', 'exposure_type',
                   'exposure', 'eligible_collateral', 'net_exposure', 'risk_weight', 'rwa']]

    def calculate_capital_requirements(self) -> CapitalRequirement:
        """
        Calculate Basel III capital requirements.

        Returns:
            CapitalRequirement dataclass
        """
        # Credit Risk RWA
        rwa_df = self.calculate_credit_risk_rwa()
        credit_risk_rwa = rwa_df['rwa'].sum() if not rwa_df.empty else 0
        total_exposure = rwa_df['exposure'].sum() if not rwa_df.empty else 0

        # Market Risk RWA (simplified - typically 5-10% of credit risk for banks)
        market_risk_rwa = credit_risk_rwa * 0.05

        # Operational Risk RWA (Basic Indicator Approach - simplified)
        # Typically 15% of average gross income over 3 years
        # Simplified: 8% of credit risk RWA
        operational_risk_rwa = credit_risk_rwa * 0.08

        total_rwa = credit_risk_rwa + market_risk_rwa + operational_risk_rwa

        # Capital requirements
        cet1_requirement = total_rwa * RegulatoryConfig.CET1_RATIO
        tier1_requirement = total_rwa * RegulatoryConfig.TIER1_RATIO
        total_capital_requirement = total_rwa * RegulatoryConfig.MIN_CAPITAL_RATIO

        # Capital buffers
        capital_buffers = {
            'conservation_buffer': total_rwa * 0.025,  # 2.5%
            'countercyclical_buffer': total_rwa * 0.0,  # Variable, assume 0
            'systemic_buffer': total_rwa * 0.0  # For G-SIBs/D-SIBs
        }

        return CapitalRequirement(
            total_exposure=total_exposure,
            total_rwa=total_rwa,
            credit_risk_rwa=credit_risk_rwa,
            market_risk_rwa=market_risk_rwa,
            operational_risk_rwa=operational_risk_rwa,
            cet1_requirement=cet1_requirement,
            tier1_requirement=tier1_requirement,
            total_capital_requirement=total_capital_requirement,
            capital_buffers=capital_buffers
        )

    # =========================================================================
    # LARGE EXPOSURE REPORTING
    # =========================================================================

    def generate_large_exposure_report(self, capital_base: float = None) -> pd.DataFrame:
        """
        Generate large exposure report.

        Args:
            capital_base: Institution's capital base (for threshold calculation)

        Returns:
            DataFrame with large exposures
        """
        # Get capital requirements to determine threshold
        if capital_base is None:
            cap_req = self.calculate_capital_requirements()
            capital_base = cap_req.total_capital_requirement / RegulatoryConfig.MIN_CAPITAL_RATIO

        # Large exposure threshold (10% of capital)
        threshold = capital_base * RegulatoryConfig.LARGE_EXPOSURE_THRESHOLD
        absolute_limit = capital_base * RegulatoryConfig.LARGE_EXPOSURE_ABSOLUTE_LIMIT

        query = """
        SELECT
            k.kunden_id,
            k.name,
            k.branche,
            k.kreditrating,
            k.kunden_segment,
            SUM(v.restschuld) as brutto_exposure,
            SUM(v.sicherheiten_wert) as sicherheiten,
            SUM(v.restschuld) - SUM(v.sicherheiten_wert) as netto_exposure,
            COUNT(v.vertrag_id) as anzahl_vertraege
        FROM kunden k
        JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
        WHERE v.vertrag_status = 'aktiv'
        GROUP BY k.kunden_id
        ORDER BY brutto_exposure DESC
        """

        df = self.db.execute_dataframe(query)

        if df.empty:
            return pd.DataFrame()

        df['capital_base'] = capital_base
        df['threshold'] = threshold
        df['exposure_ratio'] = df['brutto_exposure'] / capital_base * 100
        df['is_large_exposure'] = df['brutto_exposure'] >= threshold
        df['exceeds_limit'] = df['brutto_exposure'] > absolute_limit
        df['limit_headroom'] = absolute_limit - df['brutto_exposure']

        # Filter to large exposures only
        large_exposures = df[df['is_large_exposure']].copy()

        return large_exposures

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================

    def generate_regulatory_report(self, output_path: Path) -> None:
        """
        Generate comprehensive regulatory report as Excel file.

        Args:
            output_path: Path for output file
        """
        print(f"Generating regulatory report for {self.reporting_date}...")

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # IFRS 9 Report
            ifrs9_reports = self.generate_ifrs9_report()
            if ifrs9_reports:
                for name, df in ifrs9_reports.items():
                    sheet_name = f'IFRS9_{name}'[:31]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Capital Requirements
            cap_req = self.calculate_capital_requirements()
            cap_df = pd.DataFrame([{
                'Metric': 'Total Exposure',
                'Value': cap_req.total_exposure,
                'Unit': 'EUR'
            }, {
                'Metric': 'Total RWA',
                'Value': cap_req.total_rwa,
                'Unit': 'EUR'
            }, {
                'Metric': 'Credit Risk RWA',
                'Value': cap_req.credit_risk_rwa,
                'Unit': 'EUR'
            }, {
                'Metric': 'Market Risk RWA',
                'Value': cap_req.market_risk_rwa,
                'Unit': 'EUR'
            }, {
                'Metric': 'Operational Risk RWA',
                'Value': cap_req.operational_risk_rwa,
                'Unit': 'EUR'
            }, {
                'Metric': 'RWA Density',
                'Value': cap_req.total_rwa / cap_req.total_exposure * 100 if cap_req.total_exposure > 0 else 0,
                'Unit': '%'
            }, {
                'Metric': 'CET1 Requirement',
                'Value': cap_req.cet1_requirement,
                'Unit': 'EUR'
            }, {
                'Metric': 'Tier 1 Requirement',
                'Value': cap_req.tier1_requirement,
                'Unit': 'EUR'
            }, {
                'Metric': 'Total Capital Requirement',
                'Value': cap_req.total_capital_requirement,
                'Unit': 'EUR'
            }])
            cap_df.to_excel(writer, sheet_name='Capital_Requirements', index=False)

            # RWA Details
            rwa_df = self.calculate_credit_risk_rwa()
            if not rwa_df.empty:
                # Summary by rating
                rwa_summary = rwa_df.groupby('kreditrating').agg({
                    'exposure': 'sum',
                    'net_exposure': 'sum',
                    'rwa': 'sum',
                    'vertrag_id': 'count'
                }).reset_index()
                rwa_summary.columns = ['Rating', 'Brutto Exposure', 'Netto Exposure', 'RWA', 'Anzahl']
                rwa_summary['RWA Density %'] = rwa_summary['RWA'] / rwa_summary['Netto Exposure'] * 100
                rwa_summary.to_excel(writer, sheet_name='RWA_by_Rating', index=False)

            # Large Exposures
            large_exp = self.generate_large_exposure_report()
            if not large_exp.empty:
                large_exp.to_excel(writer, sheet_name='Large_Exposures', index=False)

        print(f"Regulatory report saved to: {output_path}")

    def print_capital_summary(self):
        """Print capital requirements summary."""
        cap_req = self.calculate_capital_requirements()

        print("\n" + "=" * 60)
        print("BASEL III CAPITAL REQUIREMENTS")
        print("=" * 60)
        print(f"Reporting Date: {self.reporting_date}")

        print(f"\nRisk-Weighted Assets:")
        print(f"  Credit Risk RWA:      {cap_req.credit_risk_rwa:>18,.2f} EUR")
        print(f"  Market Risk RWA:      {cap_req.market_risk_rwa:>18,.2f} EUR")
        print(f"  Operational Risk RWA: {cap_req.operational_risk_rwa:>18,.2f} EUR")
        print(f"  Total RWA:            {cap_req.total_rwa:>18,.2f} EUR")

        print(f"\nCapital Requirements:")
        print(f"  CET1 (4.5%):          {cap_req.cet1_requirement:>18,.2f} EUR")
        print(f"  Tier 1 (6%):          {cap_req.tier1_requirement:>18,.2f} EUR")
        print(f"  Total Capital (8%):   {cap_req.total_capital_requirement:>18,.2f} EUR")

        print(f"\nCapital Buffers:")
        for buffer_name, amount in cap_req.capital_buffers.items():
            print(f"  {buffer_name}: {amount:>18,.2f} EUR")

        rwa_density = (cap_req.total_rwa / cap_req.total_exposure * 100
                      if cap_req.total_exposure > 0 else 0)
        print(f"\nRWA Density: {rwa_density:.2f}%")

    def print_ifrs9_summary(self):
        """Print IFRS 9 ECL summary."""
        ecl_df, summary = self.calculate_portfolio_ecl()

        if not summary:
            print("No IFRS 9 data available")
            return

        print("\n" + "=" * 60)
        print("IFRS 9 EXPECTED CREDIT LOSS SUMMARY")
        print("=" * 60)
        print(f"Reporting Date: {summary['reporting_date']}")
        print(f"Total Contracts: {summary['total_contracts']:,}")

        print(f"\nPortfolio Overview:")
        print(f"  Total EAD:     {summary['total_ead']:>18,.2f} EUR")
        print(f"  Total ECL:     {summary['total_ecl']:>18,.2f} EUR")
        print(f"  ECL Ratio:     {summary['ecl_ratio']:>17.2f} %")

        print(f"\nStage Distribution:")
        print(f"  Stage 1 (Performing):")
        print(f"    Contracts: {summary['stage_1_count']:>10,}")
        print(f"    EAD:       {summary['stage_1_ead']:>18,.2f} EUR")
        print(f"    ECL:       {summary['stage_1_ecl']:>18,.2f} EUR")

        print(f"  Stage 2 (Underperforming):")
        print(f"    Contracts: {summary['stage_2_count']:>10,}")
        print(f"    EAD:       {summary['stage_2_ead']:>18,.2f} EUR")
        print(f"    ECL:       {summary['stage_2_ecl']:>18,.2f} EUR")

        print(f"  Stage 3 (Non-Performing):")
        print(f"    Contracts: {summary['stage_3_count']:>10,}")
        print(f"    EAD:       {summary['stage_3_ead']:>18,.2f} EUR")
        print(f"    ECL:       {summary['stage_3_ecl']:>18,.2f} EUR")

        print(f"\nAverage Risk Parameters:")
        print(f"  Average PD:  {summary['avg_pd']*100:>10.4f} %")
        print(f"  Average LGD: {summary['avg_lgd']*100:>10.2f} %")


if __name__ == "__main__":
    from src.database import get_demo_db

    db = get_demo_db()
    reporting = RegulatoryReporting(db)

    # Print summaries
    reporting.print_capital_summary()
    reporting.print_ifrs9_summary()

    # Generate large exposure report
    print("\n" + "=" * 60)
    print("LARGE EXPOSURE REPORT")
    print("=" * 60)
    large_exp = reporting.generate_large_exposure_report()
    if not large_exp.empty:
        print(f"Found {len(large_exp)} large exposures")
        print(large_exp[['name', 'brutto_exposure', 'exposure_ratio', 'exceeds_limit']].to_string())
    else:
        print("No large exposures found")
