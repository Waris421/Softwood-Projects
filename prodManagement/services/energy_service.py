import pandas as pd
from prodManagement import models


def normalize_machine_name(raw_name: str) -> str:
    import re
    name = raw_name.strip()
    name = re.sub(r'#\s*(\d+)', lambda m: f'#{int(m.group(1)):02d}', name)
    name = re.sub(r'\(kw\)', '(kW)', name.title(), flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def ProcessEnergyUpload(uploaded_file) -> tuple[bool, str]:
    # Step 1 — Read directly from memory into pandas — no disk involved
    df = pd.read_excel(uploaded_file)

    # Step 2 — Rename first column to Timestamp, parse into proper datetime
    df = df.rename(columns={df.columns[0]: 'Timestamp'})
    total_before = len(df)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%a %d/%m/%y %H:%M", errors='coerce')
    dropped = df['Timestamp'].isna().sum()
    df = df.dropna(subset=['Timestamp'])
    print(f"Rows before: {total_before}, dropped: {dropped}, kept: {len(df)}")

    # Step 3 — Check if data for this exact day already exists
    upload_date = df['Timestamp'].dt.date.min()
    duplicate_day = models.EnergyReading.objects.filter(Timestamp__date=upload_date).exists()

    # Step 4 — Melt: convert wide format (many columns) to long format (one row per machine per minute)
    machine_cols = df.columns[1:].tolist()
    df = df.melt(id_vars=['Timestamp'], value_vars=machine_cols, var_name='MachineName', value_name='Value_kW')
    df['Value_kW'] = df['Value_kW'].fillna(0)

    # Step 5 — Collect machine names from the file
    machine_names = df['MachineName'].unique()

    # Step 6 — Get or create a Machine record for every machine in the file
    machine_lookup = {}
    for name in machine_names:
        machine_obj, _ = models.Machine.objects.get_or_create(
            MachineId=name,
            defaults={
                'DisplayName': normalize_machine_name(name),
                'Type': 'Unknown',
                'FunctionStatus': 'Active',
            }
        )
        machine_lookup[name] = machine_obj

    # Step 7 — Fetch ALL existing timestamp+machine combos in ONE query to check duplicates
    existing = set(
        (name, ts.astimezone().replace(tzinfo=None))
        for name, ts in models.EnergyReading.objects
        .filter(Machine__in=machine_names)
        .values_list('Machine__MachineId', 'Timestamp')
    )

    # Step 8 — Filter duplicates and bulk save all new readings
    readings = []
    for row in df.itertuples(index=False):
        key = (row.MachineName, row.Timestamp.to_pydatetime().replace(tzinfo=None))
        if key not in existing:
            readings.append(models.EnergyReading(
                Machine=machine_lookup[row.MachineName],
                Timestamp=row.Timestamp,
                Value_kW=row.Value_kW
            ))

    models.EnergyReading.objects.bulk_create(readings, ignore_conflicts=True)

    # Step 9 — Return duplicate flag and date string so the view can build the right response
    return duplicate_day, upload_date.strftime("%d %B %Y")

def GetEnergyDateRange() -> dict | None:
    from django.db.models import Min, Max

    # Ask the database for the earliest and latest timestamp in one query
    result = models.EnergyReading.objects.aggregate(
        min_date=Min('Timestamp'),
        max_date=Max('Timestamp')
    )

    # Return None if no data exists at all
    if not result['min_date']:
        return None

    return {
        'min_date': result['min_date'].date().isoformat(),
        'max_date': result['max_date'].date().isoformat()
    }


def GetEnergyReadings(from_date: str, to_date: str) -> list:
    from datetime import datetime

    # Convert date strings into datetime objects the database understands
    from_dt = datetime.strptime(from_date, '%Y-%m-%d')
    to_dt = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

    # Fetch all readings in the date range ordered by machine then time
    all_readings = (
        models.EnergyReading.objects
        .filter(Timestamp__range=(from_dt, to_dt))
        .values('Machine__DisplayName', 'Timestamp', 'Value_kW')
        .order_by('Machine__DisplayName', 'Timestamp')
    )

    # Group readings by machine display name
    grouped = {}
    for r in all_readings:
        name = r['Machine__DisplayName']
        if name not in grouped:
            grouped[name] = []
        grouped[name].append({'timestamp': r['Timestamp'].isoformat(), 'value_kw': r['Value_kW']})

    return [{'machine': name, 'readings': readings} for name, readings in grouped.items()]
