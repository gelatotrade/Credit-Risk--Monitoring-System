"""
Demo Data Generator for Credit Risk Monitoring System
Generates realistic synthetic data for testing and demonstration purposes.
"""

import random
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import DemoConfig, RiskParameters
from src.database import DatabaseManager, init_demo_database


class DemoDataGenerator:
    """Generates synthetic demo data for the Credit Risk Monitoring System."""

    def __init__(self, seed: int = 42):
        """
        Initialize the generator with a seed for reproducibility.

        Args:
            seed: Random seed for reproducibility
        """
        random.seed(seed)
        np.random.seed(seed)

        # German company name components
        self.company_prefixes = [
            'Deutsche', 'Nord', 'Süd', 'West', 'Ost', 'Euro', 'Global', 'Inter',
            'Trans', 'Multi', 'Uni', 'Zentral', 'Regional', 'National'
        ]
        self.company_types = [
            'GmbH', 'AG', 'KG', 'OHG', 'GmbH & Co. KG', 'SE', 'e.K.'
        ]
        self.company_names = [
            'Technik', 'Logistik', 'Bau', 'Handel', 'Service', 'Maschinen',
            'Industrie', 'Consulting', 'Solutions', 'Holding', 'Invest',
            'Chemie', 'Pharma', 'Energie', 'Stahl', 'Auto', 'Elektronik',
            'Medien', 'Immobilien', 'Finanz', 'Versicherung'
        ]

        # Rating transition probabilities (simplified)
        self.ratings = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC', 'CC', 'C', 'D']

        # Risk classes based on rating
        self.risk_class_mapping = {
            'AAA': 'niedrig', 'AA': 'niedrig', 'A': 'niedrig',
            'BBB': 'mittel', 'BB': 'mittel',
            'B': 'hoch', 'CCC': 'hoch',
            'CC': 'sehr_hoch', 'C': 'sehr_hoch', 'D': 'sehr_hoch'
        }

    def generate_company_name(self) -> str:
        """Generate a realistic German company name."""
        pattern = random.choice([1, 2, 3, 4])

        if pattern == 1:
            return f"{random.choice(self.company_prefixes)} {random.choice(self.company_names)} {random.choice(self.company_types)}"
        elif pattern == 2:
            return f"{random.choice(self.company_names)} {random.choice(self.company_types)}"
        elif pattern == 3:
            last_name = random.choice(['Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber',
                                       'Meyer', 'Wagner', 'Becker', 'Schulz', 'Hoffmann',
                                       'Koch', 'Richter', 'Klein', 'Wolf', 'Schröder'])
            return f"{last_name} {random.choice(self.company_names)} {random.choice(self.company_types)}"
        else:
            return f"{random.choice(self.company_prefixes)}{random.choice(self.company_names).lower()} {random.choice(self.company_types)}"

    def select_rating(self) -> str:
        """Select a rating based on configured distribution."""
        ratings = list(DemoConfig.RATING_DISTRIBUTION.keys())
        weights = list(DemoConfig.RATING_DISTRIBUTION.values())
        return random.choices(ratings, weights=weights)[0]

    def generate_customers(self, n: int = None) -> List[Dict[str, Any]]:
        """
        Generate customer records.

        Args:
            n: Number of customers to generate (default from config)

        Returns:
            List of customer dictionaries
        """
        n = n or DemoConfig.NUM_CUSTOMERS
        customers = []

        for i in range(n):
            rating = self.select_rating()
            risk_class = self.risk_class_mapping.get(rating, 'mittel')

            # Bonitätsindex based on rating (higher = better)
            rating_scores = {'AAA': 95, 'AA': 88, 'A': 80, 'BBB': 70,
                            'BB': 58, 'B': 45, 'CCC': 32, 'CC': 20, 'C': 10, 'D': 5}
            base_score = rating_scores.get(rating, 50)
            bonitaetsindex = max(0, min(100, base_score + random.gauss(0, 5)))

            # Company size influences segment
            segment_choice = random.random()
            if segment_choice < 0.3:
                segment = 'retail'
                umsatz = random.uniform(100000, 2000000)
                mitarbeiter = random.randint(1, 50)
            elif segment_choice < 0.7:
                segment = 'sme'
                umsatz = random.uniform(2000000, 50000000)
                mitarbeiter = random.randint(50, 500)
            else:
                segment = 'corporate'
                umsatz = random.uniform(50000000, 5000000000)
                mitarbeiter = random.randint(500, 50000)

            customer = {
                'name': self.generate_company_name(),
                'branche': random.choice(DemoConfig.INDUSTRIES),
                'kreditrating': rating,
                'gruendungsjahr': random.randint(1950, 2023),
                'bonitaetsindex': round(bonitaetsindex, 2),
                'region': random.choice(DemoConfig.REGIONS),
                'risiko_klasse': risk_class,
                'kunden_segment': segment,
                'umsatz': round(umsatz, 2),
                'mitarbeiteranzahl': mitarbeiter,
                'eigenkapitalquote': round(random.uniform(10, 60), 2)
            }
            customers.append(customer)

        return customers

    def generate_contracts(self, customer_ids: List[int],
                           n: int = None) -> List[Dict[str, Any]]:
        """
        Generate credit contract records.

        Args:
            customer_ids: List of valid customer IDs
            n: Number of contracts to generate

        Returns:
            List of contract dictionaries
        """
        n = n or DemoConfig.NUM_CONTRACTS
        contracts = []

        # Base date for contract generation
        base_date = datetime.now()

        for i in range(n):
            kunden_id = random.choice(customer_ids)
            produkt = random.choice(DemoConfig.PRODUCT_TYPES)

            # Contract date in the past (0-5 years ago)
            days_ago = random.randint(0, 1825)
            vertragsdatum = (base_date - timedelta(days=days_ago)).date()

            # Loan parameters
            if produkt == 'Hypothek':
                laufzeit = random.choice([120, 180, 240, 300, 360])  # 10-30 years
                kreditlimit = random.uniform(100000, 5000000)
                zinssatz = random.uniform(0.02, 0.05)
                sicherheiten_typ = 'Immobilie'
                sicherheiten_wert = kreditlimit * random.uniform(1.1, 1.5)
            elif produkt == 'Kreditlinie':
                laufzeit = random.choice([12, 24, 36, 60])
                kreditlimit = random.uniform(50000, 10000000)
                zinssatz = random.uniform(0.04, 0.12)
                sicherheiten_typ = random.choice(['Buergschaft', 'Warenlager', 'Keine'])
                sicherheiten_wert = kreditlimit * random.uniform(0, 0.8)
            elif produkt == 'Leasing':
                laufzeit = random.choice([24, 36, 48, 60])
                kreditlimit = random.uniform(20000, 2000000)
                zinssatz = random.uniform(0.03, 0.08)
                sicherheiten_typ = 'Leasingobjekt'
                sicherheiten_wert = kreditlimit * 0.7
            else:  # Darlehen and others
                laufzeit = random.choice([12, 24, 36, 48, 60, 84, 120])
                kreditlimit = random.uniform(10000, 50000000)
                zinssatz = random.uniform(0.03, 0.10)
                sicherheiten_typ = random.choice(['Immobilie', 'Buergschaft',
                                                   'Warenlager', 'Forderungen', 'Keine'])
                if sicherheiten_typ == 'Keine':
                    sicherheiten_wert = 0
                else:
                    sicherheiten_wert = kreditlimit * random.uniform(0.3, 1.0)

            # Calculate utilization and remaining debt
            if produkt == 'Kreditlinie':
                auslastung = random.uniform(0, 1)
                ausgenutztes_limit = kreditlimit * auslastung
                restschuld = ausgenutztes_limit
            else:
                # Progress through loan
                elapsed_months = (base_date.date() - vertragsdatum).days / 30
                progress = min(1, elapsed_months / laufzeit)
                restschuld = kreditlimit * (1 - progress * random.uniform(0.8, 1.0))
                ausgenutztes_limit = kreditlimit

            # Status based on various factors
            status_roll = random.random()
            if status_roll < 0.85:
                status = 'aktiv'
            elif status_roll < 0.92:
                status = 'abgeschlossen'
            elif status_roll < 0.97:
                status = 'gekuendigt'
            else:
                status = 'ausfall'

            # PD, LGD, EAD for risk calculations
            pd_base = RiskParameters.RATING_PD.get('BBB', 0.0045)  # Will be updated based on customer
            lgd = RiskParameters.LGD_BY_COLLATERAL.get(sicherheiten_typ, 0.45)

            contract = {
                'kunden_id': kunden_id,
                'produkt_typ': produkt,
                'vertragsdatum': vertragsdatum.isoformat(),
                'laufzeit_monate': laufzeit,
                'zinssatz': round(zinssatz, 4),
                'waehrung': 'EUR',
                'kreditlimit': round(kreditlimit, 2),
                'ausgenutztes_limit': round(ausgenutztes_limit, 2),
                'restschuld': round(max(0, restschuld), 2),
                'sicherheiten_wert': round(sicherheiten_wert, 2),
                'sicherheiten_typ': sicherheiten_typ,
                'kreditnehmer_score': random.randint(300, 900),
                'vertrag_status': status,
                'naechste_faelligkeit': (base_date + timedelta(days=random.randint(1, 30))).date().isoformat(),
                'tilgungsart': random.choice(['annuitaet', 'endfaellig', 'linear']),
                'zweckbindung': random.choice(['Betriebsmittel', 'Investition', 'Umschuldung',
                                               'Expansion', 'Immobilienerwerb', None]),
                'pd_wert': round(pd_base * random.uniform(0.5, 2.0), 6),
                'lgd_wert': round(lgd, 4),
                'ead_wert': round(ausgenutztes_limit, 2)
            }
            contracts.append(contract)

        return contracts

    def generate_payments(self, contract_data: List[Dict],
                          n: int = None) -> List[Dict[str, Any]]:
        """
        Generate payment records.

        Args:
            contract_data: List of contract dictionaries with IDs
            n: Number of payments to generate

        Returns:
            List of payment dictionaries
        """
        n = n or DemoConfig.NUM_PAYMENTS
        payments = []
        base_date = datetime.now()

        for i in range(n):
            contract = random.choice(contract_data)
            vertrag_id = contract['vertrag_id']

            # Generate payment date
            faelligkeitsdatum = base_date - timedelta(days=random.randint(0, 730))
            faelligkeitsdatum = faelligkeitsdatum.date()

            # Payment amount based on contract
            soll_betrag = contract.get('kreditlimit', 100000) / contract.get('laufzeit_monate', 60)
            soll_betrag = round(soll_betrag * random.uniform(0.8, 1.2), 2)

            # Payment status
            status_roll = random.random()
            if status_roll < 0.75:
                # On time payment
                zahlungsdatum = faelligkeitsdatum - timedelta(days=random.randint(0, 5))
                ist_betrag = soll_betrag
                verspaetung = 0
                status = 'puenktlich'
            elif status_roll < 0.90:
                # Late payment
                verspaetung = random.randint(1, 30)
                zahlungsdatum = faelligkeitsdatum + timedelta(days=verspaetung)
                ist_betrag = soll_betrag
                status = 'verzoegert'
            elif status_roll < 0.96:
                # Significantly late
                verspaetung = random.randint(31, 90)
                zahlungsdatum = faelligkeitsdatum + timedelta(days=verspaetung)
                ist_betrag = soll_betrag * random.uniform(0.5, 1.0)
                status = 'verzoegert'
            elif status_roll < 0.99:
                # Default
                verspaetung = random.randint(91, 365)
                zahlungsdatum = None
                ist_betrag = soll_betrag * random.uniform(0, 0.3)
                status = 'ausfall'
            else:
                # Open payment
                verspaetung = max(0, (base_date.date() - faelligkeitsdatum).days)
                zahlungsdatum = None
                ist_betrag = 0
                status = 'offen'

            payment = {
                'vertrag_id': vertrag_id,
                'faelligkeitsdatum': faelligkeitsdatum.isoformat(),
                'zahlungsdatum': zahlungsdatum.isoformat() if zahlungsdatum else None,
                'soll_betrag': round(soll_betrag, 2),
                'ist_betrag': round(ist_betrag, 2),
                'verspaetung_tage': verspaetung,
                'zahlungsstatus': status,
                'zahlungsart': random.choice(['Tilgung', 'Zinsen', 'Tilgung_und_Zinsen']),
                'mahnungsstufe': min(3, verspaetung // 30),
                'kommentar': None
            }
            payments.append(payment)

        return payments

    def generate_defaults(self, contract_data: List[Dict],
                          customer_data: List[Dict],
                          n: int = None) -> List[Dict[str, Any]]:
        """
        Generate default event records.

        Args:
            contract_data: List of contracts with IDs
            customer_data: List of customers with IDs
            n: Number of default events

        Returns:
            List of default event dictionaries
        """
        n = n or DemoConfig.NUM_DEFAULTS
        defaults = []
        base_date = datetime.now()

        # Filter for contracts that could be in default
        potential_defaults = [c for c in contract_data if c.get('vertrag_status') in ['ausfall', 'gekuendigt']]
        if len(potential_defaults) < n:
            potential_defaults = contract_data[:n]

        default_reasons = [
            'Insolvenz', 'Zahlungsunfaehigkeit', 'Liquiditaetsprobleme',
            'Umsatzrueckgang', 'Marktveraenderungen', 'Managementfehler',
            'Betrug', 'Branchenkrise', 'Pandemie_Auswirkungen'
        ]

        for contract in random.sample(potential_defaults, min(n, len(potential_defaults))):
            vertrag_id = contract['vertrag_id']
            kunden_id = contract['kunden_id']

            # Default date
            ausfall_datum = base_date - timedelta(days=random.randint(30, 730))
            ausgefallener_betrag = contract.get('restschuld', 100000)

            # Recovery
            recovery_rate = random.uniform(0.1, 0.6)
            wiederherstellungs_betrag = ausgefallener_betrag * recovery_rate
            sicherheiten_verwertet = contract.get('sicherheiten_wert', 0) * random.uniform(0.5, 0.9)

            default_event = {
                'vertrag_id': vertrag_id,
                'kunden_id': kunden_id,
                'ausfall_datum': ausfall_datum.date().isoformat(),
                'ausfall_grund': random.choice(default_reasons),
                'ausgefallener_betrag': round(ausgefallener_betrag, 2),
                'sicherheiten_verwertet': round(sicherheiten_verwertet, 2),
                'wiederherstellungs_betrag': round(wiederherstellungs_betrag, 2),
                'wiederherstellungs_datum': (ausfall_datum + timedelta(days=random.randint(90, 730))).date().isoformat() if random.random() > 0.3 else None,
                'wiederherstellungs_quote': round(recovery_rate, 4),
                'abschreibung_betrag': round(ausgefallener_betrag - wiederherstellungs_betrag - sicherheiten_verwertet, 2),
                'abschreibung_datum': (ausfall_datum + timedelta(days=random.randint(180, 365))).date().isoformat() if random.random() > 0.4 else None,
                'rechtsverfahren_status': random.choice(['offen', 'laufend', 'abgeschlossen']),
                'kommentar': None
            }
            defaults.append(default_event)

        return defaults

    def generate_economic_data(self, years: int = 5) -> List[Dict[str, Any]]:
        """
        Generate economic indicator data.

        Args:
            years: Number of years of data to generate

        Returns:
            List of economic data dictionaries
        """
        economic_data = []
        base_date = datetime.now()

        for months_ago in range(years * 12):
            datum = (base_date - timedelta(days=months_ago * 30)).date()

            for region in DemoConfig.REGIONS:
                for branche in DemoConfig.INDUSTRIES + [None]:
                    # Generate realistic economic indicators with some correlation
                    base_unemployment = 5.5 + random.gauss(0, 1)
                    base_interest = 3.5 + random.gauss(0, 0.5)

                    # Cyclical component
                    cycle = np.sin(months_ago / 24 * np.pi) * 0.5

                    economic_record = {
                        'datum': datum.isoformat(),
                        'region': region,
                        'branche': branche,
                        'ausfallrate_branche': round(max(0.001, 0.02 + cycle * 0.01 + random.gauss(0, 0.005)), 4),
                        'konjunktur_index': round(100 + cycle * 10 + random.gauss(0, 3), 2),
                        'arbeitslosenquote': round(max(2, base_unemployment + cycle + random.gauss(0, 0.5)), 2),
                        'zinsniveau': round(max(0, base_interest + cycle * 0.5 + random.gauss(0, 0.2)), 4),
                        'inflation': round(2.5 + cycle * 0.5 + random.gauss(0, 0.5), 2),
                        'bip_wachstum': round(1.5 - cycle + random.gauss(0, 0.5), 2),
                        'insolvenzquote': round(max(0, 0.01 + cycle * 0.005 + random.gauss(0, 0.002)), 4),
                        'kreditvergabe_wachstum': round(3 - cycle * 2 + random.gauss(0, 1), 2),
                        'quelle': 'Demo_Generator'
                    }
                    economic_data.append(economic_record)

                    # Only generate industry-specific data occasionally
                    if branche is None or random.random() > 0.95:
                        continue

        return economic_data[:5000]  # Limit to reasonable size

    def generate_risk_limits(self, customer_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Generate risk limit records.

        Args:
            customer_data: List of customer dictionaries

        Returns:
            List of risk limit dictionaries
        """
        limits = []
        base_date = datetime.now().date()

        # Overall portfolio limit
        limits.append({
            'limit_typ': 'gesamt',
            'limit_name': 'Gesamtportfolio Limit',
            'referenz_id': None,
            'referenz_wert': 'Portfolio',
            'limit_wert': 5000000000,  # 5 Billion EUR
            'aktuelle_auslastung': 0,  # Will be calculated
            'auslastung_prozent': 0,
            'ueberschreitung_flag': False,
            'ueberschreitung_betrag': 0,
            'warn_schwelle': 80.0,
            'kritisch_schwelle': 95.0,
            'eskaliert_an': 'Vorstand',
            'eskaliert_datum': None,
            'gueltig_von': (base_date - timedelta(days=365)).isoformat(),
            'gueltig_bis': (base_date + timedelta(days=365)).isoformat(),
            'genehmigt_von': 'Aufsichtsrat',
            'genehmigt_am': (base_date - timedelta(days=365)).isoformat(),
            'kommentar': None
        })

        # Industry limits
        for branche in DemoConfig.INDUSTRIES:
            limit_value = random.uniform(500000000, 1500000000)
            auslastung = random.uniform(40, 100)

            limits.append({
                'limit_typ': 'branche',
                'limit_name': f'Branchenlimit {branche}',
                'referenz_id': None,
                'referenz_wert': branche,
                'limit_wert': round(limit_value, 2),
                'aktuelle_auslastung': round(limit_value * auslastung / 100, 2),
                'auslastung_prozent': round(auslastung, 2),
                'ueberschreitung_flag': auslastung > 100,
                'ueberschreitung_betrag': round(max(0, limit_value * (auslastung - 100) / 100), 2),
                'warn_schwelle': 80.0,
                'kritisch_schwelle': 95.0,
                'eskaliert_an': 'Kreditrisiko-Abteilung' if auslastung > 80 else None,
                'eskaliert_datum': base_date.isoformat() if auslastung > 80 else None,
                'gueltig_von': (base_date - timedelta(days=365)).isoformat(),
                'gueltig_bis': (base_date + timedelta(days=365)).isoformat(),
                'genehmigt_von': 'Kreditkomitee',
                'genehmigt_am': (base_date - timedelta(days=365)).isoformat(),
                'kommentar': None
            })

        # Region limits
        for region in DemoConfig.REGIONS:
            limit_value = random.uniform(300000000, 1000000000)
            auslastung = random.uniform(30, 95)

            limits.append({
                'limit_typ': 'region',
                'limit_name': f'Regionslimit {region}',
                'referenz_id': None,
                'referenz_wert': region,
                'limit_wert': round(limit_value, 2),
                'aktuelle_auslastung': round(limit_value * auslastung / 100, 2),
                'auslastung_prozent': round(auslastung, 2),
                'ueberschreitung_flag': auslastung > 100,
                'ueberschreitung_betrag': round(max(0, limit_value * (auslastung - 100) / 100), 2),
                'warn_schwelle': 80.0,
                'kritisch_schwelle': 95.0,
                'eskaliert_an': None,
                'eskaliert_datum': None,
                'gueltig_von': (base_date - timedelta(days=365)).isoformat(),
                'gueltig_bis': (base_date + timedelta(days=365)).isoformat(),
                'genehmigt_von': 'Kreditkomitee',
                'genehmigt_am': (base_date - timedelta(days=365)).isoformat(),
                'kommentar': None
            })

        # Top customer limits
        for customer in customer_data[:20]:  # Top 20 customers
            limit_value = random.uniform(10000000, 100000000)
            auslastung = random.uniform(20, 110)

            limits.append({
                'limit_typ': 'kunde',
                'limit_name': f'Kundenlimit {customer["name"][:30]}',
                'referenz_id': customer.get('kunden_id'),
                'referenz_wert': customer['name'][:50],
                'limit_wert': round(limit_value, 2),
                'aktuelle_auslastung': round(limit_value * auslastung / 100, 2),
                'auslastung_prozent': round(auslastung, 2),
                'ueberschreitung_flag': auslastung > 100,
                'ueberschreitung_betrag': round(max(0, limit_value * (auslastung - 100) / 100), 2),
                'warn_schwelle': 80.0,
                'kritisch_schwelle': 95.0,
                'eskaliert_an': 'Kundenbetreuer' if auslastung > 100 else None,
                'eskaliert_datum': base_date.isoformat() if auslastung > 100 else None,
                'gueltig_von': (base_date - timedelta(days=365)).isoformat(),
                'gueltig_bis': (base_date + timedelta(days=365)).isoformat(),
                'genehmigt_von': 'Kreditabteilung',
                'genehmigt_am': (base_date - timedelta(days=180)).isoformat(),
                'kommentar': None
            })

        return limits

    def generate_rating_history(self, customer_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Generate rating history records.

        Args:
            customer_data: List of customer dictionaries

        Returns:
            List of rating history dictionaries
        """
        history = []
        base_date = datetime.now()
        ratings = self.ratings

        for customer in customer_data:
            # Generate 0-5 rating changes per customer
            num_changes = random.randint(0, 5)
            current_rating = customer['kreditrating']

            for i in range(num_changes):
                # Previous rating (usually adjacent)
                current_idx = ratings.index(current_rating) if current_rating in ratings else 4
                if random.random() < 0.6:  # 60% chance of downgrade
                    new_idx = min(len(ratings) - 1, current_idx + random.randint(1, 2))
                else:  # 40% chance of upgrade
                    new_idx = max(0, current_idx - random.randint(1, 2))

                old_rating = ratings[new_idx]
                change_date = base_date - timedelta(days=random.randint(30, 1000))

                history.append({
                    'kunden_id': customer.get('kunden_id'),
                    'altes_rating': old_rating,
                    'neues_rating': current_rating,
                    'aenderungsdatum': change_date.date().isoformat(),
                    'aenderungsgrund': random.choice([
                        'Jahresabschluss-Analyse', 'Zahlungsverhalten',
                        'Branchenentwicklung', 'Management-Wechsel',
                        'Quartalsbericht', 'Rating-Review'
                    ]),
                    'bearbeiter': random.choice(['Analyst_A', 'Analyst_B', 'Analyst_C', 'System']),
                    'kommentar': None
                })

                current_rating = old_rating

        return history

    def generate_provisions(self, contract_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Generate IFRS 9 provision records.

        Args:
            contract_data: List of contract dictionaries

        Returns:
            List of provision dictionaries
        """
        provisions = []
        base_date = datetime.now().date()

        for contract in contract_data:
            # Determine IFRS 9 stage
            status = contract.get('vertrag_status', 'aktiv')
            pd_wert = contract.get('pd_wert', 0.01)

            if status == 'ausfall':
                stage = 3
            elif pd_wert > 0.05 or status == 'gekuendigt':
                stage = 2
            else:
                stage = 1

            # Calculate ECL
            ead = contract.get('ead_wert', contract.get('restschuld', 100000))
            lgd = contract.get('lgd_wert', 0.45)

            if stage == 1:
                ecl_12m = ead * pd_wert * lgd
                ecl_lifetime = ecl_12m * 2  # Simplified
            elif stage == 2:
                ecl_12m = ead * pd_wert * lgd
                ecl_lifetime = ead * min(1, pd_wert * 5) * lgd
            else:  # Stage 3
                ecl_12m = ead * lgd
                ecl_lifetime = ead * lgd

            provision = {
                'vertrag_id': contract.get('vertrag_id'),
                'stichtag': base_date.isoformat(),
                'stufe': stage,
                'ecl_12_monate': round(ecl_12m, 2),
                'ecl_lifetime': round(ecl_lifetime, 2),
                'pd_12_monate': round(pd_wert, 6),
                'pd_lifetime': round(min(1, pd_wert * 5), 6),
                'lgd': round(lgd, 4),
                'ead': round(ead, 2),
                'rueckstellung_betrag': round(ecl_lifetime if stage > 1 else ecl_12m, 2),
                'vorperiode_betrag': round((ecl_lifetime if stage > 1 else ecl_12m) * random.uniform(0.8, 1.2), 2),
                'aenderung_betrag': 0  # Will be calculated
            }
            provision['aenderung_betrag'] = round(
                provision['rueckstellung_betrag'] - provision['vorperiode_betrag'], 2
            )
            provisions.append(provision)

        return provisions


def populate_demo_database(db: DatabaseManager = None):
    """
    Populate the demo database with synthetic data.

    Args:
        db: DatabaseManager instance (creates new if None)

    Returns:
        DatabaseManager instance
    """
    if db is None:
        db = init_demo_database(force_recreate=True)

    generator = DemoDataGenerator()

    print("Generating demo data...")

    # Generate customers
    print("  - Generating customers...")
    customers = generator.generate_customers()
    db.execute_insert_many('kunden', customers)

    # Get customer IDs
    customer_data = db.execute_query("SELECT kunden_id, name, kreditrating FROM kunden")
    customer_ids = [c['kunden_id'] for c in customer_data]

    # Generate contracts
    print("  - Generating contracts...")
    contracts = generator.generate_contracts(customer_ids)
    db.execute_insert_many('kredit_vertraege', contracts)

    # Get contract IDs
    contract_data = db.execute_query(
        "SELECT vertrag_id, kunden_id, kreditlimit, restschuld, "
        "laufzeit_monate, vertrag_status, sicherheiten_wert, pd_wert, lgd_wert, ead_wert "
        "FROM kredit_vertraege"
    )

    # Generate payments
    print("  - Generating payments...")
    payments = generator.generate_payments(contract_data)
    db.execute_insert_many('zahlungen', payments)

    # Generate defaults
    print("  - Generating default events...")
    defaults = generator.generate_defaults(contract_data, customer_data)
    db.execute_insert_many('ausfall_ereignisse', defaults)

    # Generate economic data (limited for demo)
    print("  - Generating economic data...")
    economic = generator.generate_economic_data(years=2)
    # Insert in batches to avoid issues
    batch_size = 500
    for i in range(0, len(economic), batch_size):
        batch = economic[i:i + batch_size]
        try:
            db.execute_insert_many('wirtschaftsdaten', batch)
        except Exception:
            pass  # Skip duplicates

    # Generate risk limits
    print("  - Generating risk limits...")
    # Add customer IDs to customer data
    for i, c in enumerate(customer_data):
        c['kunden_id'] = c['kunden_id']
        c['name'] = c['name']
    limits = generator.generate_risk_limits(customer_data)
    db.execute_insert_many('risiko_limits', limits)

    # Generate rating history
    print("  - Generating rating history...")
    history = generator.generate_rating_history(customer_data)
    db.execute_insert_many('rating_historie', history)

    # Generate provisions
    print("  - Generating provisions (IFRS 9)...")
    provisions = generator.generate_provisions(contract_data)
    db.execute_insert_many('rueckstellungen', provisions)

    print("\nDemo database populated successfully!")
    print(f"\nDatabase statistics:")
    for table in db.get_all_tables():
        if not table.startswith('sqlite_'):
            count = db.get_row_count(table)
            print(f"  {table}: {count:,} records")

    return db


if __name__ == "__main__":
    db = populate_demo_database()
