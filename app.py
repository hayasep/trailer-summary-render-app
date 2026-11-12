import matplotlib

matplotlib.use('Agg')  # Use non-GUI backend for rendering*

from flask import Flask, render_template, render_template_string, request, redirect, url_for, send_file

import pandas as pd

import re

import io

import matplotlib.pyplot as plt

import os

from flask import Response



from stocking_rates import fill_missing_stocking_times



app = Flask(__name__)



# Global variables to store data*

all_data = pd.DataFrame()

summary = None

trailer_names = []

uploaded_files_info = []  # List to store file name and trailer name pairs*



# Automated mappings with updated section names*

automated_mapping = {

    'Pets': ['PETS', 'DOG', 'CAT', 'LITTER'],

    'Toys': ['TOY', 'LEGOS', 'BOYS ACTION', 'E42', 'Preschool', 'Boys Girls', 'Dolls Collectables', 'RC and Cars', 'Nerf'],

    'Chemical-Paper': ['CHEMICAL', 'PAPER', 'BLEACH', 'LAUNDRY', 'HOUSEHOLD', 'AIR FRESHENER', 'DISH SOAP', 'Plates', 'TRASH BAGS'],

    'HBA': ['HBA', 'BEAUTY', 'HEALTH', 'COSMETICS', 'HAIR', 'ORAL', 'FEMININE', 'Pads', 'Shampoo', 'Travel', 's Care', 'Mouthwash','Face Wash', 'Skin Care', 'Vitamins', 'Tampons', 'Shave', 'Toothpaste', 'First Aid', 'MENS'],

    'Infants': ['INFANT', 'BABY', 'NURSING', 'DIAPERS', 'BABY MONITORS', 'BABY MISC', 'BABY FOOD', ],

    'C-D': ['C/D', 'BED', 'BATH', 'RUGS', 'LAMP', 'KITCHEN PLUG', 'APPLIANCE', 'PILLOWS D12', 'FURNITURE', 'STORAGE', 'PLASTIC', 'VACUUM', 'VIGNETTE', 'HEARTH', 'MIRRORS/WALL DECOR', 'HOME DECOR'],

    'Kitchen': ['KITCHEN'],

    'Stationery': ['STATIONERY', 'OFFICE', 'STATIONARY'],

    'BPG-CL-FA': ['BPG', 'CL/FA', 'BULLSEYE','CHECKLANES'],

    'Sports': ['SPORTS', 'OUTDOORS', 'SPORT', 'LUGG', 'AUTO'],

    'Seasonal': ['SEASONAL', 'HOLIDAY', 'GRILLING', 'SOIL', 'SEED', 'LAWN', 'G43', 'Gift Wrap', 'Decor', 'Ornaments', 'Tree Tables', 'Tree Skirts', 'Tinsel', 'Wreaths', 'Lights and', 'YARD FURNITURE', 'LIGHTS PILLOWS AND BUGZ', 'Yard', 'Fire', 'Pot', 'Garden', 'Seeds', 'Bugz', 'F68', 'F77', 'Halloween', 'TAT', 'Wrap', 'Mini Seasonal', 'Mini Christmas', 'Da Forest', 'TAT STYLE', 'Valentine', 'Gameday', 'Outdoor fun', 'Organization', 'Snacktime', 'Composition', 'Art', 'Backpacks', 'ODL'],

    'Tech': ['TECH', 'ELECTRONICS', '13 - ELEC', 'ENTERTAINMENT'],

    'Style': ['STYLE', 'APPAREL', 'FOLDING', 'INTIMATES', 'BOYS/GIRLS', 'HANGING', 'NOP (A&A)'],

    'Food': ['FOOD', 'GROCERY', 'WATER', 'PASTA', 'SPICES', 'BAKING', 'CEREAL', 'COFFEE', 'CANDY', 'COOKIES', 'CHIPS', 'BEVERAGE','CANNED GOODS','BREAKFAST', 'JUICE', 'Ethnic', 'Condiments']

}





def extract_trailer_name(uploaded_file):

    """Extract trailer name by scanning the content for the 'Trailer #' pattern."""

    try:

        if uploaded_file.filename.endswith('.xlsx'):

            temp_df = pd.read_excel(uploaded_file, engine='openpyxl')

        elif uploaded_file.filename.endswith('.csv'):

            uploaded_file.stream.seek(0)  # Ensure the file stream is at the start*

            temp_df = pd.read_csv(uploaded_file)

        else:

            return None



        # Convert all values to strings and search for 'Trailer #' in the entire DataFrame*

        for col in temp_df.columns:

            for cell in temp_df[col]:

                if isinstance(cell, str) and re.search(r'Trailer\s?#\S+', cell):

                    match = re.search(r'Trailer\s?#\S+', cell)

                    if match:

                        return match.group(0)



        return None

    except Exception as e:

        print(f"Error extracting trailer name from {uploaded_file.filename}: {e}")

        return None





def map_to_section(custom_block):

    """Map a custom block to its respective section based on keywords."""

    if not isinstance(custom_block, str):

        return "Uncategorized"

    # Dedicated OTC blocks: keep them separate from the rest of HBA.
    # Match the merchandise description, independent of leading block numbers.
    normalized_block = re.sub(r"[^A-Z0-9]+", " ", custom_block.upper()).strip()
    if ("PROTEIN DIGESTION COLD ALLERGY" in normalized_block
            or "OTC FEM CARE" in normalized_block):
        return "OTC"

    for section, keywords in automated_mapping.items():

        for keyword in keywords:

            if keyword.upper() in custom_block.upper():

                return section

    return "Uncategorized"



@app.route("/")

def main_menu():

    """Render the main menu."""

    global uploaded_files_info

    return render_template("main_menu.html", uploaded_files=uploaded_files_info)









@app.route('/stocking-rates')
def stocking_rates_view():
    """Read-only reference for the exact rates and fallbacks currently used."""
    from stocking_rates import RATES, normalize
    from department_fallback import (
        DEPARTMENT_KEYS, KEY_TO_DEPT, department_average, overall_proxy
    )
    rows = []
    for key, case_rate, repack_rate in RATES:
        dept = KEY_TO_DEPT.get(normalize(key), 'Unassigned')
        dept_case = department_average(dept, 'case') if dept != 'Unassigned' else None
        dept_repack = department_average(dept, 'repack') if dept != 'Unassigned' else None
        rows.append({
            'block': key,
            'department': dept,
            'case': case_rate if case_rate is not None else (dept_case if dept_case is not None else overall_proxy('case')),
            'repack': repack_rate if repack_rate is not None else (dept_repack if dept_repack is not None else overall_proxy('repack')),
            'case_source': 'Custom-block rate' if case_rate is not None else ('Department average' if dept_case is not None else 'Storewide proxy'),
            'repack_source': 'Custom-block rate' if repack_rate is not None else ('Department average' if dept_repack is not None else 'Storewide proxy'),
        })
    rows.sort(key=lambda row: (row['department'], row['block']))
    departments = [
        {'name': dept,
         'case': department_average(dept, 'case') if department_average(dept, 'case') is not None else overall_proxy('case'),
         'repack': department_average(dept, 'repack') if department_average(dept, 'repack') is not None else overall_proxy('repack'),
         'case_proxy': department_average(dept, 'case') is None,
         'repack_proxy': department_average(dept, 'repack') is None}
        for dept in sorted(DEPARTMENT_KEYS)
    ]
    return render_template_string(STOCKING_RATES_PAGE,
        rows=rows, departments=departments,
        proxy_case=overall_proxy('case'), proxy_repack=overall_proxy('repack'))


STOCKING_RATES_PAGE = r"""
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stocking Rates & Formulas</title>
<style>
body{font-family:Arial,sans-serif;max-width:1150px;margin:32px auto;padding:0 18px;color:#e8edf4;background:#111820}
a{color:#9bc8ed}.back{display:inline-block;margin-bottom:16px}
h1{margin:8px 0 10px}h2{margin-top:30px}
.note{background:#1b2530;border:1px solid #334355;border-radius:8px;padding:15px;line-height:1.6}
.table-wrap{overflow-x:auto;background:#1b2530;border:1px solid #334355;border-radius:8px}
table{width:100%;border-collapse:collapse}th,td{padding:10px 12px;border-bottom:1px solid #334355;text-align:left}
th{background:#253343;position:sticky;top:0}td.num{text-align:right;font-variant-numeric:tabular-nums}
small,.muted{color:#a4b4c5}.formula{font-family:Consolas,monospace;background:#253343;padding:9px;border-radius:4px;display:block;overflow-x:auto}
.proxy{display:block;color:#e3b780;font-size:11px;margin-top:3px}.rate{font-weight:700;font-size:16px}.units{font-size:12px;color:#a4b4c5}.table-wrap tr:hover td{background:#223040}</style></head><body>
<a class="back" href="{{ url_for('main_menu') }}">← Back to Main Menu</a>
<h1>Stocking Rates & Formulas</h1>
<p class="muted">Preliminary historical estimates, not official Target standards. Rates are minutes per carton.</p>
<div class="note">
<strong>Formula:</strong>
<code class="formula">Estimated hours = (full-case cartons × case minutes + repack cartons × repack minutes) / 60</code>
<p><strong>How rates are chosen:</strong> Use a matching custom-block rate first. If a case or repack rate is missing, use the average of known rates within the same department. If that department has no known rate for that carton type, use the provisional storewide median. These averages are currently <strong>unweighted</strong>.</p>
<p><strong>Original times:</strong> A report with positive Target stocking times keeps those values; blanks may be estimated. If an uploaded report has no positive stocking times, its freight rows with zero or blank hours are estimated. Each file is checked independently.</p>
<p><strong>Important:</strong> A missing custom-block rate does not mean zero minutes. Storewide proxies are a rough fallback and may be less accurate, especially for Style and Seasonal.</p>
</div>
<h2>Stocking time per item, by department</h2>
<p class="muted">Each value is the estimated time to stock <strong>one</strong> carton in that area. Department rates are averages of available historical custom-block rates. An orange proxy label means the storewide median is used instead.</p>
<div class="table-wrap"><table><thead><tr><th>Area</th><th>1 case takes</th><th>1 repack takes</th></tr></thead><tbody>
{% for row in departments %}<tr><td><strong>{{ row.name }}</strong></td>
<td><span class="rate">{{ '%.2f'|format(row.case) if row.case is not none else 'N/A' }}</span> <span class="units">minutes</span>{% if row.case_proxy %}<span class="proxy">Storewide proxy</span>{% endif %}</td>
<td><span class="rate">{{ '%.2f'|format(row.repack) if row.repack is not none else 'N/A' }}</span> <span class="units">minutes</span>{% if row.repack_proxy %}<span class="proxy">Storewide proxy</span>{% endif %}</td></tr>{% endfor %}
</tbody></table></div>
<p><small>Storewide median fallback: <strong>{{ '%.2f'|format(proxy_case) if proxy_case is not none else 'N/A' }}</strong> minutes per case and <strong>{{ '%.2f'|format(proxy_repack) if proxy_repack is not none else 'N/A' }}</strong> minutes per repack.</small></p>
<h2>Custom-block rates</h2>
<p class="muted">Estimated minutes to stock <strong>one case</strong> or <strong>one repack</strong> in each custom block. Fallback values are labeled so you can distinguish them from historical block rates.</p>
<div class="table-wrap"><table><thead><tr><th>Custom-block match</th><th>Department</th><th>1 case takes</th><th>1 repack takes</th></tr></thead><tbody>
{% for row in rows %}<tr><td>{{ row.block }}</td><td>{{ row.department }}</td>
<td><span class="rate">{{ '%.2f'|format(row.case) if row.case is not none else 'N/A' }}</span> <span class="units">minutes</span>{% if row.case_source != 'Custom-block rate' %}<span class="proxy">{{ row.case_source }}</span>{% endif %}</td>
<td><span class="rate">{{ '%.2f'|format(row.repack) if row.repack is not none else 'N/A' }}</span> <span class="units">minutes</span>{% if row.repack_source != 'Custom-block rate' %}<span class="proxy">{{ row.repack_source }}</span>{% endif %}</td></tr>{% endfor %}
</tbody></table></div>
<p class="muted"><small>Names are matching keywords used by the calculator. The app maps the uploaded custom block to a department before calculating estimates.</small></p>
<a class="back" href="{{ url_for('main_menu') }}">← Back to Main Menu</a>
</body></html>
"""

@app.route("/upload", methods=["POST"])

def upload_files():

    """Handle file uploads and categorize trailers as HDC or RDC."""

    global all_data, trailer_names, uploaded_files_info

    uploaded_files = request.files.getlist("files")

    if not uploaded_files:

        return redirect(url_for("main_menu"))



    for uploaded_file in uploaded_files:

        try:

            # Read the uploaded file into a DataFrame*

            if uploaded_file.filename.endswith('.csv'):

                uploaded_file.stream.seek(0)

                temp_df = pd.read_csv(uploaded_file)

            elif uploaded_file.filename.endswith('.xlsx'):

                temp_df = pd.read_excel(uploaded_file, engine='openpyxl')

            else:

                continue



            # Extract trailer name*

            trailer_name = extract_trailer_name(uploaded_file)

            if trailer_name:

                # Check if the trailer has repacks*

                temp_df['REPACK CARTONS'] = pd.to_numeric(temp_df['REPACK CARTONS'], errors='coerce').fillna(0)

                if temp_df['REPACK CARTONS'].sum() > 0:

                    trailer_name += " (RDC)"

                else:

                    trailer_name += " (HDC)"

                trailer_names.append(trailer_name)

            else:

                trailer_name = "Unknown Trailer"



            # Store the file name and associated trailer name*

            uploaded_files_info.append((uploaded_file.filename, trailer_name))



            temp_df['Section'] = temp_df['CUSTOM BLOCK'].apply(map_to_section)
            temp_df = fill_missing_stocking_times(temp_df)



            # Combine the file data into the main DataFrame*

            all_data = pd.concat([all_data, temp_df], ignore_index=True)

        except Exception as e:

            print(f"Error processing file {uploaded_file.filename}: {e}")

            continue



    return redirect(url_for("main_menu"))



@app.route("/process", methods=["GET", "POST"])

def process_data():

    """Process data and summarize it."""

    global all_data, summary

    if all_data.empty:

        return redirect(url_for("main_menu"))



    # Map sections*

    all_data['Section'] = all_data['CUSTOM BLOCK'].apply(map_to_section)



    # Log initial sections to debug the mapping*

    print("Initial Section Counts (Before Filtering):")

    print(all_data['Section'].value_counts())



    # Permanently exclude "Uncategorized" rows from all_data*

    all_data = all_data[all_data['Section'] != "Uncategorized"]



    # Log filtered sections to confirm exclusion*

    print("Filtered Section Counts (After Removing Uncategorized):")

    print(all_data['Section'].value_counts())



    # If it's a GET request, show the exclusion form*

    if request.method == "GET":

        all_sections = sorted(all_data['Section'].unique())

        return render_template("exclude_sections.html", sections=all_sections)



    # If it's a POST request, exclude selected sections*

    excluded_sections = request.form.getlist("sections")

    if excluded_sections:

        all_data = all_data[~all_data['Section'].isin(excluded_sections)]



    # Ensure numeric columns for aggregation*

    numeric_columns = ['FULL CASE CARTONS', 'REPACK CARTONS', 'STOCKING TIME (HRS)']

    for col in numeric_columns:

        all_data[col] = pd.to_numeric(all_data[col], errors='coerce')

        if col != 'STOCKING TIME (HRS)':

            all_data[col] = all_data[col].fillna(0)



    # Summarize the data*

    summary = all_data.groupby('Section')[numeric_columns].sum(min_count=1)



    # Add the Workload % column*

    total_stocking_time = summary['STOCKING TIME (HRS)'].sum()

    if total_stocking_time > 0:

        summary['Workload %'] = (summary['STOCKING TIME (HRS)'] / total_stocking_time * 100).round(1)

    else:

        summary['Workload %'] = 0



    # Remove "Uncategorized" again if it still sneaks into summary*

    if "Uncategorized" in summary.index:

        print("Uncategorized found in summary, removing it...")

        summary = summary[summary.index != "Uncategorized"]



    # Add a Total row*

    total_row = summary.sum(numeric_only=True, min_count=1).rename("Total")

    summary = pd.concat([summary, total_row.to_frame().T])



    # Round all numeric values to the nearest tenth*

    summary = summary.round(1)



    # Debug final summary*

    print("Final Summary (Post Processing):")

    print(summary)



    return redirect(url_for("summary_view"))









@app.route("/reset")

def reset_data():

    """Reset all data."""

    global all_data, summary, trailer_names, uploaded_files_info

    all_data = pd.DataFrame()

    summary = None

    trailer_names = []

    uploaded_files_info = []  # Clear the uploaded files list*

    return redirect(url_for("main_menu"))





@app.route("/generate_chart")

def generate_chart():

    """Generate a pie chart for the summary data."""

    global summary

    if summary is None:

        return "No data to generate chart", 404



    # Exclude the "Total" row and "Uncategorized" section*

    chart_data = summary.loc[

        (summary.index != "Total") & (summary.index != "Uncategorized"), "Workload %"

    ]



    # Generate pie chart*

    fig, ax = plt.subplots(figsize=(6, 6))

    ax.pie(

        chart_data,

        labels=chart_data.index,

        autopct='%1.1f%%',

        startangle=140,

        wedgeprops={'edgecolor': 'black'}

    )

    ax.set_title("Workload Distribution by Section")



    # Save the figure to a BytesIO stream*

    from io import BytesIO

    output = BytesIO()

    plt.savefig(output, format="png")

    plt.close(fig)

    output.seek(0)



    # Serve the image as a response*

    return Response(output, content_type="image/png")







@app.route("/summary")

def summary_view():

    """Display the summary."""

    global summary, trailer_names

    if summary is None:

        return redirect(url_for("main_menu"))



    # Pass the chart URL to the template*

    chart_url = url_for("generate_chart")

    return render_template("summary.html", summary_data=summary, trailer_names=trailer_names, chart_url=chart_url)







@app.route("/download_breakout_pdf")

def download_breakout_pdf():

    """Generate a printable Inbound Breakout PDF with cases/repacks and stocking time."""

    global summary

    if summary is None:

        return redirect(url_for("main_menu"))



    from io import BytesIO

    from reportlab.lib.pagesizes import letter

    from reportlab.lib.units import inch

    from reportlab.pdfgen import canvas

    from reportlab.pdfbase import pdfmetrics



    def to_float(value, default=0.0):

        """Convert a value to float safely."""

        try:

            return float(value)

        except (TypeError, ValueError):

            return default



    def pluralize_count(count, singular, plural):

        """Return a count with the correct singular/plural label."""

        return f"{count} {singular if count == 1 else plural}"



    def format_case_repack(cases_value, repacks_value):

        """Format case/repack counts like: 50 cases / 20 repacks.

        If repacks are 0, only show cases.

        """

        cases = int(round(to_float(cases_value)))

        repacks = int(round(to_float(repacks_value)))



        cases_text = pluralize_count(cases, "case", "cases")

        if repacks <= 0:

            return cases_text



        repacks_text = pluralize_count(repacks, "repack", "repacks")

        return f"{cases_text} / {repacks_text}"



    def format_stocking_time(hours_value):

        """Round stocking time to the nearest 15 minutes and format as hours/minutes.



        Examples:

            1.25 -> 1 hr 15 min

            2.50 -> 2 hrs 30 min

            0.75 -> 45 min

        """

        hours = max(0.0, to_float(hours_value))

        total_minutes = int((hours * 60 + 7.5) // 15) * 15



        whole_hours, minutes = divmod(total_minutes, 60)



        parts = []

        if whole_hours:

            hour_label = "hr" if whole_hours == 1 else "hrs"

            parts.append(f"{whole_hours} {hour_label}")



        if minutes:

            parts.append(f"{minutes} min")



        return " ".join(parts) if parts else "0 min"



    sections = [

        ("Chem/Paper", "Chemical-Paper"),

        ("Pets", "Pets"),

        ("HBA", "HBA"),

        ("OTC", "OTC"),

        ("Stationery", "Stationery"),

        ("Kitchen", "Kitchen"),

        ("C&D", "C-D"),

        ("Toy", "Toys"),

        ("Sports", "Sports"),

        ("Seasonal", "Seasonal"),

        ("Infants", "Infants"),

        ("Style", "Style"),

        ("Tech", "Tech"),

        ("Food", "Food"),

    ]



    output = BytesIO()

    c = canvas.Canvas(output, pagesize=letter)

    page_width, page_height = letter



    # Page and table layout. These values are tuned to match your breakout sheet.*

    left = 0.32 * inch

    table_top = 9.55 * inch

    table_width = page_width - (0.64 * inch)



    col1_width = 2.45 * inch

    col3_width = 1.05 * inch

    col2_width = table_width - col1_width - col3_width

    row_height = 0.58 * inch



    x1 = left

    x2 = x1 + col1_width

    x3 = x2 + col2_width

    x4 = x1 + table_width

    table_bottom = table_top - (row_height * len(sections))



    # Main title*

    c.setFont("Helvetica-Bold", 24)

    c.drawCentredString(page_width / 2, 10.48 * inch, "Inbound Breakout")



    # Column titles above the table, centered and without a bordered title row.*

    c.setFont("Helvetica-Bold", 12)

    c.drawCentredString(x1 + col1_width / 2, table_top + 0.16 * inch, "During Unload")

    c.drawCentredString(x2 + col2_width / 2, table_top + 0.16 * inch, "After Unload")

    c.drawCentredString(x3 + col3_width / 2, table_top + 0.16 * inch, "Stocking Time")



    # Table grid*

    c.setLineWidth(0.8)

    for x in (x1, x2, x3, x4):

        c.line(x, table_top, x, table_bottom)



    for i in range(len(sections) + 1):

        y = table_top - (i * row_height)

        c.line(x1, y, x4, y)



    # Row labels and auto-filled stocking data.*

    section_font_size = 9.5

    c.setFont("Helvetica", section_font_size)



    for i, (display_name, summary_key) in enumerate(sections):

        y_top = table_top - (i * row_height)

        label_y = y_top - 0.15 * inch



        # Section labels slightly high in each row for more writing room.*

        c.setFont("Helvetica", section_font_size)

        c.drawString(x1 + 0.10 * inch, label_y, display_name)

        c.drawString(x2 + 0.10 * inch, label_y, display_name)



        # Auto-fill cases / repacks and stocking time in the right column.*

        if summary_key in summary.index:

            case_repack_text = format_case_repack(

                summary.loc[summary_key, "FULL CASE CARTONS"],

                summary.loc[summary_key, "REPACK CARTONS"]

            )

            hours_text = format_stocking_time(summary.loc[summary_key, "STOCKING TIME (HRS)"])



            center_x = x3 + col3_width / 2



            # Case/repack count: slightly smaller, regular weight, lowercase labels.*

            c.setFont("Helvetica", 7.0)

            c.drawCentredString(center_x, y_top - 0.17 * inch, case_repack_text)



            # Stocking time: centered and automatically reduced only when needed.*

            time_font = "Helvetica-Bold"

            time_font_size = 11.5

            available_width = col3_width - (0.10 * inch)



            while (

                time_font_size > 8.0

                and pdfmetrics.stringWidth(hours_text, time_font, time_font_size) > available_width

            ):

                time_font_size -= 0.5



            c.setFont(time_font, time_font_size)

            c.drawCentredString(center_x, y_top - 0.42 * inch, hours_text)



    # Bottom labels*

    c.setFont("Helvetica-Bold", 11)

    bottom_label_y = table_bottom - 0.27 * inch

    c.drawString(x1, bottom_label_y, "4AM Team Members:")

    c.drawString(x1 + 3.65 * inch, bottom_label_y, "Residual Push:")



    c.save()

    output.seek(0)



    return send_file(

        output,

        as_attachment=True,

        download_name="Inbound_Breakout.pdf",

        mimetype="application/pdf"

    )





@app.route("/details/<section>")

def section_details(section):

    """Show details for a specific section."""

    global all_data

    section_data = all_data[all_data['Section'] == section]

    if section_data.empty:

        return redirect(url_for("summary_view"))

    return render_template("details.html", section_name=section, section_data=section_data.to_html(index=False))



@app.route("/mappings")

def view_mappings():

    """View mappings."""

    global all_data

    if all_data.empty:

        return redirect(url_for("main_menu"))

    return render_template("mappings.html", mappings=all_data[['CUSTOM BLOCK', 'Section']].to_html(index=False))



@app.route("/exclude_sections", methods=["GET", "POST"])

def exclude_sections():

    global all_data, summary

    if all_data.empty:

        return redirect(url_for("main_menu"))



    # Get unique sections available in the data*

    all_sections = all_data['Section'].unique() if 'Section' in all_data else []



    if request.method == "POST":

        # Get selected sections to exclude*

        sections_to_exclude = request.form.getlist("sections")

        if sections_to_exclude:

            all_data = all_data[~all_data['Section'].isin(sections_to_exclude)]



        # Recalculate the summary after exclusions*

        numeric_columns = ['FULL CASE CARTONS', 'REPACK CARTONS', 'STOCKING TIME (HRS)']

        for col in numeric_columns:

            all_data[col] = pd.to_numeric(all_data[col], errors='coerce')

        if col != 'STOCKING TIME (HRS)':

            all_data[col] = all_data[col].fillna(0)



        summary = all_data.groupby('Section')[numeric_columns].sum(min_count=1)



        # Add the Workload % column*

        total_stocking_time = summary['STOCKING TIME (HRS)'].sum()

        if total_stocking_time > 0:

            summary['Workload %'] = (summary['STOCKING TIME (HRS)'] / total_stocking_time * 100).round(1)

        else:

            summary['Workload %'] = 0



        # Add a Total row*

        total_row = summary.sum(numeric_only=True, min_count=1).rename("Total")

        summary = pd.concat([summary, total_row.to_frame().T])



        summary = summary.round(1)



        return redirect(url_for("summary_view"))



    return render_template("exclude_sections.html", sections=all_sections)



@app.route("/generate_email")

def generate_email():

    """Generate a recap email based on the processed data."""

    global all_data



    if all_data.empty:

        return redirect(url_for("main_menu"))



    # Categorize into push, backstock, and bulk backstock*

    push_sections = ['Kitchen', 'Stationery', 'Style', 'Food']  # Example sections for push*

    backstock_sections = ['HBA', 'OTC', 'Sports', 'Toys', 'Chemical-Paper', 'Seasonal']

    bulk_backstock_sections = ['C-D']  # Example section for bulk backstock*



    push_data = all_data[all_data['Section'].isin(push_sections)]

    backstock_data = all_data[all_data['Section'].isin(backstock_sections)]

    bulk_backstock_data = all_data[all_data['Section'].isin(bulk_backstock_sections)]



    # Count quantities for each type*

    def summarize_data(data):

        summary = {}

        for section in data['Section'].unique():

            section_data = data[data['Section'] == section]

            summary[section] = {

                'flats': section_data['FULL CASE CARTONS'].sum(),

                'carts': section_data['REPACK CARTONS'].sum(),

                'pallets': section_data['STOCKING TIME (HRS)'].sum(),

                # Add 'uboats' if available*

            }

        return summary



    push_summary = summarize_data(push_data)

    backstock_summary = summarize_data(backstock_data)

    bulk_backstock_summary = summarize_data(bulk_backstock_data)



    # Format the email content*

    email_content = "Good morning team!\n\n"

    email_content += "Here is the recap of what we left back:\n\n"



    def format_section(title, data):

        content = f"{title}:\n"

        for section, counts in data.items():

            content += f"{section}: {counts['flats']} flats, {counts['carts']} carts, {counts['pallets']} pallets\n"

        return content



    email_content += format_section("Push", push_summary)

    email_content += format_section("Backstock", backstock_summary)

    email_content += format_section("Bulk Backstock", bulk_backstock_summary)



    email_content += "\nPlease let me know if you have any questions. Thank you!"



    return render_template("email_preview.html", email_content=email_content)



@app.route("/email_form", methods=["GET", "POST"])

def email_form():

    global all_data



    predefined_sections = [

        'C-D', 'Food', 'Chemical-Paper', 'HBA', 'OTC', 'Infants',

        'Style', 'Pets', 'Sports', 'Tech', 'Kitchen',

        'BPG-CL-FA', 'Stationery', 'Seasonal', 'Toys'

    ]



    sections = sorted(all_data['Section'].unique()) if not all_data.empty else predefined_sections



    if request.method == "POST":

        summary_data = request.form.get('summaryData')

        last_night = request.form.get('last_night', '')

        heavy_last_night = request.form.get('heavy_last_night', '')

        tonight = request.form.get('tonight', '')

        heavy_tonight = request.form.get('heavy_tonight', '')



        email_content = f"Good morning team!\n\nLast night we took a {last_night}."

        if heavy_last_night:

            email_content += f" It was heavy in {heavy_last_night}.\n\n"



        if summary_data:

            summary_items = eval(summary_data)

            for category, items in summary_items.items():

                if items:

                    email_content += f"{category}:\n"

                    for item in items:

                        email_content += f"- {item}\n"

                    email_content += "\n"



        email_content += f"Tonight we will take a {tonight}."

        if heavy_tonight:

            email_content += f" It will be heavy in {heavy_tonight}.\n\n"



        email_content += "Please let me know if you have any questions. Thank you!"



        return render_template("email_preview.html", email_content=email_content)



    return render_template("email_form.html", sections=sections)





if __name__ == "__main__":

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


