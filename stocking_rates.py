"""Preliminary minutes/carton estimates from six historical reports.
None means insufficient evidence; never silently replace unknown work with zero.
"""
import re
import pandas as pd

# (substring of normalized custom block, case minutes, repack minutes)
RATES = [
('BABY ESSENTIALS',1.00,6.39),('DIAPERS',.99,8.05),('BABY FOOD',1.31,None),
('COSMETICS',1.51,6.68),('PROTEIN',1.20,None),('OTC',1.13,5.65),
('HAIR CARE',1.13,6.86),('WOMENS HBA',1.58,7.02),('MENS',1.32,6.42),
('KITCHEN',1.14,4.92),('STATIONERY',1.26,7.03),
('DECORATIVE STORAGE',1.14,None),('CLOSET STORAGE',1.14,1.50),
('LAMPS',1.11,None),('CANDLES',1.33,None),('SMALL APPLIANCES',.91,None),
('KIDS BEDDING',.90,3.15),('BEDDING',1.06,1.94),('PILLOWS',1.45,1.24),
('FURNITURE',1.35,None),('BULK PLASTICS',1.23,None),('BATH',1.11,2.23),
('AIR FRESHENERS',1.10,None),('HOUSEHOLD CLEANING',1.18,None),
('FLOOR',1.08,None),('TOILET PAPER',1.08,None),('PAPER TOWELS',1.15,None),
('BLEACH',1.08,None),('LAUNDRY',.99,None),('TRASH BAGS',1.57,None),
('PLATES',1.37,None),('LITTER',.84,5.16),('DOG FOOD',.99,4.12),('CAT FOOD',1.00,1.03),
('ETHNIC',1.34,None),('PBJ',1.36,None),('PASTA',1.34,None),
('BREAKFAST',1.26,None),('BAKING',1.29,None),('CANDY',1.34,None),
('CHIPS',1.28,None),('NUTS',1.37,None),('SPARKLING WATER',.99,None),('JUICE',1.26,None),
('MINI SEASONAL',1.55,None),('GIFT WRAPPING',1.50,None),
('SPORTS 2',1.03,2.76),('LUGGAGE',.62,3.14),('SPORTS',1.75,1.59),
('PRESCHOOL',1.11,None),('GIRL TOYS',1.25,None),('LEGOS',.90,.60),
('BOY TOYS',1.09,None),('KIDS BOARD GAMES',1.02,4.86),
('TECH',1.63,14.03),('ENTERTAINMENT',1.63,14.03),('CHECKLANES',2.83,10.11),
]

def normalize(value):
    s = str(value).upper().replace('’', "'")
    s = re.sub(r"[^A-Z0-9]+", ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def estimate(row):
    """Returns (hours or NaN, status). Does not invent missing repack rates."""
    name = normalize(row.get('CUSTOM BLOCK', ''))
    cases = pd.to_numeric(row.get('FULL CASE CARTONS', 0), errors='coerce')
    repacks = pd.to_numeric(row.get('REPACK CARTONS', 0), errors='coerce')
    if pd.isna(cases) or pd.isna(repacks) or cases < 0 or repacks < 0:
        return float('nan'), 'Invalid quantity'
    for key, cm, rm in RATES:
        if normalize(key) in name:
            if repacks > 0 and rm is None:
                return float('nan'), 'Missing repack rate'
            return (cases*cm + repacks*(rm or 0))/60, 'Estimated'
    return float('nan'), 'Unmapped rate'

def fill_missing_stocking_times(df):
    """Estimate freight rows on all-zero reports; preserve supplied positive times.

    On mixed reports, only blank times are estimated; explicit zeros are retained.
    Each uploaded file is processed separately, before combining trailer data.
    """
    df = df.copy()
    col = 'STOCKING TIME (HRS)'
    if col not in df.columns:
        df[col] = float('nan')
    df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
    for quantity_col in ('FULL CASE CARTONS', 'REPACK CARTONS'):
        if quantity_col not in df.columns:
            df[quantity_col] = 0
    cases = pd.to_numeric(df['FULL CASE CARTONS'], errors='coerce').fillna(0)
    repacks = pd.to_numeric(df['REPACK CARTONS'], errors='coerce').fillna(0)
    has_freight = cases.gt(0) | repacks.gt(0)
    # Report-level detection: no positive time anywhere among freight rows.
    no_target_times = not df.loc[has_freight, col].gt(0).any()
    needs_estimate = has_freight & (df[col].isna() | (no_target_times & df[col].eq(0)))
    df['Stocking Time Source'] = 'Target'
    df['Stocking Time Issue'] = ''
    from department_fallback import estimate_with_fallback
    for idx in df.index[needs_estimate]:
        val, status = estimate_with_fallback(df.loc[idx])
        df.at[idx, col] = val
        df.at[idx, 'Stocking Time Source'] = status
        if status not in ('Custom-block estimate', 'No freight') and not status.startswith('Department average fallback:'):
            df.at[idx, 'Stocking Time Issue'] = status
    return df
