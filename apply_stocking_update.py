"""Run in the repository root: python apply_stocking_update.py"""
from pathlib import Path
p = Path('app.py')
s = p.read_text(encoding='utf-8')
if 'from stocking_rates import fill_missing_stocking_times' not in s:
    s = s.replace('app = Flask(__name__)', 'from stocking_rates import fill_missing_stocking_times\n\napp = Flask(__name__)', 1)
# Calculate at upload, before aggregation; no destructive fillna(0) for stocking time.
needle = '            # Combine the file data into the main DataFrame'
assert needle in s, 'Cannot locate upload processing block; repository may have changed.'
s = s.replace(needle, '            temp_df = fill_missing_stocking_times(temp_df)\n\n' + needle, 1)
# Both routes aggregate times. Missing estimates stay NaN, with min_count=1.
old = "        all_data[col] = pd.to_numeric(all_data[col], errors='coerce').fillna(0)"
assert s.count(old) == 2, 'Expected two aggregation loops; review app.py manually.'
s = s.replace(old, "        all_data[col] = pd.to_numeric(all_data[col], errors='coerce')\n        if col != 'STOCKING TIME (HRS)':\n            all_data[col] = all_data[col].fillna(0)")
old2 = "summary = all_data.groupby('Section')[numeric_columns].sum()"
assert s.count(old2) == 2
s = s.replace(old2, "summary = all_data.groupby('Section')[numeric_columns].sum(min_count=1)")
# Prevent a total from silently hiding unestimated freight.
old3 = 'total_row = summary.sum(numeric_only=True).rename("Total")'
assert s.count(old3) == 2
s = s.replace(old3, 'total_row = summary.sum(numeric_only=True, min_count=1).rename("Total")')
p.write_text(s, encoding='utf-8')
print('Updated app.py. Review unknown-rate warnings in Stocking Time Issue column.')
