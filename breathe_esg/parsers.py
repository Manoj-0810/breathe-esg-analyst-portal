import re
import csv
import math
import codecs
from decimal import Decimal, InvalidOperation
from datetime import datetime
import pandas as pd
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from breathe_esg.models import IngestionJob, EmissionRow, EmissionFactor, AuditLog

User = get_user_model()

# --- UK Airports static set for domestic classification ---
UK_AIRPORTS = {
    'LHR', 'LGW', 'MAN', 'STN', 'LTN', 'BHX', 'EDI', 'GLA', 'BRS', 'NCL',
    'LBA', 'EMA', 'ABZ', 'INV', 'SOU', 'CWL', 'BHD', 'BFS', 'JER', 'GCI',
    'EXT', 'HUY', 'MME', 'NQY', 'BOH', 'SEN', 'DSA', 'PIK', 'LSI', 'BEB',
}

# --- Curated fallback dictionary of airport coordinates (lat, lon) ---
FALLBACK_AIRPORTS = {
    'LHR': (51.47002, -0.454295),
    'LGW': (51.148102, -0.190278),
    'MAN': (53.353744, -2.27495),
    'STN': (51.885, 0.235),
    'LTN': (51.8747, -0.36833),
    'BHX': (52.4539, -1.74803),
    'EDI': (55.950798, -3.363069),
    'GLA': (55.8719, -4.43306),
    'INV': (57.5425, -4.0475),
    'JFK': (40.639751, -73.778925),
    'AMS': (52.308611, 4.763889),
    'CDG': (49.009722, 2.547778),
    'FRA': (50.033333, 8.570556),
    'DXB': (25.252778, 55.364444),
    'SIN': (1.35019, 103.994003),
    'LAX': (33.942501, -118.407997),
    'SFO': (37.618999, -122.375),
    'ORD': (41.9786, -87.9048),
    'DFW': (32.896801, -97.038002),
    'ATL': (33.6367, -84.428101),
}


def load_iata_coords():
    """
    Attempt to load airport coordinates from 'airports.csv' in the project directory.
    If not found, fall back to the curated static fallback dictionary.
    """
    coords = FALLBACK_AIRPORTS.copy()
    try:
        # Check standard paths
        for path in ['airports.csv', '../airports.csv', 'breathe_esg/resources/airports.csv']:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        iata = row.get('iata_code')
                        lat = row.get('latitude_deg')
                        lon = row.get('longitude_deg')
                        if iata and lat and lon:
                            coords[iata.upper().strip()] = (float(lat), float(lon))
                break
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return coords


def haversine_km(origin_iata, dest_iata):
    """
    Calculate the great-circle distance between two airports in km using the haversine formula.
    Returns None if either IATA code coordinates are unknown.
    """
    coords = load_iata_coords()
    o_iata = origin_iata.upper().strip()
    d_iata = dest_iata.upper().strip()
    if o_iata not in coords or d_iata not in coords:
        return None

    lat1, lon1 = map(math.radians, coords[o_iata])
    lat2, lon2 = map(math.radians, coords[d_iata])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    
    EARTH_RADIUS_KM = 6371.0
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def parse_german_decimal(val_str):
    """
    Convert a German numeric string (e.g. "1.500,000" or "-2.250,50") to a Decimal.
    Also handles standard English formatting.
    """
    if not val_str:
        return None
    val_cleaned = val_str.strip()
    
    # Check if German: has period for thousands and comma for decimal
    if ',' in val_cleaned and '.' in val_cleaned:
        # e.g., 1.500,00 -> 1500.00
        val_cleaned = val_cleaned.replace('.', '').replace(',', '.')
    elif ',' in val_cleaned:
        # e.g., 1500,00 -> 1500.00
        # If there's only one comma, it could be decimal separator
        # Check if it looks like thousands or decimal
        parts = val_cleaned.split(',')
        if len(parts) == 2 and len(parts[1]) != 3:
            val_cleaned = val_cleaned.replace(',', '.')
        else:
            # Let's assume it's decimal if standard German
            val_cleaned = val_cleaned.replace(',', '.')
            
    try:
        return Decimal(val_cleaned)
    except InvalidOperation:
        raise ValueError(f"Invalid numeric value: '{val_str}'")


def find_latest_factor(source_type, category, sub_category='', date=None):
    """
    Query versioned EmissionFactor rows for a match.
    Selects active factor based on validity ranges:
    valid_from <= date AND (valid_to IS NULL OR valid_to >= date)
    """
    if not date:
        date = timezone.now().date()
        
    qs = EmissionFactor.objects.filter(
        source_type=source_type,
        category__iexact=category,
        sub_category__iexact=sub_category or '',
        valid_from__lte=date
    )
    
    # Filter by valid_to
    factors = []
    for f in qs:
        if f.valid_to is None or f.valid_to >= date:
            factors.append(f)
            
    if not factors:
        # Try finding one without sub_category as fallback if sub_category was provided
        if sub_category:
            return find_latest_factor(source_type, category, '', date)
        return None
        
    # Return the latest year or most recently created factor
    factors.sort(key=lambda x: x.year, reverse=True)
    return factors[0]


def process_file_decoding(file_object):
    """
    Robust reader that handles UTF-8 and falls back to windows-1252.
    Returns list of decoded string lines.
    """
    content = file_object.read()
    # Handle both memory upload files and file paths
    if isinstance(content, str):
        return content.splitlines()
        
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('windows-1252', errors='replace')
        
    return decoded.splitlines()


def parse_sap_mm(job):
    """
    Parses standard SAP MM MB51 tab-separated or semicolon-delimited exports.
    """
    lines = process_file_decoding(job.original_filename)  # Wait, job.original_filename is a path? No, let's open from job files.
    # In Django views we will pass the file object or cache it.
    # Let's design the functions to take either an open file object or a list of lines.
    # For safety, let's make the parser accept a list of lines or file object directly.
    # Let's check how we can write it.
    pass

# Let's write the real complete parser functions that take the file_data (as list of lines)
# and run the calculations. This makes it completely modular!

def run_sap_mm_parser(job, file_lines):
    if not file_lines:
        raise ValueError("File is empty.")

    # Auto-detect delimiter
    first_line = file_lines[0]
    delimiter = '\t' if '\t' in first_line else ';'
    
    reader = csv.reader(file_lines, delimiter=delimiter)
    header = None
    rows = list(reader)
    
    # Find header row (must contain Material, Menge, or Buchungskreis etc.)
    header_idx = -1
    for i, r in enumerate(rows):
        if any(h in ''.join(r) for h in ['Buchungskreis', 'Company Code', 'Material', 'Menge', 'Quantity']):
            header = [h.strip() for h in r]
            header_idx = i
            break
            
    if header is None:
        raise ValueError("Could not find standard ALV header row in SAP MM export.")
        
    # Clean headers (normalize to lowercase-snake-case)
    # We will map standard German and English headers to standard internal keys
    header_mapping = {
        'buchungskreis': 'company_code', 'company code': 'company_code',
        'werk': 'plant_code', 'plant': 'plant_code',
        'lagerort': 'storage_location', 'storage location': 'storage_location',
        'material': 'material_code', 'material number': 'material_code',
        'materialkurztext': 'material_text', 'material short text': 'material_text',
        'bewegungsart': 'movement_type', 'movement type': 'movement_type',
        'buchungsdatum': 'posting_date', 'posting date': 'posting_date',
        'belegdatum': 'document_date', 'document date': 'document_date',
        'menge': 'quantity', 'quantity': 'quantity',
        'meins': 'unit', 'unit of measure': 'unit',
        'kostenstelle': 'cost_centre', 'cost centre': 'cost_centre',
        'lieferant': 'vendor_number', 'vendor': 'vendor_number',
        'materialbeleg': 'document_number', 'material document': 'document_number',
        'jahr': 'year', 'fiscal year': 'year'
    }
    
    normalized_headers = []
    for h in header:
        h_lower = h.lower().strip()
        matched = False
        for k, v in header_mapping.items():
            if k == h_lower:
                normalized_headers.append(v)
                matched = True
                break
        if not matched:
            normalized_headers.append(h_lower.replace(' ', '_'))
            
    # We parse data rows starting after the header
    total_rows = 0
    success_rows = 0
    error_rows = 0
    errors = []
    
    # Fuel category mappings
    fuel_mappings = {
        'DIESEL': 'diesel',
        'GAS': 'natural_gas',
        'ERDGAS': 'natural_gas',
        'LPG': 'lpg',
        'PROPANE': 'lpg',
        'HEATING': 'diesel',  # heating oil / gasoil
    }
    
    for idx, r in enumerate(rows[header_idx + 1:]):
        # Skip empty rows or border lines (often SAP exports contain dashes lines)
        if not r or all(cell.strip() == '' or cell.strip().startswith('---') for cell in r):
            continue
            
        total_rows += 1
        raw_row_dict = {}
        for h_idx, col_name in enumerate(normalized_headers):
            if h_idx < len(r):
                raw_row_dict[col_name] = r[h_idx].strip()
                
        try:
            # Validate required fields
            document_number = raw_row_dict.get('document_number')
            posting_date_str = raw_row_dict.get('posting_date')
            quantity_str = raw_row_dict.get('quantity')
            unit = raw_row_dict.get('unit')
            material_code = raw_row_dict.get('material_code')
            
            if not document_number or not posting_date_str or not quantity_str:
                raise ValueError("Missing critical fields: Materialbeleg, Buchungsdatum, or Menge.")
                
            # Parse Date
            try:
                activity_date = datetime.strptime(posting_date_str, '%Y%m%d').date()
            except ValueError:
                raise ValueError(f"Invalid date format for Buchungsdatum '{posting_date_str}'. Expected YYYYMMDD.")
                
            # Parse Quantity
            raw_qty = parse_german_decimal(quantity_str)
            
            # Negate on reversal movement type (102, 202, 262)
            movement_type = raw_row_dict.get('movement_type')
            is_reversal = movement_type in ('102', '202', '262')
            if is_reversal and raw_qty > 0:
                raw_qty = -raw_qty
            elif not is_reversal and raw_qty < 0:
                # Reversal or negative correction
                is_reversal = True
                
            # Check Idempotency Key
            # SAP uses Materialbeleg as unique document number. We make it globally unique using DocumentNumber+Year
            fiscal_year = raw_row_dict.get('year', str(activity_date.year))
            idempotency_key = f"sap_mm_{document_number}_{fiscal_year}"
            
            # If already exists, we skip creating a duplicate, but count as success (idempotent)
            if EmissionRow.objects.filter(idempotency_key=idempotency_key).exists():
                success_rows += 1
                continue
                
            # Classify fuel
            fuel_category = None
            for key, cat in fuel_mappings.items():
                if material_code and key in material_code.upper():
                    fuel_category = cat
                    break
            if not fuel_category and raw_row_dict.get('material_text'):
                for key, cat in fuel_mappings.items():
                    if key in raw_row_dict.get('material_text').upper():
                        fuel_category = cat
                        break
                        
            # Normalize to Scope 1 & calculate emissions
            normalized_kgco2e = None
            is_flagged = False
            flag_reason = None
            factor_used = None
            
            if not fuel_category:
                is_flagged = True
                flag_reason = f"Unknown material code '{material_code}' — cannot map to fuel emission factor."
            else:
                # Look up factor
                factor_used = find_latest_factor(
                    source_type=EmissionFactor.SourceType.FUEL,
                    category=fuel_category,
                    date=activity_date
                )
                if not factor_used:
                    is_flagged = True
                    flag_reason = f"No emission factor found for fuel '{fuel_category}' on date {activity_date}."
                else:
                    normalized_kgco2e = raw_qty * factor_used.factor_value
                    
            # Check for anomalies: reversal with positive qty or vice versa
            if is_reversal and raw_qty > 0:
                is_flagged = True
                flag_reason = "Reversal movement type 102 with positive quantity — possible sign error."
                
            # Construct row
            row = EmissionRow(
                ingestion_job=job,
                source_type=EmissionRow.SourceType.SAP_MM,
                source_raw=raw_row_dict,
                idempotency_key=idempotency_key,
                activity_date=activity_date,
                raw_value=raw_qty,
                raw_unit=unit,
                scope=EmissionRow.Scope.SCOPE1,
                emission_factor_used=factor_used,
                normalized_kgco2e=normalized_kgco2e,
                plant_code=raw_row_dict.get('plant_code'),
                company_code=raw_row_dict.get('company_code'),
                material_code=material_code,
                movement_type=movement_type,
                cost_centre=raw_row_dict.get('cost_centre'),
                is_flagged=is_flagged,
                flag_reason=flag_reason
            )
            row.save()
            success_rows += 1
            
        except Exception as e:
            error_rows += 1
            errors.append({
                "row_number": idx + header_idx + 2,
                "error": str(e),
                "raw_row": raw_row_dict
            })
            
    # Update Job
    job.row_count_total = total_rows
    job.row_count_success = success_rows
    job.row_count_error = error_rows
    job.error_detail = errors
    if error_rows == 0:
        job.status = IngestionJob.Status.COMPLETE
    elif success_rows > 0:
        job.status = IngestionJob.Status.PARTIAL
    else:
        job.status = IngestionJob.Status.FAILED
        
    job.completed_at = timezone.now()
    job.save()


def run_utility_hh_parser(job, file_lines):
    if not file_lines:
        raise ValueError("File is empty.")

    # Find the data header row where the first cell is MPAN
    header_idx = -1
    for i, line in enumerate(file_lines):
        if line.strip().startswith('MPAN'):
            header_idx = i
            break
            
    if header_idx == -1:
        raise ValueError("Could not find Stark header row containing 'MPAN' as first cell.")
        
    # Read columns
    header_line = file_lines[header_idx]
    # Stark exports are CSV
    header_cols = next(csv.reader([header_line]))
    header_cols = [c.strip() for c in header_cols]
    
    # Identify time periods: format is HH:MM or HH:MM Status
    time_col_pattern = re.compile(r'^(\d{2}:\d{2})(a)?$')
    time_columns = []
    status_columns = {}
    
    for c in header_cols:
        match = time_col_pattern.match(c)
        if match:
            time_columns.append(c)
        elif c.endswith(' Status'):
            time_prefix = c.replace(' Status', '')
            status_columns[time_prefix] = c

    # Parse rows
    total_rows = 0
    success_rows = 0
    error_rows = 0
    errors = []
    
    reader = csv.reader(file_lines[header_idx + 1:])
    for idx, r in enumerate(reader):
        if not r or all(cell.strip() == '' for cell in r):
            continue
            
        total_rows += 1
        
        # Build dictionary
        raw_row_dict = {}
        for col_idx, col_name in enumerate(header_cols):
            if col_idx < len(r):
                raw_row_dict[col_name] = r[col_idx].strip()
                
        try:
            mpan = raw_row_dict.get('MPAN')
            date_str = raw_row_dict.get('Date')
            meter_serial = raw_row_dict.get('Meter Serial')
            
            if not mpan or not date_str:
                raise ValueError("Missing critical columns: MPAN or Date.")
                
            # Read MPAN as string
            mpan = str(mpan).strip()
            
            # Parse Date
            try:
                activity_date = datetime.strptime(date_str, '%d/%m/%Y').date()
            except ValueError:
                raise ValueError(f"Invalid date format '{date_str}'. Expected DD/MM/YYYY.")
                
            idempotency_key = f"utility_hh_{mpan}_{activity_date.strftime('%Y-%m-%d')}"
            
            # If already exists, we skip creating a duplicate, but count as success (idempotent)
            if EmissionRow.objects.filter(idempotency_key=idempotency_key).exists():
                success_rows += 1
                continue
                
            # Melt periods
            daily_kwh = Decimal('0.000000')
            has_estimated_periods = False
            
            for t_col in time_columns:
                val_str = raw_row_dict.get(t_col)
                if val_str:
                    try:
                        kwh_val = Decimal(val_str.replace(',', ''))
                        daily_kwh += kwh_val
                    except InvalidOperation:
                        # Non-numeric readings are treated as zeroes or skip, let's raise
                        raise ValueError(f"Invalid numeric value '{val_str}' in settlement period {t_col}.")
                        
                # Check status flag
                status_col_name = status_columns.get(t_col) or f"{t_col} Status"
                status_flag = raw_row_dict.get(status_col_name)
                if status_flag and status_flag.upper() in ('E', 'S'):
                    has_estimated_periods = True
                    
            # Look up DEFRA electricity factor for UK
            factor_used = find_latest_factor(
                source_type=EmissionFactor.SourceType.ELECTRICITY,
                category='uk',
                date=activity_date
            )
            
            normalized_kgco2e = None
            is_flagged = False
            flag_reason = None
            
            if not factor_used:
                is_flagged = True
                flag_reason = f"No emission factor found for electricity grid 'uk' on date {activity_date}."
            else:
                normalized_kgco2e = daily_kwh * factor_used.factor_value
                
            if has_estimated_periods:
                is_flagged = True
                flag_reason = "Daily total includes estimated (E) or substituted (S) half-hourly periods."
                
            # Create EmissionRow
            row = EmissionRow(
                ingestion_job=job,
                source_type=EmissionRow.SourceType.UTILITY_HH,
                source_raw=raw_row_dict,
                idempotency_key=idempotency_key,
                activity_date=activity_date,
                raw_value=daily_kwh,
                raw_unit='kWh',
                scope=EmissionRow.Scope.SCOPE2,
                emission_factor_used=factor_used,
                normalized_kgco2e=normalized_kgco2e,
                mpan=mpan,
                meter_serial=meter_serial,
                has_estimated_periods=has_estimated_periods,
                is_flagged=is_flagged,
                flag_reason=flag_reason
            )
            row.save()
            success_rows += 1
            
        except Exception as e:
            error_rows += 1
            errors.append({
                "row_number": idx + header_idx + 2,
                "error": str(e),
                "raw_row": raw_row_dict
            })
            
    # Update Job
    job.row_count_total = total_rows
    job.row_count_success = success_rows
    job.row_count_error = error_rows
    job.error_detail = errors
    if error_rows == 0:
        job.status = IngestionJob.Status.COMPLETE
    elif success_rows > 0:
        job.status = IngestionJob.Status.PARTIAL
    else:
        job.status = IngestionJob.Status.FAILED
        
    job.completed_at = timezone.now()
    job.save()


def run_navan_csv_parser(job, file_lines):
    if not file_lines:
        raise ValueError("File is empty.")

    reader = csv.reader(file_lines)
    header = None
    rows = list(reader)
    
    # Find header row
    header_idx = -1
    for i, r in enumerate(rows):
        if any(h in ''.join(r) for h in ['Booking ID', 'BookingID', 'Trip ID', 'Travel Date']):
            header = [h.strip() for h in r]
            header_idx = i
            break
            
    if header is None:
        raise ValueError("Could not find standard Navan CSV header row.")
        
    # Standardize column headers
    header_mapping = {
        'booking id': 'booking_id', 'bookingid': 'booking_id',
        'trip id': 'trip_id', 'tripid': 'trip_id',
        'employee id': 'employee_id', 'employeeid': 'employee_id',
        'traveller name': 'traveller_name', 'travel date': 'travel_date',
        'booking date': 'booking_date', 'category': 'category',
        'origin': 'origin', 'destination': 'destination',
        'cabin class': 'cabin_class', 'carrier code': 'carrier_code',
        'hotel name': 'hotel_name', 'hotel city': 'hotel_city',
        'hotel country': 'hotel_country', 'nights': 'nights',
        'ground type': 'ground_type', 'distance km': 'distance_km',
        'amount': 'amount', 'currency': 'currency',
        'policy status': 'policy_status', 'department': 'department',
        'cost centre': 'cost_centre'
    }
    
    normalized_headers = []
    for h in header:
        h_lower = h.lower().strip()
        matched = False
        for k, v in header_mapping.items():
            if k == h_lower:
                normalized_headers.append(v)
                matched = True
                break
        if not matched:
            normalized_headers.append(h_lower.replace(' ', '_'))
            
    # Process travel rows
    total_rows = 0
    success_rows = 0
    error_rows = 0
    errors = []
    
    for idx, r in enumerate(rows[header_idx + 1:]):
        if not r or all(cell.strip() == '' for cell in r):
            continue
            
        total_rows += 1
        raw_row_dict = {}
        for h_idx, col_name in enumerate(normalized_headers):
            if h_idx < len(r):
                raw_row_dict[col_name] = r[h_idx].strip()
                
        try:
            booking_id = raw_row_dict.get('booking_id')
            category = raw_row_dict.get('category')
            travel_date_str = raw_row_dict.get('travel_date')
            
            if not booking_id or not category or not travel_date_str:
                raise ValueError("Missing critical travel columns: Booking ID, Category, or Travel Date.")
                
            category_lower = category.lower().strip()
            
            # Parse Travel Date
            try:
                activity_date = datetime.strptime(travel_date_str, '%d/%m/%Y').date()
            except ValueError:
                raise ValueError(f"Invalid date format '{travel_date_str}'. Expected DD/MM/YYYY.")
                
            idempotency_key = f"travel_navan_{booking_id}"
            
            # If already exists, we skip creating a duplicate, but count as success (idempotent)
            if EmissionRow.objects.filter(idempotency_key=idempotency_key).exists():
                success_rows += 1
                continue
                
            # Initialize calculation variables
            raw_value = None
            raw_unit = None
            normalized_kgco2e = None
            factor_used = None
            inferred_distance_km = None
            is_flagged = False
            flag_reason = None
            
            # Cabin class normalisation
            cabin_class = raw_row_dict.get('cabin_class')
            cabin_class_lower = cabin_class.lower().strip() if cabin_class else 'economy'
            if cabin_class_lower not in ('economy', 'premium_economy', 'business', 'first'):
                cabin_class_lower = 'economy'
                
            # Perform calculations by travel category
            if category_lower == 'flight':
                origin = raw_row_dict.get('origin')
                destination = raw_row_dict.get('destination')
                
                if not origin or not destination:
                    is_flagged = True
                    flag_reason = "Flight origin or destination IATA is missing."
                else:
                    distance = haversine_km(origin, destination)
                    if distance is None:
                        is_flagged = True
                        flag_reason = f"Missing coordinates for IATA codes: {origin} -> {destination}."
                    else:
                        inferred_distance_km = Decimal(f"{distance:.2f}")
                        raw_value = inferred_distance_km
                        raw_unit = 'km'
                        
                        # Categorize flight based on UK airports presence
                        is_dom = origin.upper().strip() in UK_AIRPORTS and destination.upper().strip() in UK_AIRPORTS
                        if is_dom:
                            haul_type = 'domestic'
                        elif distance < 3700:
                            haul_type = 'short_haul'
                        else:
                            haul_type = 'long_haul'
                            
                        # Look up factor
                        factor_used = find_latest_factor(
                            source_type=EmissionFactor.SourceType.FLIGHT,
                            category=haul_type,
                            sub_category=cabin_class_lower,
                            date=activity_date
                        )
                        
                        if not factor_used:
                            is_flagged = True
                            flag_reason = f"No emission factor found for flight ({haul_type}, {cabin_class_lower}) on {activity_date}."
                        else:
                            normalized_kgco2e = inferred_distance_km * factor_used.factor_value
                            
            elif category_lower == 'hotel':
                nights_str = raw_row_dict.get('nights')
                country = raw_row_dict.get('hotel_country', 'GB')
                
                if not nights_str:
                    is_flagged = True
                    flag_reason = "Missing number of room nights for hotel category."
                else:
                    try:
                        nights = int(float(nights_str))
                        raw_value = Decimal(nights)
                        raw_unit = 'room_night'
                        
                        hotel_cat = 'uk' if country.upper().strip() == 'GB' else 'world'
                        
                        # Look up factor
                        factor_used = find_latest_factor(
                            source_type=EmissionFactor.SourceType.HOTEL,
                            category=hotel_cat,
                            date=activity_date
                        )
                        
                        if not factor_used:
                            is_flagged = True
                            flag_reason = f"No hotel factor found for country {country} on {activity_date}."
                        else:
                            normalized_kgco2e = raw_value * factor_used.factor_value
                    except Exception:
                        raise ValueError(f"Invalid numeric value '{nights_str}' for hotel nights.")
                        
            elif category_lower in ('ground_transport', 'car_rental', 'ground', 'rail'):
                g_type = raw_row_dict.get('ground_type', 'car')
                g_type_lower = g_type.lower().strip() if g_type else 'car'
                if g_type_lower not in ('taxi', 'train', 'bus', 'car'):
                    g_type_lower = 'car'  # Default fallback
                    
                dist_str = raw_row_dict.get('distance_km')
                if not dist_str:
                    is_flagged = True
                    flag_reason = "Missing distance_km for land travel."
                    raw_unit = 'km'
                else:
                    try:
                        distance = Decimal(dist_str.replace(',', ''))
                        raw_value = distance
                        raw_unit = 'km'
                        
                        # Look up land travel factor
                        factor_used = find_latest_factor(
                            source_type=EmissionFactor.SourceType.GROUND,
                            category=g_type_lower,
                            date=activity_date
                        )
                        
                        if not factor_used:
                            is_flagged = True
                            flag_reason = f"No land travel factor found for '{g_type_lower}' on {activity_date}."
                        else:
                            normalized_kgco2e = raw_value * factor_used.factor_value
                    except Exception:
                        raise ValueError(f"Invalid numeric value '{dist_str}' for distance.")
            else:
                is_flagged = True
                flag_reason = f"Unsupported travel category: '{category}'."
                
            # Flag in dashboard if policy status is out_of_policy
            policy_status = raw_row_dict.get('policy_status')
            if policy_status == 'out_of_policy':
                is_flagged = True
                if flag_reason:
                    flag_reason += " | Out of travel policy"
                else:
                    flag_reason = "Out of travel policy"
                    
            # Handle cast nights for database field
            db_nights = None
            if category_lower == 'hotel' and raw_value is not None:
                db_nights = int(raw_value)
                
            # Construct row
            row = EmissionRow(
                ingestion_job=job,
                source_type=EmissionRow.SourceType.TRAVEL_NAVAN,
                source_raw=raw_row_dict,
                idempotency_key=idempotency_key,
                activity_date=activity_date,
                raw_value=raw_value,
                raw_unit=raw_unit,
                scope=EmissionRow.Scope.SCOPE3,
                emission_factor_used=factor_used,
                normalized_kgco2e=normalized_kgco2e,
                travel_category=category_lower,
                origin_iata=raw_row_dict.get('origin'),
                destination_iata=raw_row_dict.get('destination'),
                cabin_class=cabin_class_lower if category_lower == 'flight' else None,
                carrier_code=raw_row_dict.get('carrier_code'),
                hotel_country=raw_row_dict.get('hotel_country'),
                nights=db_nights,
                inferred_distance_km=inferred_distance_km,
                booking_id=booking_id,
                employee_id=raw_row_dict.get('employee_id'),
                is_flagged=is_flagged,
                flag_reason=flag_reason
            )
            row.save()
            success_rows += 1
            
        except Exception as e:
            error_rows += 1
            errors.append({
                "row_number": idx + header_idx + 2,
                "error": str(e),
                "raw_row": raw_row_dict
            })
            
    # Update Job
    job.row_count_total = total_rows
    job.row_count_success = success_rows
    job.row_count_error = error_rows
    job.error_detail = errors
    if error_rows == 0:
        job.status = IngestionJob.Status.COMPLETE
    elif success_rows > 0:
        job.status = IngestionJob.Status.PARTIAL
    else:
        job.status = IngestionJob.Status.FAILED
        
    job.completed_at = timezone.now()
    job.save()
