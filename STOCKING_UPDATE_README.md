# Stocking time update — department fallback

Copy `stocking_rates.py`, `department_fallback.py`, and `apply_stocking_update.py` into the root of your cloned repository. If you have **already applied** the earlier patch, do **not** run `apply_stocking_update.py` again; just replace/add the two rate modules. Otherwise run `python apply_stocking_update.py` once, then test locally before committing.

The update retains Target-provided stocking times, including zero. For missing times it uses known custom-block case and repack rates, then substitutes the **simple mean** of known custom-block rates within the same department for a missing rate. It never silently uses zero for missing rates when there is freight. Rates are provisional and may not match Target standards.

**Important:** A weighted department average cannot be calculated correctly from the previously fitted rates alone. We need reliable observed repack counts or per-block fitted weights to produce weighted averages. The present fallback is an **unweighted mean**. Known custom blocks are mapped explicitly to departments; unknown block names are flagged for review rather than assigned by an ambiguous substring. Some areas have no usable repack rates, and their times remain unresolved.

The original patch does not surface unresolved workload prominently in the summary and could undercount total time if unknown rows exist. Inspect the detailed data and do not use totals for staffing until all relevant rows have estimates. Run the app locally and check an older report with known Target hours and a newer report with missing hours. No changes have been pushed to GitHub or Render.
