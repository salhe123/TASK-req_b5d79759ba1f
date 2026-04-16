import csv
import io
import json
import re
import statistics
from datetime import datetime

from sqlalchemy import select, func

from app.extensions import db
from app.models.cleansing import CleansingTemplate, CleansingJob


# Place-name reference table for standardization
PLACE_NAME_REFERENCE = {
    # US cities
    'ny': 'New York',
    'nyc': 'New York',
    'new york city': 'New York',
    'los angeles': 'Los Angeles',
    'sf': 'San Francisco',
    'san fran': 'San Francisco',
    'chi': 'Chicago',
    'philly': 'Philadelphia',
    'dc': 'Washington D.C.',
    'washington dc': 'Washington D.C.',
    'vegas': 'Las Vegas',
    'lv': 'Las Vegas',
    'atl': 'Atlanta',
    'bos': 'Boston',
    'dal': 'Dallas',
    'hou': 'Houston',
    'det': 'Detroit',
    'phx': 'Phoenix',
    'sea': 'Seattle',
    'den': 'Denver',
    'mia': 'Miami',
    # US states (2-letter abbreviations)
    'al': 'Alabama',
    'ak': 'Alaska',
    'az': 'Arizona',
    'ar': 'Arkansas',
    'ca': 'California',
    'co': 'Colorado',
    'ct': 'Connecticut',
    'de': 'Delaware',
    'fl': 'Florida',
    'ga': 'Georgia',
    'hi': 'Hawaii',
    'id': 'Idaho',
    'il': 'Illinois',
    'in': 'Indiana',
    'ia': 'Iowa',
    'ks': 'Kansas',
    'ky': 'Kentucky',
    'la': 'Louisiana',
    'me': 'Maine',
    'md': 'Maryland',
    'ma': 'Massachusetts',
    'mi': 'Michigan',
    'mn': 'Minnesota',
    'ms': 'Mississippi',
    'mo': 'Missouri',
    'mt': 'Montana',
    'ne': 'Nebraska',
    'nv': 'Nevada',
    'nh': 'New Hampshire',
    'nj': 'New Jersey',
    'nm': 'New Mexico',
    'nc': 'North Carolina',
    'nd': 'North Dakota',
    'oh': 'Ohio',
    'ok': 'Oklahoma',
    'or': 'Oregon',
    'pa': 'Pennsylvania',
    'ri': 'Rhode Island',
    'sc': 'South Carolina',
    'sd': 'South Dakota',
    'tn': 'Tennessee',
    'tx': 'Texas',
    'ut': 'Utah',
    'vt': 'Vermont',
    'va': 'Virginia',
    'wa': 'Washington',
    'wv': 'West Virginia',
    'wi': 'Wisconsin',
    'wy': 'Wyoming',
}

# Common date format patterns for datetime normalization
DATE_FORMATS = [
    '%Y-%m-%d',
    '%m/%d/%Y',
    '%m-%d-%Y',
    '%d/%m/%Y',
    '%d-%m-%Y',
    '%Y/%m/%d',
    '%m/%d/%y',
    '%d %b %Y',
    '%d %B %Y',
    '%b %d, %Y',
    '%B %d, %Y',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d %H:%M:%S',
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%Y %I:%M %p',
]

# Unit conversion factors to USD (approximate)
CURRENCY_TO_USD = {
    'usd': 1.0, '$': 1.0,
    'eur': 1.10, 'gbp': 1.27, 'cad': 0.74, 'aud': 0.65,
    'jpy': 0.0067, 'cny': 0.14, 'inr': 0.012, 'mxn': 0.058,
}

# Unit conversion to imperial
METRIC_TO_IMPERIAL = {
    'km': ('miles', 0.621371),
    'kilometers': ('miles', 0.621371),
    'm': ('feet', 3.28084),
    'meters': ('feet', 3.28084),
    'cm': ('inches', 0.393701),
    'centimeters': ('inches', 0.393701),
    'kg': ('lbs', 2.20462),
    'kilograms': ('lbs', 2.20462),
    'g': ('oz', 0.035274),
    'grams': ('oz', 0.035274),
    'l': ('gal', 0.264172),
    'liters': ('gal', 0.264172),
    'c': ('f', None),  # special: Celsius to Fahrenheit
    'celsius': ('f', None),
}


class CleansingService:

    # --- Template CRUD with versioning ---

    @staticmethod
    def create_template(data, created_by=None):
        name = data['name'].strip()
        latest = db.session.execute(
            select(func.max(CleansingTemplate.version))
            .where(CleansingTemplate.name == name)
        ).scalar()

        version = (latest or 0) + 1

        template = CleansingTemplate(
            name=name,
            description=data.get('description', '').strip() or None,
            version=version,
            field_mapping=json.dumps(data.get('field_mapping', {})),
            missing_value_rules=json.dumps(data.get('missing_value_rules', {})),
            dedup_fields=json.dumps(data.get('dedup_fields', [])),
            dedup_threshold=float(data.get('dedup_threshold', 1.0)),
            format_rules=json.dumps(data.get('format_rules', {})),
            created_by=created_by,
        )
        db.session.add(template)
        db.session.commit()
        CleansingService._audit('create_template', 'cleansing_template', template.id,
                                created_by, f'{template.name} v{template.version}')
        return template, None

    @staticmethod
    def update_template(template_id, data):
        """Update creates a new version of the template.
        Deactivation + creation are wrapped in a single transaction for atomicity."""
        old = db.session.get(CleansingTemplate, template_id)
        if not old:
            return None, 'Template not found.'

        old.is_active = False
        # Do NOT commit yet — let create_template commit both in one transaction

        return CleansingService.create_template({
            'name': old.name,
            'description': data.get('description', old.description),
            'field_mapping': data.get('field_mapping', json.loads(old.field_mapping or '{}')),
            'missing_value_rules': data.get('missing_value_rules', json.loads(old.missing_value_rules or '{}')),
            'dedup_fields': data.get('dedup_fields', json.loads(old.dedup_fields or '[]')),
            'dedup_threshold': data.get('dedup_threshold', old.dedup_threshold),
            'format_rules': data.get('format_rules', json.loads(old.format_rules or '{}')),
        }, created_by=old.created_by)

    @staticmethod
    def get_template(template_id):
        return db.session.get(CleansingTemplate, template_id)

    @staticmethod
    def list_templates(active_only=True):
        q = select(CleansingTemplate)
        if active_only:
            q = q.where(CleansingTemplate.is_active == True)  # noqa: E712
        return db.session.execute(
            q.order_by(CleansingTemplate.name, CleansingTemplate.version.desc())
        ).scalars().all()

    @staticmethod
    def get_template_versions(name):
        return db.session.execute(
            select(CleansingTemplate)
            .where(CleansingTemplate.name == name)
            .order_by(CleansingTemplate.version.desc())
        ).scalars().all()

    @staticmethod
    def delete_template(template_id, user_id=None):
        t = db.session.get(CleansingTemplate, template_id)
        if not t:
            return False, 'Template not found.'
        t.is_active = False
        db.session.commit()
        CleansingService._audit('delete_template', 'cleansing_template', template_id,
                                user_id, f'{t.name} v{t.version}')
        return True, None

    # --- Job execution ---

    @staticmethod
    def create_job(template_id, csv_content, filename, created_by=None):
        """Create a cleansing job from CSV content."""
        template = db.session.get(CleansingTemplate, template_id)
        if not template:
            return None, 'Template not found.'

        # Encrypt raw data at rest — fail closed in production
        encrypted_data = csv_content
        try:
            from app.services.encryption_service import EncryptionService
            encrypted_data = EncryptionService.encrypt(csv_content)
        except Exception as e:
            from flask import current_app
            if current_app.config.get('SQLCIPHER_ENABLED', False):
                return None, f'Encryption failed — cannot store sensitive data unencrypted: {e}'
            import logging
            logging.getLogger(__name__).warning('Field encryption unavailable: %s', e)

        job = CleansingJob(
            template_id=template_id,
            filename=filename,
            status='pending',
            raw_data=encrypted_data,
            created_by=created_by,
        )
        db.session.add(job)
        db.session.commit()
        return job, None

    @staticmethod
    def execute_job(job_id):
        """Execute a cleansing job pipeline."""
        job = db.session.get(CleansingJob, job_id)
        if not job:
            return None, 'Job not found.'

        if job.status not in ('pending', 'failed'):
            return None, f'Job is already {job.status}.'

        job.status = 'processing'
        job.started_at = datetime.utcnow()
        db.session.commit()

        try:
            template = job.template
            field_mapping = json.loads(template.field_mapping or '{}')
            missing_rules = json.loads(template.missing_value_rules or '{}')
            dedup_fields = json.loads(template.dedup_fields or '[]')
            dedup_threshold = template.dedup_threshold
            format_rules = json.loads(template.format_rules or '{}')

            # Decrypt raw data if encrypted
            raw_data = job.raw_data
            try:
                from app.services.encryption_service import EncryptionService
                if EncryptionService.is_encrypted(raw_data):
                    raw_data = EncryptionService.decrypt(raw_data)
            except Exception:
                pass

            # Parse CSV
            rows = CleansingService._parse_csv(raw_data)
            job.total_rows = len(rows)

            if not rows:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.results = json.dumps([])
                db.session.commit()
                return job, None

            # Step 1: Apply field mapping
            mapped = CleansingService._apply_field_mapping(rows, field_mapping)

            # Step 2: Apply format standardization (includes new normalizations)
            formatted = CleansingService._apply_format_rules(mapped, format_rules)

            # Step 3: Apply missing value rules
            clean, flagged = CleansingService._apply_missing_rules(formatted, missing_rules)

            # Step 4: Outlier detection
            clean, outlier_flagged = CleansingService._detect_outliers(clean)
            flagged.extend(outlier_flagged)

            # Step 5: Deduplication
            deduped, duplicates = CleansingService._deduplicate(clean, dedup_fields, dedup_threshold)

            job.processed_rows = len(rows)
            job.clean_rows = len(deduped)
            job.flagged_rows = len(flagged)
            job.duplicate_rows = len(duplicates)
            job.skipped_rows = len(rows) - len(deduped) - len(flagged)

            # Encrypt processed outputs at rest — fail closed in production
            results_json = json.dumps(deduped)
            flagged_json = json.dumps(flagged)
            try:
                from app.services.encryption_service import EncryptionService
                results_json = EncryptionService.encrypt(results_json)
                flagged_json = EncryptionService.encrypt(flagged_json)
            except Exception as enc_err:
                from flask import current_app
                if current_app.config.get('SQLCIPHER_ENABLED', False):
                    raise RuntimeError(
                        f'Encryption failed — refusing to store results unencrypted: {enc_err}'
                    ) from enc_err
                import logging
                logging.getLogger(__name__).warning('Field encryption unavailable for results: %s', enc_err)

            job.results = results_json
            job.flagged_data = flagged_json
            job.status = 'completed'
            job.completed_at = datetime.utcnow()

        except Exception as e:
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()

        db.session.commit()
        return job, None

    @staticmethod
    def get_job(job_id):
        return db.session.get(CleansingJob, job_id)

    @staticmethod
    def get_job_results(job):
        """Return decrypted (results, flagged_data) as Python lists."""
        results_raw = job.results or ''
        flagged_raw = job.flagged_data or ''
        try:
            from app.services.encryption_service import EncryptionService
            if results_raw and EncryptionService.is_encrypted(results_raw):
                results_raw = EncryptionService.decrypt(results_raw)
            if flagged_raw and EncryptionService.is_encrypted(flagged_raw):
                flagged_raw = EncryptionService.decrypt(flagged_raw)
        except Exception:
            pass
        clean = json.loads(results_raw) if results_raw else []
        flagged = json.loads(flagged_raw) if flagged_raw else []
        return clean, flagged

    @staticmethod
    def list_jobs(limit=50):
        return db.session.execute(
            select(CleansingJob)
            .order_by(CleansingJob.created_at.desc())
            .limit(limit)
        ).scalars().all()

    # --- Pipeline steps ---

    @staticmethod
    def _parse_csv(csv_content):
        """Parse CSV string into list of dicts."""
        reader = csv.DictReader(io.StringIO(csv_content))
        return [dict(row) for row in reader]

    @staticmethod
    def _apply_field_mapping(rows, mapping):
        """Rename CSV columns to target field names."""
        if not mapping:
            return rows

        result = []
        for row in rows:
            mapped_row = {}
            for csv_col, target_field in mapping.items():
                if csv_col in row:
                    mapped_row[target_field] = row[csv_col]
            for k, v in row.items():
                if k not in mapping:
                    mapped_row[k] = v
            result.append(mapped_row)
        return result

    @staticmethod
    def _apply_format_rules(rows, rules):
        """Apply format standardization to fields including new normalizations."""
        if not rules:
            return rows

        formatters = {
            'lowercase': lambda v: v.lower() if v else v,
            'uppercase': lambda v: v.upper() if v else v,
            'titlecase': lambda v: v.title() if v else v,
            'strip': lambda v: v.strip() if v else v,
            'digits_only': lambda v: re.sub(r'[^\d]', '', v) if v else v,
            'email_normalize': lambda v: v.strip().lower() if v else v,
            'phone_format': lambda v: re.sub(r'[^\d+]', '', v) if v else v,
            'date_normalize': CleansingService._normalize_datetime,
            'datetime_normalize': CleansingService._normalize_datetime,
            'usd_normalize': CleansingService._normalize_currency_to_usd,
            'currency_normalize': CleansingService._normalize_currency_to_usd,
            'imperial_normalize': CleansingService._normalize_to_imperial,
            'unit_normalize': CleansingService._normalize_to_imperial,
            'place_name': CleansingService._normalize_place_name,
            'place_normalize': CleansingService._normalize_place_name,
            'city_normalize': CleansingService._normalize_place_name,
            'state_normalize': CleansingService._normalize_place_name,
        }

        result = []
        for row in rows:
            new_row = dict(row)
            for field, rule in rules.items():
                if field in new_row and new_row[field]:
                    formatter = formatters.get(rule)
                    if formatter:
                        new_row[field] = formatter(new_row[field])
            result.append(new_row)
        return result

    @staticmethod
    def _normalize_datetime(value):
        """Normalize date/datetime strings to MM/DD/YYYY 12-hour format."""
        if not value or not value.strip():
            return value
        value = value.strip()
        for fmt in DATE_FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime('%m/%d/%Y %I:%M %p')
            except ValueError:
                continue
        return value

    @staticmethod
    def _normalize_currency_to_usd(value):
        """Normalize currency values to USD."""
        if not value or not value.strip():
            return value
        value = value.strip()

        # Try to extract currency code and amount
        match = re.match(
            r'^([A-Za-z$]{1,3})?\s*([0-9,]+\.?\d*)\s*([A-Za-z]{2,3})?$',
            value,
        )
        if not match:
            return value

        prefix = (match.group(1) or '').lower().strip()
        amount_str = match.group(2).replace(',', '')
        suffix = (match.group(3) or '').lower().strip()

        try:
            amount = float(amount_str)
        except ValueError:
            return value

        currency = prefix or suffix or 'usd'
        rate = CURRENCY_TO_USD.get(currency, None)
        if rate is None:
            return value

        usd_amount = amount * rate
        return f'${usd_amount:,.2f}'

    @staticmethod
    def _normalize_to_imperial(value):
        """Normalize metric units to imperial."""
        if not value or not value.strip():
            return value
        value = value.strip()

        match = re.match(r'^([0-9,]+\.?\d*)\s*([A-Za-z]+)$', value)
        if not match:
            return value

        amount_str = match.group(1).replace(',', '')
        unit = match.group(2).lower().strip()

        try:
            amount = float(amount_str)
        except ValueError:
            return value

        conversion = METRIC_TO_IMPERIAL.get(unit)
        if not conversion:
            return value

        target_unit, factor = conversion
        if unit in ('c', 'celsius'):
            converted = amount * 9 / 5 + 32
            return f'{converted:.1f} {target_unit}'

        converted = amount * factor
        return f'{converted:.2f} {target_unit}'

    @staticmethod
    def _normalize_place_name(value):
        """Normalize place names using reference table."""
        if not value or not value.strip():
            return value
        lookup = value.strip().lower()
        standard = PLACE_NAME_REFERENCE.get(lookup)
        if standard:
            return standard
        return value.strip().title()

    @staticmethod
    def _detect_outliers(rows):
        """Detect numeric outliers using IQR method. Flag rows with outlier values."""
        if not rows:
            return rows, []

        # Find numeric fields
        numeric_fields = {}
        for row in rows:
            for field, value in row.items():
                if field.startswith('_'):
                    continue
                if field not in numeric_fields:
                    numeric_fields[field] = []
                try:
                    numeric_fields[field].append(float(str(value).replace(',', '')))
                except (ValueError, TypeError):
                    pass

        # Calculate IQR bounds for fields with enough data
        bounds = {}
        for field, values in numeric_fields.items():
            if len(values) < 4:
                continue
            # Only process if majority of values in field are numeric
            if len(values) < len(rows) * 0.5:
                continue
            sorted_vals = sorted(values)
            q1_idx = len(sorted_vals) // 4
            q3_idx = (3 * len(sorted_vals)) // 4
            q1 = sorted_vals[q1_idx]
            q3 = sorted_vals[q3_idx]
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            bounds[field] = (lower, upper)

        if not bounds:
            return rows, []

        clean = []
        flagged = []
        for row in rows:
            outlier_fields = []
            for field, (lower, upper) in bounds.items():
                val_str = row.get(field, '')
                try:
                    val = float(str(val_str).replace(',', ''))
                    if val < lower or val > upper:
                        outlier_fields.append(f'{field}={val_str}')
                except (ValueError, TypeError):
                    pass

            if outlier_fields:
                new_row = dict(row)
                new_row['_flag_reason'] = f'Outlier detected: {", ".join(outlier_fields)}'
                flagged.append(new_row)
            else:
                clean.append(row)

        return clean, flagged

    @staticmethod
    def _apply_missing_rules(rows, rules):
        """Handle missing values. Returns (clean_rows, flagged_rows)."""
        if not rules:
            return rows, []

        clean = []
        flagged = []

        for row in rows:
            is_flagged = False
            new_row = dict(row)

            for field, rule_config in rules.items():
                value = new_row.get(field, '').strip() if new_row.get(field) else ''

                if not value:
                    action = rule_config.get('action', 'skip')

                    if action == 'default':
                        new_row[field] = rule_config.get('value', '')
                    elif action == 'skip':
                        is_flagged = True
                        new_row['_flag_reason'] = f'Missing required field: {field}'
                        break
                    elif action == 'flag':
                        is_flagged = True
                        new_row['_flag_reason'] = f'Missing field needs review: {field}'

            if is_flagged:
                flagged.append(new_row)
            else:
                clean.append(new_row)

        return clean, flagged

    @staticmethod
    def _deduplicate(rows, dedup_fields, threshold=1.0):
        """Remove duplicate rows based on specified fields.
        threshold=1.0 means exact match only."""
        if not dedup_fields or not rows:
            return rows, []

        seen = {}
        unique = []
        duplicates = []

        for row in rows:
            key_parts = []
            for field in dedup_fields:
                val = str(row.get(field, '')).strip().lower()
                key_parts.append(val)
            key = '|'.join(key_parts)

            if not key or key == '|' * (len(dedup_fields) - 1):
                unique.append(row)
                continue

            if threshold >= 1.0:
                if key in seen:
                    row['_dup_of'] = seen[key]
                    duplicates.append(row)
                else:
                    seen[key] = len(unique)
                    unique.append(row)
            else:
                is_dup = False
                for existing_key in seen:
                    similarity = CleansingService._similarity(key, existing_key)
                    if similarity >= threshold:
                        row['_dup_of'] = seen[existing_key]
                        duplicates.append(row)
                        is_dup = True
                        break
                if not is_dup:
                    seen[key] = len(unique)
                    unique.append(row)

        return unique, duplicates

    @staticmethod
    def _similarity(s1, s2):
        """Simple character-level similarity ratio."""
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0

        def bigrams(s):
            return set(s[i:i+2] for i in range(len(s) - 1))

        b1 = bigrams(s1)
        b2 = bigrams(s2)

        if not b1 or not b2:
            return 0.0

        intersection = len(b1 & b2)
        union = len(b1 | b2)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _audit(action, entity_type, entity_id, user_id=None, details=None):
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action=action, category='system', entity_type=entity_type,
                entity_id=entity_id, user_id=user_id, details=details,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Audit log failed for cleansing %s', action)
