# Breathe ESG — Data Model Documentation

## Overview

The Breathe ESG data model consists of four Django models that handle the full lifecycle of emissions data: ingestion, storage, calculation, and audit.

- **IngestionJob** — tracks each file upload as a batch, recording who uploaded what, when, and whether parsing succeeded or failed.
- **EmissionRow** — the central table. One row per emission-generating activity, regardless of source. All three sources (SAP MM fuel, HH electricity, Navan travel) write to this single table.
- **EmissionFactor** — versioned lookup table of DEFRA/DESNZ emission factors. Never overwritten — new factor releases are appended with date ranges.
- **AuditLog** — append-only record of every analyst action. INSERT only, no UPDATE, no DELETE.

The relationships are straightforward:

- **Client** 1:N **IngestionJob** — one client, many uploads
- **IngestionJob** 1:N **EmissionRow** — one upload, many rows
- **EmissionRow** N:1 **EmissionFactor** — many rows share one factor
- **EmissionRow** 1:N **AuditLog** — one row, many audit events
- **IngestionJob** 1:N **AuditLog** — one job, many audit events

---

## Why One Unified EmissionRow Table

The obvious alternative is three source-specific tables: `SapEmissionRow`, `UtilityEmissionRow`, `TravelEmissionRow`. Here is why a single table with a `source_type` enum is the better choice for a carbon reporting workload.

**Query simplicity.** The analyst dashboard's primary query is: "what are our total emissions for March 2024?" With one table, that is:

```sql
SELECT SUM(normalized_kgco2e)
FROM emission_row
WHERE activity_date BETWEEN '2024-03-01' AND '2024-03-31';
```

With three tables, you need a `UNION ALL` across three tables with different column layouts, or a materialised view that denormalises them back into one table anyway. Every dashboard filter — by scope, by date range, by client — requires the same UNION. The complexity compounds.

**No data loss.** The `source_raw` JSONField on every row preserves the original data exactly as it arrived from the source system. A SAP row stores the full German-locale SAP record. An HH row stores all 48 half-hourly readings and their status flags. A Navan row stores the complete booking record. Nothing is lost by flattening into a common schema because nothing is flattened — the raw data is kept verbatim alongside the normalised fields.

**Deliberate denormalisation.** Source-specific fields (`plant_code`, `mpan`, `origin_iata`, etc.) are nullable and populated only for their respective `source_type`. On any given row, roughly 60% of columns are NULL. This is a deliberate choice. The alternative — normalised junction tables like `SapDetail`, `UtilityDetail`, `TravelDetail` — adds JOIN complexity without adding query value. Carbon reporting queries filter by `source_type` and `activity_date`, not by junction table relationships.

**Extensibility.** Adding a fourth source (e.g. fleet telematics, waste disposal manifests) means adding nullable fields to one table plus writing a new parser. It does not require a new table, new API endpoints, new serialisers, or new dashboard components. The `source_type` enum gains one more value.

**Storage efficiency.** PostgreSQL stores NULLs efficiently — one bit per field in the null bitmap, not one byte. A row with 20 NULL fields costs 20 bits (~2.5 bytes) of overhead, not 20 × field_size bytes. The storage penalty for wide-and-sparse is negligible compared to the query simplicity gained.

The tradeoff is schema aesthetics. The model has many nullable fields, which looks uncomfortable in a schema diagram. That discomfort is the price of not making every dashboard query a three-table UNION.

---

## Model: IngestionJob

`IngestionJob` represents a single file upload — one SAP export, one month of HH data, one Navan travel dump. It is the parent of every `EmissionRow` created from that file.

### Fields

| Field | Type | Why It Exists |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4)` | Avoids sequential integer IDs. Prevents enumeration attacks ("try job ID 1, 2, 3..."). Works across distributed systems without a central sequence. |
| `client_id` | `ForeignKey('Client', on_delete=PROTECT)` | Links upload to a client. `PROTECT` prevents deleting a client that has emission data — you never orphan audited records. |
| `source_type` | `CharField(choices=SourceType)` | Determines which parser runs: `sap_mm`, `utility_hh`, or `travel_navan`. Set by the upload endpoint based on file type or user selection. |
| `original_filename` | `CharField(max_length=255)` | Audit trail. When a regulator asks "where did row X come from?", you trace back to this filename. Also used for idempotency — same filename + same file hash = skip re-upload. |
| `uploaded_by` | `ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)` | Who uploaded the file. Non-negotiable for audit. `PROTECT` ensures you cannot delete a user who uploaded data. |
| `uploaded_at` | `DateTimeField(auto_now_add=True)` | When the file was uploaded. Distinct from `completed_at`. |
| `status` | `CharField(choices=Status)` | `pending` → `processing` → `complete` / `failed` / `partial`. The `partial` status is critical: a real SAP export of 500 rows will have 3-5 bad rows (invalid dates, missing fields, encoding errors). The system must not reject the entire file because of 3 bad rows. `partial` means "847 of 850 rows ingested, 3 errors — here are the errors." |
| `row_count_total` | `IntegerField(null=True, blank=True)` | Total rows in the source file. Populated after parsing. |
| `row_count_success` | `IntegerField(null=True, blank=True)` | Rows successfully ingested. The analyst sees "847 of 850" not just "complete". |
| `row_count_error` | `IntegerField(null=True, blank=True)` | Rows that failed parsing. |
| `error_detail` | `JSONField(null=True, blank=True)` | Per-row error messages. Example: `[{"row": 42, "error": "Buchungsdatum '20241301' is not a valid date", "raw": {...}}]`. This lets the analyst fix the source file and re-upload with targeted corrections. |
| `completed_at` | `DateTimeField(null=True, blank=True)` | NULL while processing. Set on completion (regardless of success/failure/partial). The frontend polls `status` for progress; `completed_at` is for audit. |

### Why IngestionJob Exists

Without a batch-level parent model, you cannot:

1. **Reprocess a bad file.** If 3 rows out of 850 had parsing errors, the analyst fixes the source file and re-uploads. The system needs to know "these 847 rows came from the first upload — delete them and reprocess." Without IngestionJob, you don't know which rows belong to which upload.

2. **Show batch context.** The analyst needs to see "this batch of 847 rows came from file `MB51_March2024.txt` uploaded at 14:32 by Sarah Chen." That metadata lives on IngestionJob, not on 847 individual EmissionRows.

3. **Implement idempotency.** If the same file is uploaded twice (accidentally, or after a timeout), the system should detect the duplicate at the batch level (same filename + same file hash) and skip it. Row-by-row dedup via `idempotency_key` is the second line of defence, not the first.

---

## Model: EmissionRow

The central table. Every emission-generating activity — a diesel delivery, a day of electricity consumption, a flight — becomes one row here.

### Identity Fields

| Field | Type | Why It Exists |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4)` | Same rationale as IngestionJob — no sequential enumeration. |
| `ingestion_job` | `ForeignKey(IngestionJob, on_delete=PROTECT, related_name='emission_rows')` | Links row to its parent batch. `PROTECT` prevents deleting a job that still has rows — forces explicit cleanup. |
| `source_type` | `CharField(choices=SourceType)` | Denormalised from IngestionJob. Yes, you could join to get source_type. But the dashboard query `WHERE source_type = 'sap_mm' AND activity_date BETWEEN ...` runs on EmissionRow directly — avoiding the join matters at scale. |
| `source_raw` | `JSONField` | The original row exactly as it arrived. If a CSRD auditor asks "what did the SAP export actually say?", you show `source_raw`. This field is never modified after creation. It is the immutable audit anchor. |
| `idempotency_key` | `CharField(max_length=100, unique=True)` | Prevents duplicate ingestion at the database level. The unique constraint does the work — no application-layer dedup logic needed. Composition varies by source: SAP uses `Materialbeleg` (document number), HH uses `MPAN+Date` (one reading per meter per day after daily aggregation), Navan uses `Booking ID`. If a user re-uploads the same file, the unique constraint catches duplicates on INSERT and the parser skips them. |

### Time Fields

| Field | Type | Why It Exists |
|---|---|---|
| `activity_date` | `DateField` | When the emission-generating activity occurred. Not when the data was uploaded (that is `IngestionJob.uploaded_at`). For SAP: `Buchungsdatum` (posting date). For HH: the settlement date. For Navan: Travel Date. This distinction matters — a fuel delivery on March 15 uploaded on April 2 should appear in the March report, not April. |

### Raw Fields

| Field | Type | Why It Exists |
|---|---|---|
| `raw_value` | `DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)` | The quantity from the source, in source units. For SAP: `Menge` (litres of diesel, cubic metres of gas), sign-corrected for reversals. For HH: daily kWh total (aggregated from 48 half-hourly readings). For Navan flights: inferred distance in km (haversine result); for hotels: number of nights. Nullable because some rows arrive with missing data — a Navan ground transport expense without `distance_km` has no raw_value. |
| `raw_unit` | `CharField(max_length=20, null=True, blank=True)` | The unit exactly as the source expressed it: `L`, `KG`, `M3`, `kWh`, `km`, `room_night`. Stored as-is, not normalised. This preserves the source's own terminology for audit. When an auditor asks "what units did the SAP export use?", you show `raw_unit`, not a normalised label your system invented. |

### Normalised Fields

| Field | Type | Why It Exists |
|---|---|---|
| `scope` | `CharField(max_length=1, choices=Scope, null=True, blank=True)` | GHG Protocol scope classification. SAP fuel = Scope 1 (direct combustion). Electricity = Scope 2 (purchased energy). Travel = Scope 3 (value chain). Nullable because scope assignment can be ambiguous — natural gas used for on-site electricity generation could be Scope 1 or Scope 2 depending on whether you're reporting location-based or market-based. |
| `emission_factor_used` | `ForeignKey('EmissionFactor', on_delete=PROTECT, null=True, blank=True)` | Points to the exact EmissionFactor row used to calculate `normalized_kgco2e`. This FK is critical for factor correction workflows. When DEFRA releases corrected factors (they did this in October 2024), you query `EmissionRow.objects.filter(emission_factor_used=old_factor)` and reprocess only those rows. Without this FK, you would have to reprocess every row in the system. `PROTECT` prevents deleting a factor that is referenced by emission data. |
| `normalized_kgco2e` | `DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)` | **This is the most important design decision in the model.** This field is nullable, not zero-defaulted. The distinction matters: |

**Why `normalized_kgco2e` is nullable:**

- **NULL** means "we could not calculate an emission for this row." The parser encountered missing data (no flight distance, unknown IATA code, missing fuel quantity) and correctly produced no result. This surfaces as a flagged row in the analyst dashboard — it demands attention.

- **0.0** means "this activity produced zero emissions." This is a legitimate value — for example, electricity from a 100% renewable tariff with a market-based zero grid factor.

- If you default missing data to 0.0, you silently undercount emissions. A taxi trip without a distance becomes `0.0 kgCO2e` instead of "unknown." An auditor would flag this as a material misstatement — the emission did not disappear because you failed to calculate it.

- NULL `normalized_kgco2e` triggers `is_flagged = True` on the row, which surfaces in the analyst dashboard. The analyst can then investigate, fill in the missing data, and approve the row. This is the correct workflow for audited carbon data.

### Source-Specific Fields

These fields are grouped by source type. All are nullable. On any given row, only the fields relevant to that row's `source_type` are populated; the rest are NULL.

**SAP MM fields:**

| Field | Type | Notes |
|---|---|---|
| `plant_code` | `CharField(max_length=4)` | `Werk`. SAP plant code, e.g. `1100`. Identifies which physical facility received the fuel. |
| `company_code` | `CharField(max_length=4)` | `Buchungskreis`. SAP company code, e.g. `GB01`. Identifies the legal entity. |
| `material_code` | `CharField(max_length=40)` | `Material`. SAP material number. Stored as string — SAP internally zero-pads to 18 chars but ALV exports strip leading zeros. |
| `movement_type` | `CharField(max_length=3)` | `Bewegungsart`. 3-digit SAP movement type. `101` = goods receipt from PO, `102` = reversal. The parser negates `raw_value` for reversal types. |
| `cost_centre` | `CharField(max_length=10, null=True)` | `Kostenstelle`. Nullable even within SAP — blank when the posting targets a WBS element instead of a cost centre. |

**Utility HH fields:**

| Field | Type | Notes |
|---|---|---|
| `mpan` | `CharField(max_length=13)` | Meter Point Administration Number. Always stored as string, never as integer. The leading digit is a DNO region code — casting to int (or letting Excel autoformat) destroys it. |
| `meter_serial` | `CharField(max_length=20, null=True)` | Physical meter serial number. Sometimes absent in Stark exports when MPAN alone is sufficient for identification. |
| `has_estimated_periods` | `BooleanField(null=True)` | True if any of the 48 half-hourly readings for that day had a BSC status flag of `E` (Estimated) or `S` (Substituted) instead of `A` (Actual). This single boolean lets you answer "what percentage of our Scope 2 data is based on metered readings vs. estimates?" — a real regulatory question under SECR and CSRD. |

**Navan Travel fields:**

| Field | Type | Notes |
|---|---|---|
| `travel_category` | `CharField(max_length=20)` | `flight`, `hotel`, `ground_transport`, `rail`. Determines which emission factor to look up. |
| `origin_iata` | `CharField(max_length=3, null=True)` | IATA airport code. Blank for hotel and ground transport rows. |
| `destination_iata` | `CharField(max_length=3, null=True)` | Same. |
| `cabin_class` | `CharField(max_length=20, null=True)` | `economy`, `premium_economy`, `business`, `first`. Blank for non-flight. Determines which DEFRA flight factor to use within a haul category. |
| `carrier_code` | `CharField(max_length=2, null=True)` | IATA airline code, e.g. `BA`, `KL`. Metadata for analysis; not used in emission calculation (DEFRA factors are not airline-specific). |
| `hotel_country` | `CharField(max_length=2, null=True)` | ISO 3166-1 alpha-2 country code. Used to select UK (11.6 kgCO2e/night) vs. non-UK (33.4 kgCO2e/night) hotel factor. |
| `nights` | `IntegerField(null=True)` | Number of hotel room nights. Blank for non-hotel. |
| `inferred_distance_km` | `DecimalField(max_digits=10, decimal_places=2, null=True)` | Haversine result for flights. Kept as a separate field from `raw_value` to distinguish "distance the source provided" (which is always NULL for flights) from "distance we calculated." The provenance of a number matters in audited data. |
| `booking_id` | `CharField(max_length=30, null=True)` | Navan booking reference. Used as the `idempotency_key` for travel rows. |
| `employee_id` | `CharField(max_length=20, null=True)` | Internal employee identifier from HR integration. |

### Data Quality Fields

| Field | Type | Why It Exists |
|---|---|---|
| `is_flagged` | `BooleanField(default=False)` | Set True when `normalized_kgco2e` is NULL, when distance is missing for ground transport, when a reversal movement type has a positive quantity, or when HH readings contain estimated periods. This is the primary filter for the analyst's review queue. |
| `flag_reason` | `CharField(max_length=255, null=True)` | Human-readable reason for the flag. Examples: "Missing distance_km for ground transport", "Movement type 102 with positive quantity — possible sign error", "Estimated HH readings detected (3 of 48 periods)". |
| `is_approved` | `BooleanField(default=False)` | Analyst must explicitly approve a flagged row before it counts in aggregate reports. Unapproved rows are excluded from `SUM(normalized_kgco2e)` queries in the reporting layer. |
| `approved_by` | `ForeignKey(AUTH_USER_MODEL, on_delete=SET_NULL, null=True)` | Who approved it. `SET_NULL` (not PROTECT) because deleting a user account should not cascade to emissions data — the data remains, the approval attribution becomes NULL. |
| `approved_at` | `DateTimeField(null=True)` | When approval occurred. |

### Indexes

Each index serves a specific query pattern:

| Index | Query It Serves |
|---|---|
| `(source_type, activity_date)` | Dashboard filtering: "show me all SAP rows from March 2024" |
| `(ingestion_job)` | Batch operations: "show me all rows from this upload" / "delete all rows from failed job X" |
| `(mpan, activity_date)` | Utility-specific: "show me daily readings for meter 1012345678901" |
| `(idempotency_key)` | Unique constraint enforcement — database-level duplicate detection on INSERT |

---

## Model: AuditLog

### Why It Exists as a Separate Table

Auditors — both internal compliance teams and external firms like KPMG, Deloitte, or EY — need an immutable record of every analyst action on the emissions data. This is not optional. Under CSRD and the UK's SECR, companies must demonstrate that their emissions data has been subject to adequate controls. An audit trail is one of those controls.

The alternative — audit fields on EmissionRow (`last_edited_by`, `last_edited_at`) — only captures the most recent action. If an analyst edits a diesel quantity from 12,000L to 1,200L (correcting a decimal comma error), and then a second analyst reverts it back, the audit fields show only the revert. The original edit — and the fact that it was a factor-of-10 correction — is lost. You cannot reconstruct the timeline.

### Why It Is Append-Only

"Append-only" means INSERT only. No UPDATE. No DELETE. Ever.

This is not a code convention or a team agreement. In production, the database role that the Django application uses should have `INSERT`-only permissions on the `audit_log` table. `UPDATE` and `DELETE` should be revoked at the PostgreSQL level. If a developer or admin needs to correct an AuditLog entry, they insert a new correction row — they never modify an existing one.

This is what makes the audit trail tamper-evident. An auditor can verify that the earliest `timestamp` in the table predates the audit engagement, and that no rows have been modified since. If the application had UPDATE permissions, this guarantee would not hold.

### Fields

| Field | Type | Why It Exists |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4)` | Unique identifier for each audit event. |
| `timestamp` | `DateTimeField(auto_now_add=True, db_index=True)` | When the action occurred. Indexed for chronological queries. `auto_now_add` ensures the timestamp is set by the database, not by application code — preventing backdating. |
| `user` | `ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)` | Who performed the action. `PROTECT` prevents deleting a user who has audit history — the history must survive the user's departure. |
| `action` | `CharField(choices=Action)` | What was done. Values: `approve` (analyst approved a flagged row), `flag` (analyst flagged a row for review), `edit` (analyst changed a value), `revert` (analyst reverted a previous edit), `upload` (file was uploaded), `reprocess` (job was reprocessed with updated parsers or factors). |
| `emission_row` | `ForeignKey(EmissionRow, on_delete=PROTECT, null=True)` | The target row for row-level actions. NULL for job-level actions like `upload` and `reprocess`. |
| `ingestion_job` | `ForeignKey(IngestionJob, on_delete=PROTECT, null=True)` | The target job for job-level actions. NULL for row-level actions. |
| `before_value` | `JSONField(null=True)` | For `edit` actions: the previous state of the fields that changed. Example: `{"raw_value": "12000.000000", "normalized_kgco2e": "30192.000000"}`. |
| `after_value` | `JSONField(null=True)` | For `edit` actions: the new state. Example: `{"raw_value": "1200.000000", "normalized_kgco2e": "3019.200000"}`. |
| `note` | `TextField(null=True)` | Analyst's free-text justification. Example: "Corrected diesel quantity — supplier invoice shows 1,200L not 12,000L. Decimal comma error in SAP export." This is what the auditor reads. |

The `before_value` / `after_value` pair creates a complete edit history. A compliance officer can reconstruct the full timeline of any data point: who changed what, when, and why. This is the table that auditors actually look at.

---

## Model: EmissionFactor

### Why Emission Factors Are in a Database Model

The naive approach is to hardcode DEFRA factors as Python constants in the parser module:

```python
DEFRA_DIESEL_KGCO2E_PER_LITRE = 2.516  # Don't do this
```

This fails for three reasons:

1. **DEFRA publishes updated factors annually.** The 2025 factors will differ from 2024. Hardcoded constants require a code deploy to update — unacceptable for a production platform where factor updates are an operational task, not a development task.

2. **DEFRA releases mid-year corrections.** In October 2024, they corrected rounding errors in several factors. A hardcoded value cannot be corrected without redeploying the application.

3. **Historical rows must preserve the factor that was used at ingest time.** If you recalculate 2024 emissions with 2025 factors, you get a different number — and both numbers are correct for their respective reporting periods. The `EmissionRow.emission_factor_used` FK points to the exact `EmissionFactor` row that was current when the emission was calculated. Historical rows are not silently updated when new factors arrive.

### Fields

| Field | Type | Why It Exists |
|---|---|---|
| `source_type` | `CharField(choices=SourceType)` | `flight`, `hotel`, `fuel`, `electricity`, `ground`. First-level classification. |
| `category` | `CharField(max_length=50)` | Second-level. Flights: `domestic`, `short_haul`, `long_haul`. Hotels: `uk`, `world`. Fuel: `diesel`, `natural_gas`, `lpg`. Ground: `taxi`, `train`, `bus`, `car`. |
| `sub_category` | `CharField(max_length=50, blank=True, default='')` | Third-level. Flights: `economy`, `premium_economy`, `business`, `first`. Empty string for non-flight sources — not NULL, to avoid composite unique constraint issues with NULL values in PostgreSQL. |
| `unit` | `CharField(max_length=50)` | The unit the factor is expressed in: `kgCO2e_per_pkm` (flights), `kgCO2e_per_room_night` (hotels), `kgCO2e_per_litre` (liquid fuel), `kgCO2e_per_kwh` (electricity, gas), `kgCO2e_per_km` (ground transport). |
| `factor_value` | `DecimalField(max_digits=18, decimal_places=9)` | The factor itself. **DecimalField, not FloatField.** IEEE 754 cannot represent 0.15353 exactly — it stores `0.15352999999999999...`. Over thousands of rows, `quantity × 0.15353` accumulates rounding error. Carbon accounting is audited to 2 decimal places of kgCO2e. A Scope 2 report showing 1,247.31 kgCO2e must be reproducible — if an auditor recalculates using the same inputs, they must get the same number. `DecimalField` uses Python's `decimal.Decimal`, which is exact for the precision specified. |
| `year` | `IntegerField` | Publication year of the source document (e.g. 2024). |
| `source` | `CharField(max_length=200)` | Citation. e.g. `'DEFRA/DESNZ GHG Conversion Factors 2024'`. |
| `source_url` | `URLField(blank=True)` | Direct URL to the publication. |
| `source_sheet` | `CharField(max_length=100, blank=True)` | Exact tab name in the DEFRA spreadsheet, e.g. `'Business travel- air'`. When an auditor asks "where does 0.19085 come from?", you answer: DEFRA 2024 Condensed Set → tab 'Business travel- air' → row 'Long-haul flights, to/from UK, Economy class'. |
| `valid_from` | `DateField` | First date this factor applies. Usually January 1 of the publication year, or the date of a mid-year correction. |
| `valid_to` | `DateField(null=True)` | NULL = currently active. Set to the last day of validity when superseded by a new factor. Lookup logic: `valid_from <= activity_date AND (valid_to IS NULL OR valid_to >= activity_date)`. |
| `created_at` | `DateTimeField(auto_now_add=True)` | When this factor row was added to the database. |
| `notes` | `TextField(blank=True)` | Implementation notes, e.g. "Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology — do not apply a separate RFI uplift." |

### Constraints

- `unique_together = [('source_type', 'category', 'sub_category', 'valid_from')]` — prevents inserting duplicate factors for the same classification and date range.
- Composite index on `(source_type, category, sub_category, valid_from)` for efficient factor lookup during emission calculation.

### Versioning Workflow

When DEFRA 2025 factors are published:

1. Set `valid_to = '2024-12-31'` on all 2024 factor rows.
2. Insert new rows with the 2025 values and `valid_from = '2025-01-01'`.
3. Historical EmissionRows retain their FK to the 2024 factor rows — their `normalized_kgco2e` values do not change.
4. New emissions ingested after the cutover date automatically pick up the 2025 factors.
5. If targeted reprocessing is needed (e.g. a client wants their Q4 2024 data recalculated with 2025 factors for comparison), you can query `EmissionRow.objects.filter(emission_factor_used__year=2024)` and reprocess only those rows.
