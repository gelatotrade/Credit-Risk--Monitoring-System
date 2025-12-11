"""
Kreditrisiko-Überwachungssystem - Configuration
Credit Risk Monitoring System Configuration
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEMO_DATA_DIR = DATA_DIR / "demo"
REAL_DATA_DIR = DATA_DIR / "real"
EXCEL_DIR = DATA_DIR / "excel_templates"
REPORTS_DIR = BASE_DIR / "reports"
DASHBOARDS_DIR = BASE_DIR / "dashboards"

# Database Configuration
class DatabaseConfig:
    DEMO_DB_PATH = DEMO_DATA_DIR / "kreditrisiko_demo.db"
    REAL_DB_PATH = REAL_DATA_DIR / "kreditrisiko_real.db"
    SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"

# Risk Parameters - Based on Basel III/IV Standards
class RiskParameters:
    # Rating Scores (PD estimates based on rating)
    RATING_PD = {
        'AAA': 0.0001,
        'AA+': 0.0002,
        'AA': 0.0003,
        'AA-': 0.0005,
        'A+': 0.0008,
        'A': 0.0012,
        'A-': 0.0018,
        'BBB+': 0.0028,
        'BBB': 0.0045,
        'BBB-': 0.0075,
        'BB+': 0.012,
        'BB': 0.02,
        'BB-': 0.035,
        'B+': 0.055,
        'B': 0.09,
        'B-': 0.14,
        'CCC+': 0.20,
        'CCC': 0.28,
        'CCC-': 0.38,
        'CC': 0.50,
        'C': 0.65,
        'D': 1.0
    }

    # Risk Weights for Capital Calculation (Basel III Standardized Approach)
    RISK_WEIGHTS = {
        'AAA': 0.20,
        'AA': 0.20,
        'A': 0.50,
        'BBB': 0.100,
        'BB': 1.00,
        'B': 1.50,
        'CCC': 1.50,
        'unrated': 1.00
    }

    # LGD estimates by collateral type
    LGD_BY_COLLATERAL = {
        'Immobilie': 0.25,
        'Finanzielle_Sicherheit': 0.15,
        'Buergschaft': 0.35,
        'Warenlager': 0.50,
        'Forderungen': 0.45,
        'Keine': 0.65,
        'Sonstige': 0.55
    }

    # Industry risk multipliers (for stress testing)
    INDUSTRY_RISK_MULTIPLIER = {
        'Automobilbau': 1.3,
        'Baugewerbe': 1.4,
        'Chemie': 1.1,
        'Einzelhandel': 1.2,
        'Energie': 0.9,
        'Finanzdienstleistungen': 1.0,
        'Gesundheitswesen': 0.8,
        'Handel': 1.1,
        'Immobilien': 1.3,
        'IT_Technologie': 1.2,
        'Lebensmittel': 0.9,
        'Logistik': 1.1,
        'Maschinenbau': 1.2,
        'Pharma': 0.8,
        'Tourismus': 1.5,
        'Sonstige': 1.0
    }

# Concentration Limits (in percentage of total portfolio)
class ConcentrationLimits:
    SINGLE_CUSTOMER_MAX = 10.0  # Max 10% per customer
    INDUSTRY_MAX = 30.0  # Max 30% per industry
    REGION_MAX = 40.0  # Max 40% per region
    PRODUCT_MAX = 50.0  # Max 50% per product type

    # Warning thresholds (percentage of limit)
    WARNING_THRESHOLD = 80.0
    CRITICAL_THRESHOLD = 95.0

# IFRS 9 Stage Classification
class IFRS9:
    # Days past due for stage classification
    STAGE_1_MAX_DPD = 30  # Performing
    STAGE_2_MIN_DPD = 31  # Underperforming
    STAGE_2_MAX_DPD = 90
    STAGE_3_MIN_DPD = 91  # Non-performing

    # ECL calculation parameters
    ECL_DISCOUNT_RATE = 0.05  # Effective interest rate for discounting

    # Staging criteria thresholds
    SIGNIFICANT_INCREASE_THRESHOLD = 0.02  # PD increase for Stage 2

# Regulatory Reporting
class RegulatoryConfig:
    # Capital requirements (simplified)
    MIN_CAPITAL_RATIO = 0.08  # 8% minimum
    CET1_RATIO = 0.045  # 4.5% Common Equity Tier 1
    TIER1_RATIO = 0.06  # 6% Tier 1

    # Large Exposure limits
    LARGE_EXPOSURE_THRESHOLD = 0.10  # 10% of capital
    LARGE_EXPOSURE_ABSOLUTE_LIMIT = 0.25  # 25% max

# Demo Data Generation Settings
class DemoConfig:
    NUM_CUSTOMERS = 500
    NUM_CONTRACTS = 1500
    NUM_PAYMENTS = 10000
    NUM_DEFAULTS = 75

    # German regions for demo data
    REGIONS = [
        'Bayern', 'Baden-Württemberg', 'Nordrhein-Westfalen', 'Hessen',
        'Niedersachsen', 'Sachsen', 'Rheinland-Pfalz', 'Berlin',
        'Hamburg', 'Schleswig-Holstein', 'Brandenburg', 'Thüringen',
        'Sachsen-Anhalt', 'Mecklenburg-Vorpommern', 'Bremen', 'Saarland'
    ]

    # Industries
    INDUSTRIES = [
        'Automobilbau', 'Baugewerbe', 'Chemie', 'Einzelhandel', 'Energie',
        'Finanzdienstleistungen', 'Gesundheitswesen', 'Handel', 'Immobilien',
        'IT_Technologie', 'Lebensmittel', 'Logistik', 'Maschinenbau',
        'Pharma', 'Tourismus'
    ]

    # Product types
    PRODUCT_TYPES = [
        'Darlehen', 'Kreditlinie', 'Hypothek', 'Leasing',
        'Factoring', 'Avalkredit', 'Betriebsmittelkredit'
    ]

    # Ratings distribution (weighted)
    RATING_DISTRIBUTION = {
        'AAA': 0.02, 'AA': 0.05, 'A': 0.15, 'BBB': 0.30,
        'BB': 0.25, 'B': 0.15, 'CCC': 0.06, 'CC': 0.015, 'C': 0.005
    }

# Economic Data Sources (for real data fetching)
class DataSources:
    ECB_BASE_URL = "https://sdw-wsrest.ecb.europa.eu/service"
    EUROSTAT_URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
    BUNDESBANK_URL = "https://api.statistik-nord.de"

    # Fallback data in case APIs are unavailable
    DEFAULT_INTEREST_RATE = 0.04
    DEFAULT_INFLATION = 0.025
    DEFAULT_UNEMPLOYMENT = 0.055
