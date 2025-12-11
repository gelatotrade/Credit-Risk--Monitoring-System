"""
Stress Testing Module for Credit Risk Monitoring System
Simulates various adverse scenarios to assess portfolio resilience.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import RiskParameters, IFRS9
from src.database import DatabaseManager


class ScenarioType(Enum):
    """Types of stress scenarios."""
    INTEREST_RATE = "Zinsänderung"
    RECESSION = "Rezession"
    INDUSTRY_SHOCK = "Branchenschock"
    COMBINED = "Kombiniertes Szenario"
    CUSTOM = "Benutzerdefiniert"


@dataclass
class StressScenario:
    """Definition of a stress scenario."""
    name: str
    scenario_type: ScenarioType
    description: str
    pd_multiplier: float  # Multiplier for PD
    lgd_adjustment: float  # Adjustment to LGD (additive)
    interest_rate_shock: float  # bps change
    industry_shocks: Dict[str, float]  # Industry-specific PD multipliers
    regional_shocks: Dict[str, float]  # Region-specific multipliers


@dataclass
class StressTestResult:
    """Results of a stress test."""
    scenario: StressScenario
    baseline_ecl: float
    stressed_ecl: float
    ecl_increase: float
    ecl_increase_percent: float
    baseline_rwa: float
    stressed_rwa: float
    capital_impact: float
    affected_contracts: int
    stage_migration: Dict[str, int]
    industry_breakdown: pd.DataFrame
    rating_breakdown: pd.DataFrame


class StressTesting:
    """
    Stress Testing Framework for Credit Risk.

    Scenarios:
    - Interest rate shock (+200bps)
    - Recession (default rate +3%)
    - Industry-specific shocks
    - Combined scenarios
    """

    # Pre-defined scenarios
    PREDEFINED_SCENARIOS = {
        'interest_rate_200bps': StressScenario(
            name="Zinserhöhung +200bps",
            scenario_type=ScenarioType.INTEREST_RATE,
            description="Simulation einer plötzlichen Zinserhöhung um 200 Basispunkte",
            pd_multiplier=1.3,  # 30% higher PD due to debt servicing stress
            lgd_adjustment=0.05,  # 5% higher LGD
            interest_rate_shock=0.02,  # 200bps
            industry_shocks={
                'Immobilien': 1.5,
                'Baugewerbe': 1.4,
                'Einzelhandel': 1.2
            },
            regional_shocks={}
        ),
        'recession_mild': StressScenario(
            name="Milde Rezession",
            scenario_type=ScenarioType.RECESSION,
            description="Mildes Rezessionsszenario mit moderater Ausfallratenerhöhung",
            pd_multiplier=1.5,  # 50% higher PD
            lgd_adjustment=0.08,  # 8% higher LGD
            interest_rate_shock=0,
            industry_shocks={
                'Tourismus': 2.0,
                'Einzelhandel': 1.8,
                'Automobilbau': 1.6,
                'Baugewerbe': 1.5
            },
            regional_shocks={}
        ),
        'recession_severe': StressScenario(
            name="Schwere Rezession",
            scenario_type=ScenarioType.RECESSION,
            description="Schweres Rezessionsszenario (Ausfallrate +3%)",
            pd_multiplier=2.5,  # 150% higher PD
            lgd_adjustment=0.15,  # 15% higher LGD
            interest_rate_shock=-0.01,  # Rates typically fall
            industry_shocks={
                'Tourismus': 3.5,
                'Einzelhandel': 2.5,
                'Automobilbau': 2.8,
                'Baugewerbe': 3.0,
                'Immobilien': 2.5,
                'Logistik': 2.0
            },
            regional_shocks={
                'Berlin': 1.3,
                'Bremen': 1.4,
                'Mecklenburg-Vorpommern': 1.5
            }
        ),
        'industry_auto': StressScenario(
            name="Automobilkrise",
            scenario_type=ScenarioType.INDUSTRY_SHOCK,
            description="Krise in der Automobilindustrie und Zulieferern",
            pd_multiplier=1.0,  # Base unchanged
            lgd_adjustment=0,
            interest_rate_shock=0,
            industry_shocks={
                'Automobilbau': 3.0,
                'Maschinenbau': 1.8,
                'Logistik': 1.5,
                'Chemie': 1.3
            },
            regional_shocks={
                'Baden-Württemberg': 1.3,
                'Bayern': 1.2,
                'Niedersachsen': 1.3
            }
        ),
        'industry_real_estate': StressScenario(
            name="Immobilienkrise",
            scenario_type=ScenarioType.INDUSTRY_SHOCK,
            description="Krise im Immobiliensektor",
            pd_multiplier=1.0,
            lgd_adjustment=0.10,  # Higher LGD as collateral values drop
            interest_rate_shock=0,
            industry_shocks={
                'Immobilien': 3.5,
                'Baugewerbe': 2.5,
                'Finanzdienstleistungen': 1.5
            },
            regional_shocks={}
        ),
        'combined_severe': StressScenario(
            name="Kombiniertes Stressszenario",
            scenario_type=ScenarioType.COMBINED,
            description="Kombination aus Zinserhöhung und Rezession",
            pd_multiplier=3.0,
            lgd_adjustment=0.20,
            interest_rate_shock=0.015,
            industry_shocks={
                'Immobilien': 3.0,
                'Baugewerbe': 2.8,
                'Einzelhandel': 2.5,
                'Tourismus': 3.5,
                'Automobilbau': 2.5
            },
            regional_shocks={
                'Berlin': 1.2,
                'Bremen': 1.3,
                'Sachsen-Anhalt': 1.4,
                'Mecklenburg-Vorpommern': 1.4
            }
        )
    }

    def __init__(self, db: DatabaseManager):
        """
        Initialize the Stress Testing framework.

        Args:
            db: DatabaseManager instance
        """
        self.db = db

    def get_baseline_portfolio(self) -> pd.DataFrame:
        """
        Get current portfolio data for stress testing.

        Returns:
            DataFrame with portfolio data
        """
        query = """
        SELECT
            v.vertrag_id,
            v.kunden_id,
            k.name as kunde,
            k.branche,
            k.region,
            k.kreditrating,
            v.produkt_typ,
            v.restschuld,
            v.kreditlimit,
            v.ausgenutztes_limit,
            v.zinssatz,
            v.laufzeit_monate,
            v.sicherheiten_wert,
            v.sicherheiten_typ,
            v.pd_wert,
            v.lgd_wert,
            v.ead_wert,
            v.vertrag_status,
            COALESCE(r.stufe, 1) as ifrs9_stage,
            COALESCE(r.rueckstellung_betrag, 0) as current_provision
        FROM kredit_vertraege v
        JOIN kunden k ON v.kunden_id = k.kunden_id
        LEFT JOIN rueckstellungen r ON v.vertrag_id = r.vertrag_id
            AND r.stichtag = (SELECT MAX(stichtag) FROM rueckstellungen WHERE vertrag_id = v.vertrag_id)
        WHERE v.vertrag_status IN ('aktiv', 'gekuendigt')
        """

        return self.db.execute_dataframe(query)

    def calculate_baseline_metrics(self, portfolio: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate baseline risk metrics.

        Args:
            portfolio: Portfolio DataFrame

        Returns:
            Dictionary with baseline metrics
        """
        # Expected Credit Loss
        portfolio['ecl'] = portfolio['ead_wert'] * portfolio['pd_wert'] * portfolio['lgd_wert']
        total_ecl = portfolio['ecl'].sum()

        # Risk-Weighted Assets (simplified)
        rating_weights = {
            'AAA': 0.20, 'AA': 0.20, 'A': 0.50, 'BBB': 1.00,
            'BB': 1.00, 'B': 1.50, 'CCC': 1.50, 'CC': 1.50, 'C': 1.50, 'D': 1.50
        }
        portfolio['risk_weight'] = portfolio['kreditrating'].map(rating_weights).fillna(1.0)
        portfolio['rwa'] = portfolio['ead_wert'] * portfolio['risk_weight']
        total_rwa = portfolio['rwa'].sum()

        return {
            'total_exposure': portfolio['restschuld'].sum(),
            'total_ead': portfolio['ead_wert'].sum(),
            'total_ecl': total_ecl,
            'total_rwa': total_rwa,
            'avg_pd': portfolio['pd_wert'].mean(),
            'avg_lgd': portfolio['lgd_wert'].mean(),
            'contract_count': len(portfolio),
            'stage_1_count': len(portfolio[portfolio['ifrs9_stage'] == 1]),
            'stage_2_count': len(portfolio[portfolio['ifrs9_stage'] == 2]),
            'stage_3_count': len(portfolio[portfolio['ifrs9_stage'] == 3])
        }

    def apply_stress_scenario(self, portfolio: pd.DataFrame,
                              scenario: StressScenario) -> pd.DataFrame:
        """
        Apply stress scenario to portfolio.

        Args:
            portfolio: Portfolio DataFrame
            scenario: StressScenario to apply

        Returns:
            Stressed portfolio DataFrame
        """
        stressed = portfolio.copy()

        # Apply base PD multiplier
        stressed['stressed_pd'] = stressed['pd_wert'] * scenario.pd_multiplier

        # Apply industry-specific shocks
        for industry, multiplier in scenario.industry_shocks.items():
            mask = stressed['branche'] == industry
            stressed.loc[mask, 'stressed_pd'] *= multiplier

        # Apply regional shocks
        for region, multiplier in scenario.regional_shocks.items():
            mask = stressed['region'] == region
            stressed.loc[mask, 'stressed_pd'] *= multiplier

        # Cap PD at 100%
        stressed['stressed_pd'] = stressed['stressed_pd'].clip(upper=1.0)

        # Apply LGD adjustment
        stressed['stressed_lgd'] = (stressed['lgd_wert'] + scenario.lgd_adjustment).clip(upper=1.0)

        # Interest rate impact on EAD (for floating rate loans)
        if scenario.interest_rate_shock != 0:
            # Higher rates increase debt servicing costs, potentially increasing EAD for credit lines
            rate_impact = 1 + scenario.interest_rate_shock * 2  # Simplified multiplier
            mask = stressed['produkt_typ'].isin(['Kreditlinie', 'Betriebsmittelkredit'])
            stressed.loc[mask, 'ead_wert'] *= rate_impact

        # Calculate stressed ECL
        stressed['stressed_ecl'] = stressed['ead_wert'] * stressed['stressed_pd'] * stressed['stressed_lgd']

        # Determine new IFRS 9 stage
        stressed['stressed_stage'] = stressed.apply(
            lambda row: self._determine_stage(row['stressed_pd'], row['pd_wert']), axis=1
        )

        # Calculate stressed RWA
        rating_weights = {
            'AAA': 0.20, 'AA': 0.20, 'A': 0.50, 'BBB': 1.00,
            'BB': 1.00, 'B': 1.50, 'CCC': 1.50, 'CC': 1.50, 'C': 1.50, 'D': 1.50
        }
        stressed['risk_weight'] = stressed['kreditrating'].map(rating_weights).fillna(1.0)
        # Higher PD leads to higher effective risk weight
        pd_adjustment = (stressed['stressed_pd'] / stressed['pd_wert'].clip(lower=0.0001)).clip(upper=3.0)
        stressed['stressed_rwa'] = stressed['ead_wert'] * stressed['risk_weight'] * (1 + (pd_adjustment - 1) * 0.3)

        return stressed

    def _determine_stage(self, stressed_pd: float, baseline_pd: float) -> int:
        """
        Determine IFRS 9 stage based on PD changes.

        Args:
            stressed_pd: Stressed PD value
            baseline_pd: Baseline PD value

        Returns:
            IFRS 9 stage (1, 2, or 3)
        """
        if stressed_pd >= 0.50:  # Very high default probability
            return 3
        elif stressed_pd >= 0.10:  # Significant increase
            return 3
        elif stressed_pd > baseline_pd * 2 or stressed_pd > baseline_pd + 0.02:
            return 2
        else:
            return 1

    def run_stress_test(self, scenario_name: str = None,
                        custom_scenario: StressScenario = None) -> StressTestResult:
        """
        Run a stress test.

        Args:
            scenario_name: Name of predefined scenario
            custom_scenario: Custom StressScenario object

        Returns:
            StressTestResult with analysis
        """
        if custom_scenario:
            scenario = custom_scenario
        elif scenario_name and scenario_name in self.PREDEFINED_SCENARIOS:
            scenario = self.PREDEFINED_SCENARIOS[scenario_name]
        else:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        print(f"\nRunning stress test: {scenario.name}")
        print(f"Description: {scenario.description}")

        # Get baseline portfolio
        portfolio = self.get_baseline_portfolio()
        if portfolio.empty:
            raise ValueError("No portfolio data available")

        baseline_metrics = self.calculate_baseline_metrics(portfolio)

        # Apply stress scenario
        stressed_portfolio = self.apply_stress_scenario(portfolio, scenario)

        # Calculate stressed metrics
        stressed_ecl = stressed_portfolio['stressed_ecl'].sum()
        stressed_rwa = stressed_portfolio['stressed_rwa'].sum()

        # Stage migration analysis
        stage_migration = {
            '1_to_2': len(stressed_portfolio[
                (portfolio['ifrs9_stage'] == 1) & (stressed_portfolio['stressed_stage'] == 2)
            ]),
            '1_to_3': len(stressed_portfolio[
                (portfolio['ifrs9_stage'] == 1) & (stressed_portfolio['stressed_stage'] == 3)
            ]),
            '2_to_3': len(stressed_portfolio[
                (portfolio['ifrs9_stage'] == 2) & (stressed_portfolio['stressed_stage'] == 3)
            ])
        }

        # Industry breakdown
        industry_impact = stressed_portfolio.groupby('branche').agg({
            'restschuld': 'sum',
            'ecl': 'sum',
            'stressed_ecl': 'sum',
            'vertrag_id': 'count'
        }).reset_index()
        industry_impact.columns = ['branche', 'exposure', 'baseline_ecl', 'stressed_ecl', 'contracts']
        industry_impact['ecl_increase'] = industry_impact['stressed_ecl'] - industry_impact['baseline_ecl']
        industry_impact['ecl_increase_pct'] = (
            industry_impact['ecl_increase'] / industry_impact['baseline_ecl'].clip(lower=1) * 100
        )

        # Rating breakdown
        rating_impact = stressed_portfolio.groupby('kreditrating').agg({
            'restschuld': 'sum',
            'ecl': 'sum',
            'stressed_ecl': 'sum',
            'vertrag_id': 'count'
        }).reset_index()
        rating_impact.columns = ['rating', 'exposure', 'baseline_ecl', 'stressed_ecl', 'contracts']
        rating_impact['ecl_increase'] = rating_impact['stressed_ecl'] - rating_impact['baseline_ecl']

        # Calculate capital impact (8% of RWA increase)
        capital_impact = (stressed_rwa - baseline_metrics['total_rwa']) * 0.08

        result = StressTestResult(
            scenario=scenario,
            baseline_ecl=baseline_metrics['total_ecl'],
            stressed_ecl=stressed_ecl,
            ecl_increase=stressed_ecl - baseline_metrics['total_ecl'],
            ecl_increase_percent=(stressed_ecl / baseline_metrics['total_ecl'] - 1) * 100 if baseline_metrics['total_ecl'] > 0 else 0,
            baseline_rwa=baseline_metrics['total_rwa'],
            stressed_rwa=stressed_rwa,
            capital_impact=capital_impact,
            affected_contracts=len(stressed_portfolio),
            stage_migration=stage_migration,
            industry_breakdown=industry_impact,
            rating_breakdown=rating_impact
        )

        return result

    def run_all_scenarios(self) -> Dict[str, StressTestResult]:
        """
        Run all predefined stress scenarios.

        Returns:
            Dictionary mapping scenario names to results
        """
        results = {}

        for name in self.PREDEFINED_SCENARIOS:
            try:
                results[name] = self.run_stress_test(name)
            except Exception as e:
                print(f"Error running scenario {name}: {e}")

        return results

    def generate_stress_test_report(self, results: Dict[str, StressTestResult],
                                    output_path: Path) -> None:
        """
        Generate comprehensive stress test report.

        Args:
            results: Dictionary of stress test results
            output_path: Path for output Excel file
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for name, result in results.items():
                summary_data.append({
                    'Szenario': result.scenario.name,
                    'Typ': result.scenario.scenario_type.value,
                    'Baseline ECL': result.baseline_ecl,
                    'Stressed ECL': result.stressed_ecl,
                    'ECL Anstieg': result.ecl_increase,
                    'ECL Anstieg %': result.ecl_increase_percent,
                    'Baseline RWA': result.baseline_rwa,
                    'Stressed RWA': result.stressed_rwa,
                    'Kapitaleffekt': result.capital_impact,
                    'Stage 1->2': result.stage_migration.get('1_to_2', 0),
                    'Stage 1->3': result.stage_migration.get('1_to_3', 0),
                    'Stage 2->3': result.stage_migration.get('2_to_3', 0)
                })

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Zusammenfassung', index=False)

            # Individual scenario sheets
            for name, result in results.items():
                sheet_name = name[:31]  # Excel limit

                # Combine industry and rating data
                result.industry_breakdown.to_excel(
                    writer, sheet_name=f'{sheet_name}_Ind', index=False
                )
                result.rating_breakdown.to_excel(
                    writer, sheet_name=f'{sheet_name}_Rat', index=False
                )

        print(f"Stress test report exported to: {output_path}")

    def sensitivity_analysis(self, parameter: str,
                             values: List[float]) -> pd.DataFrame:
        """
        Run sensitivity analysis varying a single parameter.

        Args:
            parameter: 'pd_multiplier', 'lgd_adjustment', or 'interest_rate_shock'
            values: List of values to test

        Returns:
            DataFrame with sensitivity results
        """
        base_scenario = self.PREDEFINED_SCENARIOS['recession_mild']
        results = []

        for value in values:
            # Create modified scenario
            modified = StressScenario(
                name=f"Sensitivity_{parameter}_{value}",
                scenario_type=ScenarioType.CUSTOM,
                description=f"Sensitivity analysis: {parameter} = {value}",
                pd_multiplier=value if parameter == 'pd_multiplier' else base_scenario.pd_multiplier,
                lgd_adjustment=value if parameter == 'lgd_adjustment' else base_scenario.lgd_adjustment,
                interest_rate_shock=value if parameter == 'interest_rate_shock' else base_scenario.interest_rate_shock,
                industry_shocks=base_scenario.industry_shocks,
                regional_shocks=base_scenario.regional_shocks
            )

            try:
                result = self.run_stress_test(custom_scenario=modified)
                results.append({
                    'parameter': parameter,
                    'value': value,
                    'baseline_ecl': result.baseline_ecl,
                    'stressed_ecl': result.stressed_ecl,
                    'ecl_increase_pct': result.ecl_increase_percent,
                    'capital_impact': result.capital_impact
                })
            except Exception as e:
                print(f"Error at {parameter}={value}: {e}")

        return pd.DataFrame(results)


def print_stress_test_result(result: StressTestResult):
    """Print formatted stress test results."""
    print("\n" + "=" * 70)
    print(f"STRESS TEST: {result.scenario.name}")
    print("=" * 70)
    print(f"Beschreibung: {result.scenario.description}")
    print(f"\nTyp: {result.scenario.scenario_type.value}")
    print(f"PD Multiplikator: {result.scenario.pd_multiplier:.2f}x")
    print(f"LGD Anpassung: +{result.scenario.lgd_adjustment*100:.1f}%")

    print("\n" + "-" * 40)
    print("ERGEBNISSE")
    print("-" * 40)
    print(f"Betroffene Verträge: {result.affected_contracts:,}")

    print(f"\nExpected Credit Loss (ECL):")
    print(f"  Baseline:   {result.baseline_ecl:>15,.2f} EUR")
    print(f"  Stressed:   {result.stressed_ecl:>15,.2f} EUR")
    print(f"  Differenz:  {result.ecl_increase:>15,.2f} EUR ({result.ecl_increase_percent:+.1f}%)")

    print(f"\nRisk-Weighted Assets (RWA):")
    print(f"  Baseline:   {result.baseline_rwa:>15,.2f} EUR")
    print(f"  Stressed:   {result.stressed_rwa:>15,.2f} EUR")

    print(f"\nKapitaleffekt: {result.capital_impact:,.2f} EUR")

    print(f"\nIFRS 9 Stage Migration:")
    print(f"  Stage 1 -> 2: {result.stage_migration.get('1_to_2', 0):,} Verträge")
    print(f"  Stage 1 -> 3: {result.stage_migration.get('1_to_3', 0):,} Verträge")
    print(f"  Stage 2 -> 3: {result.stage_migration.get('2_to_3', 0):,} Verträge")

    print(f"\nTop 5 betroffene Branchen:")
    top_industries = result.industry_breakdown.nlargest(5, 'ecl_increase')
    for _, row in top_industries.iterrows():
        print(f"  {row['branche']}: +{row['ecl_increase']:,.2f} EUR ({row['ecl_increase_pct']:+.1f}%)")


if __name__ == "__main__":
    from src.database import get_demo_db

    db = get_demo_db()
    stress_tester = StressTesting(db)

    print("=" * 70)
    print("CREDIT RISK STRESS TESTING")
    print("=" * 70)

    # Run individual scenario
    result = stress_tester.run_stress_test('recession_severe')
    print_stress_test_result(result)

    # Run all scenarios
    print("\n\nRunning all scenarios...")
    all_results = stress_tester.run_all_scenarios()

    print("\n" + "=" * 70)
    print("SCENARIO COMPARISON")
    print("=" * 70)
    print(f"{'Scenario':<30} {'ECL Increase':>15} {'% Change':>12}")
    print("-" * 60)

    for name, res in all_results.items():
        print(f"{res.scenario.name:<30} {res.ecl_increase:>15,.0f} {res.ecl_increase_percent:>11.1f}%")
