# Breathe ESG — Engineering Tradeoffs

This document records the deliberate tradeoffs made in the v1 implementation of the Breathe ESG data ingestion platform. These are not bugs, oversights, or apologies. They are engineering decisions made with awareness of what was excluded and why. Each section explains what was left out, why it was left out, what the consequence is, and what the path to resolution looks like.

---

## Tradeoff 1: FI/CO Cost Postings Not Ingested

**What was excluded:** SAP FI/CO (Finance & Controlling) module data — cost centre postings, G/L line items, spend amounts in currency.

**Why:** We chose SAP MM (Materials Management) because fuel procurement is tracked as a material goods receipt — you get physical quantities (litres, m³) which can be directly multiplied by DEFRA emission factors. FI/CO gives you spend amounts (£12,500 of diesel) which cannot be converted to kgCO2e without knowing the price-per-litre, which varies by supplier contract, delivery date, and hedging arrangements. Physical quantity is the more reliable input for carbon calculation.

**Consequence:** The platform cannot cross-check SAP fuel volumes against financial spend. In a real deployment, a sustainability analyst would want to verify that the 1,500L of diesel in MM matches the £2,250 invoice in FI/CO (at £1.50/L). Without FI/CO data, this reconciliation happens outside the platform — likely in Excel.

**Path to resolution:** Add a second SAP parser for FI/CO cost centre reports (transaction KSB1). Store financial data in a separate model (`CostPosting`) with a foreign key to `EmissionRow` for reconciliation. This is a 2–3 sprint effort. The data model does not need to change — `CostPosting` would reference the same `IngestionJob` and `Client` models.

**What I would ask:** "How often do MM quantities and FI/CO spend amounts disagree? Is this a monthly reconciliation or an annual audit check?"

---

## Tradeoff 2: Sub-Daily HH Granularity Not Stored

**What was excluded:** Individual 30-minute half-hourly readings. The parser aggregates 48 readings per meter per day into a single daily kWh total before storing in `EmissionRow`.

**Why:** 48 rows per meter per day × 365 days × 50 meters = 876,000 rows per year at raw resolution. For Scope 2 carbon reporting, which operates on monthly totals, sub-daily granularity adds storage cost and query complexity without adding reporting value. The DEFRA grid emission factor is an annual average — it does not vary by time of day. So a kWh consumed at 2am has the same emission factor as a kWh consumed at 2pm.

**Consequence:** You cannot answer time-of-use questions like "what percentage of our electricity consumption happens outside business hours?" or "does our night-shift consume more than our day-shift?" These are legitimate energy management questions, but they are not carbon reporting questions.

**Path to resolution:** Store raw HH readings in a separate time-series table (e.g. `HalfHourlyReading` with fields `mpan`, `period_start`, `kwh`, `status_flag`). Use TimescaleDB or PostgreSQL partitioned tables for query performance. `EmissionRow` continues to hold daily aggregates for carbon reporting. The two tables coexist — one for energy management, one for carbon reporting.

**What I would ask:** "Does the client have an energy management platform (e.g. Carbon Trust, Eevee, Utilitec dashboard)? If so, sub-daily analysis is their problem, not ours."

---

## Tradeoff 3: Concur SAE Not Supported

**What was excluded:** SAP Concur Standard Accounting Extract — a 200+ column pipe-delimited or fixed-width flat file, exported via SFTP. This is the dominant travel expense integration format for enterprises that signed Concur contracts before ~2018.

**Why:** The assignment already has two complex parsers: SAP MM (German locale, YYYYMMDD dates, decimal comma notation, movement type sign correction) and HH meter data (48-column pivot/melt, status flag interleaving, clock-change day handling). Adding a third hard parser (200+ columns, many undocumented, positional encoding) would demonstrate parsing endurance but not engineering judgment. The carbon calculation challenge — haversine distance from IATA codes, DEFRA factor selection by haul type and cabin class — is identical regardless of whether the input is Concur SAE or Navan CSV. Navan CSV surfaces the same calculation problem with a cleaner input format.

**Consequence:** The platform cannot ingest travel data from clients using Concur. Given that Concur has ~60% market share in enterprise travel management, this is a significant gap for production deployment.

**Path to resolution:** Add a Concur SAE parser. The `EmissionRow` model does not need to change — Concur flights have the same fields (origin, destination, cabin class) as Navan flights. The parser is the only new code. Key implementation risk: Concur SAE column layouts are client-specific — each enterprise configures their own SAE template. You would need a SAE column mapping configuration per client, not a hardcoded parser.

**What I would ask:** "What percentage of Breathe ESG's target clients use Concur vs. Navan vs. other platforms? Is there a single Concur SAE template we can start with, or does every client have a different layout?"

---

## Tradeoff 4: Multi-Currency Normalisation Not Implemented

**What was excluded:** Conversion of non-GBP transaction amounts to GBP. The platform stores the raw currency code (GBP, USD, EUR) but does not perform FX conversion.

**Why:** Currency normalisation requires a reliable FX rate source (e.g., ECB daily rates, Open Exchange Rates API), a decision about which rate to use (transaction date rate, month-end rate, annual average rate — each gives a different number), and handling of edge cases (weekend rates, bank holiday rates, future-dated bookings). This is a financial engineering problem, not a carbon engineering problem. Carbon calculation uses physical quantities (litres, kWh, km, room-nights) — the transaction amount in currency is metadata, not an input to the emission calculation.

**Consequence:** The analyst dashboard cannot show "total travel spend in GBP" across trips booked in different currencies. It can show total kgCO2e (which is currency-independent). If the client needs spend reporting, they need to normalise currencies in their finance system, not in the carbon platform.

**Path to resolution:** Add a `CurrencyRate` model with daily exchange rates from ECB or a commercial API. Add a `normalized_amount_gbp` field to `EmissionRow`. Apply FX conversion during ingestion using the transaction date's rate. This is a ~1 sprint effort but requires a decision on rate methodology (spot vs. average) that should come from the client's finance team.

**What I would ask:** "Does the client's sustainability report include spend data alongside emissions data? If not, currency normalisation is truly out of scope."

---

## Tradeoff 5: Scope 3 Supply Chain Emissions Not Covered

**What was excluded:** Scope 3 categories beyond business travel. The GHG Protocol defines 15 Scope 3 categories; this platform covers only Category 6 (Business Travel). Categories like Purchased Goods & Services (Cat 1), Capital Goods (Cat 2), Fuel & Energy Related Activities (Cat 3), Upstream Transportation (Cat 4), and Waste (Cat 5) are not handled.

**Why:** Each Scope 3 category requires a different data source, a different emission factor methodology, and often a different calculation approach (spend-based vs. activity-based vs. supplier-specific). Covering all 15 categories in a single sprint would produce superficial implementations that none would be production-ready. The three sources chosen (SAP MM for Scope 1 fuel, HH meter data for Scope 2 electricity, Navan CSV for Scope 3 travel) demonstrate the full technical range: file parsing, data normalisation, emission factor lookup, and data quality flagging. Adding more Scope 3 categories adds breadth without adding depth.

**Consequence:** The platform reports only partial Scope 3 emissions. Under CSRD, companies are required to report material Scope 3 categories — business travel alone is rarely the largest. Purchased Goods & Services (Category 1) typically accounts for 50–80% of a company's total Scope 3.

**Path to resolution:** Add parsers and emission factor sets for additional Scope 3 categories. Priority order based on typical materiality: (1) Purchased Goods & Services — requires supplier-specific or spend-based emission factors, (2) Employee Commuting — survey-based, (3) Upstream Transportation — freight carrier emissions data. Each category is a separate parser + factor set, using the same `EmissionRow` model with `source_type` enum extended.

**What I would ask:** "Which Scope 3 categories are material for this client? Run a materiality screening first — not all 15 categories are relevant to every business."

---

## Tradeoff 6: Real-Time API Ingestion Not Supported

**What was excluded:** Real-time or scheduled API integration with SAP, Stark, or Navan. All data enters the platform via manual file upload.

**Why:** API integration requires: (a) OAuth or API key credential management per client, (b) rate limiting and pagination handling, (c) incremental sync logic ("give me records since last sync"), (d) error recovery and retry logic, (e) monitoring and alerting for API failures. Each of these is a production engineering concern that adds complexity without changing the core carbon calculation logic. File upload demonstrates the same parsing, normalisation, and calculation pipeline with simpler I/O. For an assignment, the interesting part is what happens after the data arrives, not how it arrives.

**Consequence:** Data freshness depends on how often the analyst exports and uploads files. For SAP and Navan, this is typically monthly. For HH meter data, Stark portals support automated email delivery of CSVs — a lightweight alternative to API integration.

**Path to resolution:** Add a scheduled ingestion service using Celery or Django-Q. For SAP: implement OData integration via SAP Gateway (requires client-side configuration). For Stark: parse CSV attachments from automated email delivery (simpler than API). For Navan: use their Reporting API with OAuth2 service account authentication. Each integration is independent — start with whichever the client requests first.

**What I would ask:** "How frequently does the client need updated emissions data? Monthly is fine for annual reporting. Weekly might be needed for an internal dashboard. Daily or real-time is only needed if emissions data drives operational decisions."
