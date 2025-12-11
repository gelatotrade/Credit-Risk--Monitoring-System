-- ============================================================================
-- KREDITRISIKO-ÜBERWACHUNGSSYSTEM - DATABASE SCHEMA
-- Credit Risk Monitoring System
-- Version: 1.0
-- ============================================================================

-- Drop tables if they exist (for clean reinstallation)
DROP TABLE IF EXISTS risiko_limits;
DROP TABLE IF EXISTS wirtschaftsdaten;
DROP TABLE IF EXISTS ausfall_ereignisse;
DROP TABLE IF EXISTS zahlungen;
DROP TABLE IF EXISTS kredit_vertraege;
DROP TABLE IF EXISTS kunden;
DROP TABLE IF EXISTS rating_historie;
DROP TABLE IF EXISTS rueckstellungen;

-- ============================================================================
-- KERN-TABELLEN (Core Tables)
-- ============================================================================

-- Tabelle: KUNDEN (Customers)
-- Speichert alle Kundeninformationen für Kreditnehmer
CREATE TABLE kunden (
    kunden_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    branche VARCHAR(100) NOT NULL,
    kreditrating VARCHAR(10) NOT NULL,  -- AAA, AA, A, BBB, BB, B, CCC, CC, C, D
    gruendungsjahr INTEGER,
    bonitaetsindex DECIMAL(5,2),  -- 0-100 Score
    region VARCHAR(100) NOT NULL,
    risiko_klasse VARCHAR(20) NOT NULL,  -- niedrig, mittel, hoch, sehr_hoch
    kunden_segment VARCHAR(20) NOT NULL,  -- retail, corporate, sme
    umsatz DECIMAL(18,2),
    mitarbeiteranzahl INTEGER,
    eigenkapitalquote DECIMAL(5,2),
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index für häufige Abfragen
CREATE INDEX idx_kunden_branche ON kunden(branche);
CREATE INDEX idx_kunden_region ON kunden(region);
CREATE INDEX idx_kunden_rating ON kunden(kreditrating);
CREATE INDEX idx_kunden_risiko ON kunden(risiko_klasse);

-- Tabelle: KREDIT_VERTRAEGE (Credit Contracts)
-- Speichert alle Kreditverträge und deren Details
CREATE TABLE kredit_vertraege (
    vertrag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kunden_id INTEGER NOT NULL,
    produkt_typ VARCHAR(50) NOT NULL,  -- Darlehen, Kreditlinie, Hypothek, Leasing, Factoring
    vertragsdatum DATE NOT NULL,
    laufzeit_monate INTEGER NOT NULL,
    zinssatz DECIMAL(5,4) NOT NULL,  -- z.B. 0.0525 für 5.25%
    waehrung VARCHAR(3) DEFAULT 'EUR',
    kreditlimit DECIMAL(18,2) NOT NULL,
    ausgenutztes_limit DECIMAL(18,2) DEFAULT 0,
    restschuld DECIMAL(18,2),
    sicherheiten_wert DECIMAL(18,2) DEFAULT 0,
    sicherheiten_typ VARCHAR(100),  -- Immobilie, Bürgschaft, Warenlager, etc.
    kreditnehmer_score INTEGER,  -- 1-1000
    vertrag_status VARCHAR(20) DEFAULT 'aktiv',  -- aktiv, gekuendigt, abgeschlossen, ausfall
    naechste_faelligkeit DATE,
    tilgungsart VARCHAR(50),  -- annuitaet, endfaellig, linear
    zweckbindung VARCHAR(200),
    pd_wert DECIMAL(7,6),  -- Probability of Default (z.B. 0.012345)
    lgd_wert DECIMAL(5,4),  -- Loss Given Default (z.B. 0.45)
    ead_wert DECIMAL(18,2),  -- Exposure at Default
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kunden_id) REFERENCES kunden(kunden_id)
);

CREATE INDEX idx_vertraege_kunde ON kredit_vertraege(kunden_id);
CREATE INDEX idx_vertraege_status ON kredit_vertraege(vertrag_status);
CREATE INDEX idx_vertraege_produkt ON kredit_vertraege(produkt_typ);
CREATE INDEX idx_vertraege_datum ON kredit_vertraege(vertragsdatum);

-- Tabelle: ZAHLUNGEN (Payments)
-- Speichert alle Zahlungsvorgänge
CREATE TABLE zahlungen (
    zahlung_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertrag_id INTEGER NOT NULL,
    faelligkeitsdatum DATE NOT NULL,
    zahlungsdatum DATE,
    soll_betrag DECIMAL(18,2) NOT NULL,
    ist_betrag DECIMAL(18,2) DEFAULT 0,
    verspaetung_tage INTEGER DEFAULT 0,
    zahlungsstatus VARCHAR(20) NOT NULL,  -- puenktlich, verzoegert, ausfall, offen
    zahlungsart VARCHAR(50),  -- Tilgung, Zinsen, Gebuehr
    mahnungsstufe INTEGER DEFAULT 0,
    kommentar TEXT,
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vertrag_id) REFERENCES kredit_vertraege(vertrag_id)
);

CREATE INDEX idx_zahlungen_vertrag ON zahlungen(vertrag_id);
CREATE INDEX idx_zahlungen_status ON zahlungen(zahlungsstatus);
CREATE INDEX idx_zahlungen_faelligkeit ON zahlungen(faelligkeitsdatum);
CREATE INDEX idx_zahlungen_verspaetung ON zahlungen(verspaetung_tage);

-- Tabelle: AUSFALL_EREIGNISSE (Default Events)
-- Dokumentiert alle Kreditausfälle
CREATE TABLE ausfall_ereignisse (
    ausfall_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertrag_id INTEGER NOT NULL,
    kunden_id INTEGER NOT NULL,
    ausfall_datum DATE NOT NULL,
    ausfall_grund VARCHAR(200) NOT NULL,  -- Insolvenz, Zahlungsunfaehigkeit, Betrug, etc.
    ausgefallener_betrag DECIMAL(18,2) NOT NULL,
    sicherheiten_verwertet DECIMAL(18,2) DEFAULT 0,
    wiederherstellungs_betrag DECIMAL(18,2) DEFAULT 0,
    wiederherstellungs_datum DATE,
    wiederherstellungs_quote DECIMAL(5,4),  -- Recovery Rate
    abschreibung_betrag DECIMAL(18,2) DEFAULT 0,
    abschreibung_datum DATE,
    rechtsverfahren_status VARCHAR(50),  -- offen, laufend, abgeschlossen
    kommentar TEXT,
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vertrag_id) REFERENCES kredit_vertraege(vertrag_id),
    FOREIGN KEY (kunden_id) REFERENCES kunden(kunden_id)
);

CREATE INDEX idx_ausfall_datum ON ausfall_ereignisse(ausfall_datum);
CREATE INDEX idx_ausfall_kunde ON ausfall_ereignisse(kunden_id);

-- Tabelle: WIRTSCHAFTSDATEN (Economic Data)
-- Externe Wirtschaftsindikatoren für Risikoanalyse
CREATE TABLE wirtschaftsdaten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datum DATE NOT NULL,
    region VARCHAR(100) NOT NULL,
    branche VARCHAR(100),
    ausfallrate_branche DECIMAL(6,4),  -- in Prozent
    konjunktur_index DECIMAL(6,2),  -- z.B. 100 = neutral
    arbeitslosenquote DECIMAL(5,2),
    zinsniveau DECIMAL(5,4),  -- EZB Leitzins
    inflation DECIMAL(5,2),
    bip_wachstum DECIMAL(5,2),
    insolvenzquote DECIMAL(6,4),
    kreditvergabe_wachstum DECIMAL(5,2),
    quelle VARCHAR(100),
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wirtschaft_datum ON wirtschaftsdaten(datum);
CREATE INDEX idx_wirtschaft_region ON wirtschaftsdaten(region);
CREATE INDEX idx_wirtschaft_branche ON wirtschaftsdaten(branche);
CREATE UNIQUE INDEX idx_wirtschaft_unique ON wirtschaftsdaten(datum, region, branche);

-- Tabelle: RISIKO_LIMITS (Risk Limits)
-- Definiert und überwacht Risikolimits
CREATE TABLE risiko_limits (
    limit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    limit_typ VARCHAR(50) NOT NULL,  -- kunde, branche, region, gesamt, produkt
    limit_name VARCHAR(200) NOT NULL,
    referenz_id INTEGER,  -- kunden_id, branche_code, etc.
    referenz_wert VARCHAR(100),  -- Branchenname, Region, etc.
    limit_wert DECIMAL(18,2) NOT NULL,
    aktuelle_auslastung DECIMAL(18,2) DEFAULT 0,
    auslastung_prozent DECIMAL(5,2) DEFAULT 0,
    ueberschreitung_flag BOOLEAN DEFAULT FALSE,
    ueberschreitung_betrag DECIMAL(18,2) DEFAULT 0,
    warn_schwelle DECIMAL(5,2) DEFAULT 80.00,  -- Warnung ab 80%
    kritisch_schwelle DECIMAL(5,2) DEFAULT 95.00,  -- Kritisch ab 95%
    eskaliert_an VARCHAR(200),
    eskaliert_datum TIMESTAMP,
    gueltig_von DATE NOT NULL,
    gueltig_bis DATE,
    genehmigt_von VARCHAR(100),
    genehmigt_am DATE,
    kommentar TEXT,
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_limits_typ ON risiko_limits(limit_typ);
CREATE INDEX idx_limits_referenz ON risiko_limits(referenz_wert);
CREATE INDEX idx_limits_ueberschreitung ON risiko_limits(ueberschreitung_flag);

-- Tabelle: RATING_HISTORIE (Rating History)
-- Verfolgt Änderungen in Kundenratings
CREATE TABLE rating_historie (
    historie_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kunden_id INTEGER NOT NULL,
    altes_rating VARCHAR(10),
    neues_rating VARCHAR(10) NOT NULL,
    aenderungsdatum DATE NOT NULL,
    aenderungsgrund VARCHAR(200),
    bearbeiter VARCHAR(100),
    kommentar TEXT,
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kunden_id) REFERENCES kunden(kunden_id)
);

CREATE INDEX idx_rating_kunde ON rating_historie(kunden_id);
CREATE INDEX idx_rating_datum ON rating_historie(aenderungsdatum);

-- Tabelle: RUECKSTELLUNGEN (Provisions/Reserves)
-- IFRS 9 Rückstellungen für erwartete Kreditverluste
CREATE TABLE rueckstellungen (
    rueckstellung_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertrag_id INTEGER NOT NULL,
    stichtag DATE NOT NULL,
    stufe INTEGER NOT NULL,  -- IFRS 9 Stage 1, 2, or 3
    ecl_12_monate DECIMAL(18,2),  -- 12-month ECL
    ecl_lifetime DECIMAL(18,2),  -- Lifetime ECL
    pd_12_monate DECIMAL(7,6),
    pd_lifetime DECIMAL(7,6),
    lgd DECIMAL(5,4),
    ead DECIMAL(18,2),
    rueckstellung_betrag DECIMAL(18,2) NOT NULL,
    vorperiode_betrag DECIMAL(18,2),
    aenderung_betrag DECIMAL(18,2),
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vertrag_id) REFERENCES kredit_vertraege(vertrag_id)
);

CREATE INDEX idx_rueckstellung_vertrag ON rueckstellungen(vertrag_id);
CREATE INDEX idx_rueckstellung_stichtag ON rueckstellungen(stichtag);
CREATE INDEX idx_rueckstellung_stufe ON rueckstellungen(stufe);

-- ============================================================================
-- VIEWS FÜR DASHBOARD UND ANALYSEN
-- ============================================================================

-- View: RISIKO_HEATMAP
-- Kunden nach Rating und Exposure für Heatmap-Darstellung
CREATE VIEW IF NOT EXISTS risiko_heatmap AS
SELECT
    k.kreditrating,
    k.risiko_klasse,
    k.branche,
    k.region,
    COUNT(DISTINCT k.kunden_id) as anzahl_kunden,
    COUNT(v.vertrag_id) as anzahl_vertraege,
    SUM(v.kreditlimit) as gesamt_limit,
    SUM(v.ausgenutztes_limit) as gesamt_auslastung,
    SUM(v.restschuld) as gesamt_restschuld,
    AVG(k.bonitaetsindex) as durchschnitt_bonitaet,
    SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) as ausfall_volumen
FROM kunden k
LEFT JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
GROUP BY k.kreditrating, k.risiko_klasse, k.branche, k.region;

-- View: PORTFOLIO_QUALITY_TREND
-- NPL (Non-Performing Loans) Entwicklung
CREATE VIEW IF NOT EXISTS portfolio_quality_trend AS
SELECT
    strftime('%Y-%m', v.vertragsdatum) as monat,
    COUNT(v.vertrag_id) as anzahl_vertraege,
    SUM(v.restschuld) as gesamt_portfolio,
    SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) as npl_volumen,
    ROUND(SUM(CASE WHEN v.vertrag_status = 'ausfall' THEN v.restschuld ELSE 0 END) * 100.0 /
          NULLIF(SUM(v.restschuld), 0), 2) as npl_quote,
    SUM(CASE WHEN z.verspaetung_tage > 30 THEN z.soll_betrag ELSE 0 END) as verzoegert_30_tage,
    SUM(CASE WHEN z.verspaetung_tage > 90 THEN z.soll_betrag ELSE 0 END) as verzoegert_90_tage
FROM kredit_vertraege v
LEFT JOIN zahlungen z ON v.vertrag_id = z.vertrag_id
GROUP BY strftime('%Y-%m', v.vertragsdatum)
ORDER BY monat DESC;

-- View: LIMIT_ALERTS
-- Aktuelle Limitüberschreitungen und Warnungen
CREATE VIEW IF NOT EXISTS limit_alerts AS
SELECT
    limit_id,
    limit_typ,
    limit_name,
    referenz_wert,
    limit_wert,
    aktuelle_auslastung,
    auslastung_prozent,
    CASE
        WHEN auslastung_prozent >= kritisch_schwelle THEN 'KRITISCH'
        WHEN auslastung_prozent >= warn_schwelle THEN 'WARNUNG'
        ELSE 'OK'
    END as status,
    ueberschreitung_betrag,
    eskaliert_an,
    eskaliert_datum
FROM risiko_limits
WHERE auslastung_prozent >= warn_schwelle OR ueberschreitung_flag = TRUE
ORDER BY auslastung_prozent DESC;

-- View: CONCENTRATION_MATRIX
-- Branche × Region Konzentrationsmatrix
CREATE VIEW IF NOT EXISTS concentration_matrix AS
SELECT
    k.branche,
    k.region,
    COUNT(DISTINCT k.kunden_id) as anzahl_kunden,
    SUM(v.kreditlimit) as exposure_limit,
    SUM(v.ausgenutztes_limit) as exposure_genutzt,
    SUM(v.restschuld) as exposure_restschuld,
    AVG(k.bonitaetsindex) as durchschnitt_bonitaet,
    COUNT(CASE WHEN v.vertrag_status = 'ausfall' THEN 1 END) as anzahl_ausfaelle,
    ROUND(SUM(v.restschuld) * 100.0 /
          (SELECT SUM(restschuld) FROM kredit_vertraege), 2) as portfolio_anteil_prozent
FROM kunden k
LEFT JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
GROUP BY k.branche, k.region
ORDER BY exposure_restschuld DESC;

-- View: TOP_EXPOSURES
-- Top 10 Kunden nach Exposure
CREATE VIEW IF NOT EXISTS top_exposures AS
SELECT
    k.kunden_id,
    k.name,
    k.branche,
    k.region,
    k.kreditrating,
    k.risiko_klasse,
    COUNT(v.vertrag_id) as anzahl_vertraege,
    SUM(v.kreditlimit) as gesamt_limit,
    SUM(v.ausgenutztes_limit) as gesamt_auslastung,
    SUM(v.restschuld) as gesamt_exposure,
    SUM(v.sicherheiten_wert) as gesamt_sicherheiten,
    SUM(v.restschuld) - SUM(v.sicherheiten_wert) as unbesichertes_exposure
FROM kunden k
JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
WHERE v.vertrag_status = 'aktiv'
GROUP BY k.kunden_id
ORDER BY gesamt_exposure DESC
LIMIT 10;

-- View: EARLY_WARNING_SIGNALS
-- Frühwarnindikatoren
CREATE VIEW IF NOT EXISTS early_warning_signals AS
SELECT
    'Verzögerung > 30 Tage' as signal_typ,
    v.vertrag_id,
    k.name as kunde,
    k.kreditrating,
    v.restschuld as exposure,
    MAX(z.verspaetung_tage) as max_verspaetung,
    v.vertrag_status
FROM kredit_vertraege v
JOIN kunden k ON v.kunden_id = k.kunden_id
JOIN zahlungen z ON v.vertrag_id = z.vertrag_id
WHERE z.verspaetung_tage > 30
GROUP BY v.vertrag_id

UNION ALL

SELECT
    'Hohe Limitauslastung (>80%)' as signal_typ,
    v.vertrag_id,
    k.name as kunde,
    k.kreditrating,
    v.ausgenutztes_limit as exposure,
    ROUND(v.ausgenutztes_limit * 100.0 / NULLIF(v.kreditlimit, 0), 2) as auslastung_prozent,
    v.vertrag_status
FROM kredit_vertraege v
JOIN kunden k ON v.kunden_id = k.kunden_id
WHERE v.kreditlimit > 0 AND (v.ausgenutztes_limit * 100.0 / v.kreditlimit) > 80

UNION ALL

SELECT
    'Rating Downgrade' as signal_typ,
    NULL as vertrag_id,
    k.name as kunde,
    rh.neues_rating as kreditrating,
    (SELECT SUM(restschuld) FROM kredit_vertraege WHERE kunden_id = k.kunden_id) as exposure,
    NULL,
    rh.altes_rating || ' -> ' || rh.neues_rating as rating_aenderung
FROM rating_historie rh
JOIN kunden k ON rh.kunden_id = k.kunden_id
WHERE rh.aenderungsdatum >= date('now', '-90 days')
AND rh.neues_rating > rh.altes_rating;  -- Alphabetisch höher = schlechteres Rating

-- View: REGULATORY_LARGE_EXPOSURE
-- Large Exposure Reporting (>10% des Eigenkapitals - hier vereinfacht)
CREATE VIEW IF NOT EXISTS large_exposure_report AS
SELECT
    k.kunden_id,
    k.name,
    k.branche,
    k.kreditrating,
    SUM(v.restschuld) as gesamt_exposure,
    SUM(v.sicherheiten_wert) as anrechenbare_sicherheiten,
    SUM(v.restschuld) - SUM(v.sicherheiten_wert) as netto_exposure,
    (SELECT SUM(restschuld) FROM kredit_vertraege) as portfolio_gesamt,
    ROUND(SUM(v.restschuld) * 100.0 /
          (SELECT SUM(restschuld) FROM kredit_vertraege), 2) as portfolio_anteil
FROM kunden k
JOIN kredit_vertraege v ON k.kunden_id = v.kunden_id
WHERE v.vertrag_status = 'aktiv'
GROUP BY k.kunden_id
HAVING portfolio_anteil >= 5  -- Anzeige ab 5% für Übersicht
ORDER BY gesamt_exposure DESC;

-- ============================================================================
-- STORED PROCEDURES SIMULIERT ALS TRIGGER/CHECKS
-- ============================================================================

-- Trigger: Automatische Aktualisierung des Zeitstempels
CREATE TRIGGER IF NOT EXISTS update_kunden_timestamp
AFTER UPDATE ON kunden
BEGIN
    UPDATE kunden SET aktualisiert_am = CURRENT_TIMESTAMP WHERE kunden_id = NEW.kunden_id;
END;

CREATE TRIGGER IF NOT EXISTS update_vertraege_timestamp
AFTER UPDATE ON kredit_vertraege
BEGIN
    UPDATE kredit_vertraege SET aktualisiert_am = CURRENT_TIMESTAMP WHERE vertrag_id = NEW.vertrag_id;
END;

-- Trigger: Rating-Änderungen in Historie speichern
CREATE TRIGGER IF NOT EXISTS log_rating_change
AFTER UPDATE OF kreditrating ON kunden
WHEN OLD.kreditrating != NEW.kreditrating
BEGIN
    INSERT INTO rating_historie (kunden_id, altes_rating, neues_rating, aenderungsdatum, aenderungsgrund)
    VALUES (NEW.kunden_id, OLD.kreditrating, NEW.kreditrating, date('now'), 'Automatische Erfassung');
END;

-- Trigger: Limit-Überschreitung Flag setzen
CREATE TRIGGER IF NOT EXISTS check_limit_ueberschreitung
AFTER UPDATE OF aktuelle_auslastung ON risiko_limits
BEGIN
    UPDATE risiko_limits
    SET ueberschreitung_flag = CASE WHEN NEW.aktuelle_auslastung > limit_wert THEN TRUE ELSE FALSE END,
        ueberschreitung_betrag = CASE WHEN NEW.aktuelle_auslastung > limit_wert
                                      THEN NEW.aktuelle_auslastung - limit_wert ELSE 0 END,
        auslastung_prozent = ROUND(NEW.aktuelle_auslastung * 100.0 / NULLIF(limit_wert, 0), 2),
        aktualisiert_am = CURRENT_TIMESTAMP
    WHERE limit_id = NEW.limit_id;
END;
