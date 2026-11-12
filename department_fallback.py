"""Stocking estimates by the same departments used in app.py.

Fallback rates are provisional, unweighted means of available historical block rates.
If a department has no observed repack rate (Style, Seasonal, Food, Chem/Paper),
use the cross-department median as a *clearly labeled proxy*, not a Target standard.
"""
from statistics import mean, median
from stocking_rates import RATES, normalize

DEPARTMENT_KEYS = {
 'Infants': ['BABY ESSENTIALS','DIAPERS','BABY FOOD'],
 'HBA': ['COSMETICS','HAIR CARE','WOMENS HBA','MENS'],
 'OTC': ['PROTEIN','OTC'],
 'Kitchen': ['KITCHEN'], 'Stationery': ['STATIONERY'],
 'C-D': ['DECORATIVE STORAGE','CLOSET STORAGE','LAMPS','CANDLES','SMALL APPLIANCES','KIDS BEDDING','BEDDING','PILLOWS','FURNITURE','BULK PLASTICS','BATH'],
 'Chemical-Paper': ['AIR FRESHENERS','HOUSEHOLD CLEANING','FLOOR','TOILET PAPER','PAPER TOWELS','BLEACH','LAUNDRY','TRASH BAGS','PLATES'],
 'Pets': ['LITTER','DOG FOOD','CAT FOOD'],
 'Food': ['ETHNIC','PBJ','PASTA','BREAKFAST','BAKING','CANDY','CHIPS','NUTS','SPARKLING WATER','JUICE'],
 'Seasonal': ['MINI SEASONAL','GIFT WRAPPING'],
 'Sports': ['SPORTS 2','LUGGAGE','SPORTS'],
 'Toys': ['PRESCHOOL','GIRL TOYS','LEGOS','BOY TOYS','KIDS BOARD GAMES'],
 'Tech': ['TECH','ENTERTAINMENT'],
 'BPG-CL-FA': ['CHECKLANES'],
 'Style': [],
}
KEY_TO_DEPT = {normalize(k): dept for dept, keys in DEPARTMENT_KEYS.items() for k in keys}

def find_rate(name):
    name = normalize(name)
    for key, cm, rm in RATES:
        if normalize(key) in name:
            return normalize(key), cm, rm
    return None, None, None

def department_average(dept, kind):
    idx = 1 if kind == 'case' else 2
    rates = [rate[idx] for rate in RATES if KEY_TO_DEPT.get(normalize(rate[0])) == dept and rate[idx] is not None]
    return mean(rates) if rates else None

def overall_proxy(kind):
    idx = 1 if kind == 'case' else 2
    values = [rate[idx] for rate in RATES if rate[idx] is not None]
    return median(values) if values else None

def estimate_with_fallback(row):
    import pandas as pd
    name = row.get('CUSTOM BLOCK', '')
    cases = pd.to_numeric(row.get('FULL CASE CARTONS', 0), errors='coerce')
    repacks = pd.to_numeric(row.get('REPACK CARTONS', 0), errors='coerce')
    if pd.isna(cases) or pd.isna(repacks) or cases < 0 or repacks < 0:
        return float('nan'), 'Invalid quantity'
    if cases == 0 and repacks == 0:
        return 0.0, 'No freight'
    key, cm, rm = find_rate(name)
    dept = row.get('Section')
    if not isinstance(dept, str) or dept not in DEPARTMENT_KEYS:
        return float('nan'), 'Unknown department; review mapping'
    sources = []
    for kind, count, rate in [('case', cases, cm), ('repack', repacks, rm)]:
        if count <= 0 or rate is not None:
            continue
        avg = department_average(dept, kind)
        if avg is not None:
            sources.append('Department average fallback: ' + kind)
            if kind == 'case': cm = avg
            else: rm = avg
        else:
            proxy = overall_proxy(kind)
            if proxy is None:
                return float('nan'), 'No rate available for ' + kind
            sources.append('Provisional storewide median proxy: ' + kind)
            if kind == 'case': cm = proxy
            else: rm = proxy
    hours = (cases * (cm or 0) + repacks * (rm or 0)) / 60
    return hours, '; '.join(sources) if sources else 'Custom-block estimate'
