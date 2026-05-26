# Breathe ESG — Data Source Research

This document records the research that informed every technical choice in the Breathe ESG data ingestion platform. For each data source, I document: where the information came from, what I learned, what the sample data looks like and why it looks that way, and what would break in a real deployment.

---

## 1. SAP MM — MB51 Material Document List

### Sources Consulted
- SAP Help Portal — MSEG (Material Document Segment) and MKPF (Material Document Header) table documentation. https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/MM-IM
- SAP Community forums — MB51 export column behaviour, ALV grid export formats, German locale decimal formatting (comma as decimal separator, period as thousands separator). https://community.sap.com
- SAP Note on encoding: UTF-8 without BOM is the default for SAP GUI exports; older systems (pre-ECC 6.0 EHP8) may export Windows-1252. Umlauts (ä, ö, ü, ß) in Materialkurztext (material short text) confirmed for German-locale systems.

### What I Learned
- MB51 exports from the ALV grid are tab-separated (.txt), not comma-separated. Some ABAP custom reports produce semicolon-delimited output (because comma is the decimal separator in German locale).
- Column headers appear in the user's logon language. A UK-deployed SAP system with a German-language user shows Buchungskreis (company code), Werk (plant), Menge (quantity), Meins (unit of measure), Bewegungsart (movement type). An English-language user sees Company Code, Plant, Quantity, etc. The parser must not match on exact header strings — match on column position or normalise headers.
- Buchungsdatum (posting date) is in YYYYMMDD format with no separators: 20240315 not 2024-03-15 or 15/03/2024. This is the single most common parser failure point.
- Menge uses German decimal notation: 1.500,000 means 1500.000 (period is thousands separator, comma is decimal). Parser must: strip periods, replace comma with period, cast to Decimal.
- Material number (MATNR) is internally 18-char zero-padded (000000000DIESEL01) but ALV exports strip leading zeros (DIESEL01). Store as CharField, never cast to int.
- Vendor number (Lieferant) preserves leading zeros: 0000100023. Also store as CharField.
- Movement type 101 = goods receipt from purchase order. Movement type 102 = reversal of 101. A naive parser that sums all Menge values will double-count reversals. The parser must negate quantity for reversal movement types (102, 202, 262).

### What the Sample Data Looks Like
4 rows of tab-separated data with:
- Row 1-2: Standard diesel goods receipts (movement type 101) at plant 1100, 1,500L and 2,250L
- Row 3: Natural gas receipt at plant 1200, 45.8 M3, with blank Lieferant (vendor) — because the utility supplier isn't tracked as a PO vendor in this scenario
- Row 4: A reversal (movement type 102) of 500L at plant 1100 — the parser must negate this quantity

This sample is designed to test three parser edge cases: (1) German decimal parsing, (2) blank vendor field, (3) reversal movement type sign correction.

### What Would Break in a Real Deployment
- Custom ALV layouts. The standard MB51 layout may be modified by the client's SAP admin — columns reordered, removed, or added. A production parser needs a configurable column mapping, not hardcoded positions.
- Custom movement types. SAP allows custom 3-digit movement types (e.g., Z01, Z02). The reversal detection logic (negate for 102/202/262) must be extended to include client-specific reversals.
- Multiple company codes. A multinational client may have GB01 (UK), DE01 (Germany), FR01 (France) in the same export. The parser needs to handle this; the current model's company_code field supports it.
- Batch/charge tracking. For regulated fuel types (aviation fuel, marine diesel), the Charge (batch) field carries traceability data. Our parser stores it in source_raw but doesn't use it for carbon calculation.

---

## 2. UK Electricity — Half-Hourly Settlement Data

### Sources Consulted
- Elexon BSC (Balancing and Settlement Code) documentation — Settlement Period definitions, Profile Class 00 (HH metering) requirements. https://www.elexon.co.uk/bsc-and-procedures/bsc-documentation
- Stark (formerly MHR, now Stark ID) — portal export documentation, CSV format specifications. https://www.starkgroup.co.uk
- UK electricity industry standard data flow specifications — D0036 (HH data file format) for understanding the underlying structure that portal exports simplify.

### What I Learned
- UK electricity is settled in 48 half-hourly periods per day (00:00-00:30, 00:30-01:00, ..., 23:30-00:00). This is defined by the BSC, not by individual suppliers.
- MPAN (Meter Point Administration Number) is a 13-digit identifier. The first digit is the DNO (Distribution Network Operator) region code. It must be stored as a string — Excel and naive CSV parsers will cast it to a float (1.01234568e+12), losing the last digits and making meter identification impossible.
- Stark portal exports come in wide format: one row per meter per day, with 48 columns for kWh readings. Between each kWh column is a status flag column: 00:00, 00:00 Status, 00:30, 00:30 Status, etc. Status flags: A=Actual (metered reading), E=Estimated (communication failure), S=Substituted (replaced by historical average). Your data quality dashboard should surface rows where any flag ≠ A.
- Clock-change days: on the last Sunday in March (BST start), the day has only 23 hours → 46 settlement periods (columns 01:00 and 01:30 are absent). On the last Sunday in October (GMT return), the day has 25 hours → 50 settlement periods (columns 01:00a and 01:30a are added). The parser must NOT assume exactly 48 columns — use regex to identify period columns dynamically.
- The file has 4 header rows (export metadata) before the column header row. Parser must skip until it finds 'MPAN' as the first cell.
- Total kWh column is a pre-calculated sum. Do not trust it blindly — recalculate from individual periods and flag discrepancies. A discrepancy reveals that some periods were estimated or substituted after the total was calculated.
- Reactive power (kVArh) is present in some exports. It's irrelevant for carbon calculation (only real power matters for Scope 2) but must be handled gracefully by the parser.

### What the Sample Data Looks Like
4 rows of CSV data across 2 meters and 2 days:
- Meter 1 (MPAN 1012345678901): 2 days with all-A (actual) readings on day 1, but periods 01:00 and 01:30 showing E (estimated) on day 2 — simulates a communication dropout
- Meter 2 (MPAN 1098765432109): period 01:30 on day 1 showing S (substituted) — simulates historical average substitution
- Daily totals: 187.4 kWh, 184.2 kWh, 91.2 kWh, 89.7 kWh

This sample tests: (1) multi-meter parsing, (2) status flag detection for data quality, (3) the has_estimated_periods boolean derivation.

### What Would Break in a Real Deployment
- Different portal formats. Stark, Utilitec, and direct DNO exports have slightly different column layouts. Some use HH01-HH48 numbering instead of 00:00-23:30 time labels. A production parser needs a configurable column detection strategy.
- Gas meters (MPRN). The same client may have gas meters with MPRN identifiers and kWh readings from a different portal. The model's mpan field would need renaming to meter_id, or a separate field added.
- Reactive power billing. Large industrial consumers are billed for reactive power (kVArh). While not relevant for carbon, the client may want to see it in a dashboard. Our model stores it in source_raw but doesn't surface it.
- Timezone edge cases. HH data is in UK local time (GMT/BST). If a client has facilities in Ireland (IST, same as GMT/BST) and continental Europe (CET), the settlement periods don't align. This platform assumes UK-only meters.

---

## 3. Corporate Travel — Navan CSV Export

### Sources Consulted
- Navan Help Centre — Configuring accounting export templates. https://help.navan.com/hc/en-us/articles/accounting-export-template
- Navan documentation on available export fields: Booking ID, Trip ID, Employee ID, Travel Date, Category, Flight Origin Airport, Cabin Class, Carrier Code, Hotel Name, Nights, Amount, Currency, Policy Status.
- Industry analysis: Navan (formerly TripActions) has been gaining enterprise market share since 2020, particularly among companies that went through travel program RFPs during the post-COVID restart. New enterprise contracts in 2024-2025 are increasingly Navan vs. Concur.

### What I Learned
- Navan does NOT have a fixed CSV schema. Admins configure export templates under Admin → Expense Admin → Accounting Preferences → Export Template. The columns in our sample represent a sensible ESG-oriented template that a Breathe ESG implementation consultant would configure for a new client.
- Flight distance is NEVER provided in Navan exports. You get origin_iata and destination_iata only. Distance must be inferred via haversine from airport coordinates. This is the single most important known gap in travel data for carbon calculation — and it's universal across all travel management platforms (Concur, Navan, Egencia, etc.).
- Hotel data includes hotel_name, hotel_city, hotel_country, and nights. Distance is irrelevant for hotel carbon calculation — DEFRA uses a flat kgCO2e per room per night factor.
- Ground transport sometimes includes distance_km (if booked through Navan's ground transport feature) but often doesn't (if the traveller took a taxi and expensed it). Missing distance → NULL emission → flagged row.
- Category values are lowercase in most templates (flight, hotel, ground_transport) but some template configurations produce capitalised values (Flight, Hotel). Parser must normalise to lowercase.
- Multi-leg flights (e.g., LHR→JFK→LAX) create separate rows with the same Trip ID. Each leg has its own Booking ID. The parser should calculate emissions per leg, not per trip — a long-haul leg and a domestic leg have different emission factors.
- Policy Status indicates whether the booking was within travel policy. out_of_policy bookings should still have emissions calculated — carbon doesn't care about policy compliance — but should be flagged in the dashboard.

### What the Sample Data Looks Like
6 rows representing two trips:
- Trip 1 (TRP-001, Sarah Chen): LHR→JFK outbound flight, 3-night hotel in New York (Marriott Times Square), taxi ground transport with distance (12.4km), JFK→LHR return flight. All approved.
- Trip 2 (TRP-002, James O'Brien): MAN→AMS flight (out_of_policy), taxi ground transport without distance.

This sample tests: (1) haversine distance inference for flights (LHR-JFK ≈ 5,541km → long-haul), (2) hotel emission calculation (3 nights × 33.4 kgCO2e/night for non-UK hotel), (3) ground transport with distance (12.4km × 0.14886 = 1.85 kgCO2e), (4) ground transport without distance (NULL → flagged), (5) out-of-policy flag handling, (6) multi-currency (GBP domestic, USD international, EUR on return ground).

### What Would Break in a Real Deployment
- Unknown IATA codes. If a traveller books a flight to a small regional airport not in the OurAirports dataset, haversine returns None and the emission is NULL. The analyst needs a manual override workflow for these cases.
- Rail travel. Navan supports rail bookings (particularly Eurostar, Avanti West Coast, LNER for UK clients). Rail has different emission factors from flights and uses CRS station codes (3-char, like MCV for Manchester Victoria) instead of IATA codes. The parser's origin_iata field is misnamed for rail — it should be origin_code with a separate code_type field. This is a known model imprecision.
- Personal vs. business travel. Some bookings are personal travel expensed through corporate — these should be excluded from Scope 3 reporting. The platform has no way to distinguish these without a policy_type field or manual analyst tagging.
- Connecting flights. A LHR→FRA→NRT itinerary (connecting in Frankfurt) may appear as one booking with two legs, or two separate bookings. The haversine for LHR→NRT direct (9,560km) differs from LHR→FRA (660km) + FRA→NRT (9,360km) = 10,020km. The per-leg approach is more accurate but requires the export to show legs separately.

---

## 4. Emission Factors — DEFRA/DESNZ 2024

### Sources Consulted
- UK DESNZ/DEFRA — Greenhouse Gas Conversion Factors for Company Reporting 2024. Published annually on GOV.UK.
  https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting
- DEFRA 2024 Condensed Set spreadsheet — worksheets: 'Business travel- air', 'Hotel stay', 'Fuels', 'UK electricity'
- DEFRA Methodology Paper 2024 — explains how factors are derived, including Radiative Forcing Index (RFI) for flights.

### What I Learned
- Flight factors are in kgCO2e per passenger-km and vary by haul type and cabin class. DEFRA 2024 values used:
  - Domestic economy: 0.25527
  - Short-haul (<3,700km) economy: 0.15353
  - Short-haul business: 0.22943
  - Long-haul (≥3,700km) economy: 0.19085
  - Long-haul premium economy: 0.28627
  - Long-haul business: 0.42872
  - Long-haul first: 0.76344
- These factors INCLUDE Radiative Forcing Index (RFI) — do not apply a separate RFI multiplier on top.
- Domestic is defined by airport location (both in UK), NOT by distance. Using distance as a proxy (e.g., <463km) misclassifies real UK routes: LHR-EDI is 534km, LHR-GLA is 561km, LHR-INV is 852km.
- Hotel factors: 11.6 kgCO2e per room per night (UK), 33.4 kgCO2e per room per night (non-UK). Derived from Cornell Hotel Sustainability Benchmarking (CHSB) index.
- Ground transport: taxi 0.14886 kgCO2e/km, National Rail 0.03549 kgCO2e/km, bus 0.10275 kgCO2e/km.
- Fuel: diesel 2.516 kgCO2e/litre, natural gas 0.1829 kgCO2e/kWh.
- UK grid electricity: the factor varies by year (currently ~0.207 kgCO2e/kWh for 2024) and is published in the 'UK electricity' tab.
- DEFRA released a mid-year correction in October 2024 to fix rounding errors in several factors. This confirms the need for versioned EmissionFactor storage — hardcoded values would require a code deploy to fix.

### What the Sample Data Looks Like
14 seed rows in the EmissionFactor table covering: 7 flight factors (by haul × class), 2 hotel factors (UK/world), 3 ground transport factors (taxi/train/bus), 2 fuel factors (diesel/natural gas). All with valid_from=2024-01-01, valid_to=NULL (currently active), source='DEFRA/DESNZ GHG Conversion Factors 2024'.

### What Would Break in a Real Deployment
- International emission factor databases. Non-UK operations need country-specific grid factors (e.g., France has very low grid emissions due to nuclear; Germany has higher due to coal). DEFRA provides UK factors only. For global operations, you'd need IEA or country-specific databases.
- Factor granularity. DEFRA's hotel factor is a single number per country region. In reality, a luxury hotel in central London has different emissions than a budget hotel in rural Wales. Client-specific or supplier-specific factors would be more accurate but harder to source.
- Annual updates. DEFRA publishes new factors every June-July. The platform needs an operational process (not a code deploy) to load new factors each year. The EmissionFactor model supports this via valid_from/valid_to versioning and Django Admin.

---

## 5. Airport Coordinates — OurAirports

### Sources Consulted
- OurAirports — Global airport database (public domain). https://ourairports.com/data/
- File: airports.csv — contains IATA code (iata_code), latitude (latitude_deg), longitude (longitude_deg) for ~7,500 airports with IATA codes.
- Licence: Public domain, suitable for commercial use without attribution requirement.

### What I Learned
- OurAirports provides coordinates for approximately 7,500 airports with IATA codes, covering all major commercial airports globally.
- Some smaller airports have IATA codes but are missing from the dataset (or have placeholder coordinates). The parser returns None for unknown codes, which produces NULL distance → NULL emission → flagged row.
- The dataset includes closed airports and military airfields that have IATA codes. These are unlikely to appear in corporate travel data but should be handled gracefully.

### What Would Break in a Real Deployment
- IATA code changes. Airports occasionally get new IATA codes (e.g., when Berlin Tegel TXL closed and Berlin Brandenburg BER opened). The coordinates file needs periodic updates.
- Shared IATA codes. Some cities have metropolitan area codes (e.g., NYC covers JFK, LGA, EWR). If a Navan export uses NYC instead of the specific airport, the haversine will use metropolitan coordinates, which may differ from the actual airport by 10-20km — negligible for emission calculation purposes.
