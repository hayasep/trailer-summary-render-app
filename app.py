import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for rendering
from flask import Flask, render_template, request, redirect, url_for, send_file
import pandas as pd
import re
import io
import matplotlib.pyplot as plt
import os
from flask import Response

app = Flask(__name__)

# Global variables to store data
all_data = pd.DataFrame()
summary = None
trailer_names = []
uploaded_files_info = []  # List to store file name and trailer name pairs

# Automated mappings with updated section names
automated_mapping = {
    'Pets': ['PETS', 'DOG', 'CAT', 'LITTER'],
    'Toys': ['TOY', 'LEGOS', 'BOYS ACTION', 'E42', 'Preschool', 'Boys Girls', 'Dolls Collectables', 'RC and Cars', 'Nerf'],
    'Chemical-Paper': ['CHEMICAL', 'PAPER', 'BLEACH', 'LAUNDRY', 'HOUSEHOLD', 'AIR FRESHENER', 'DISH SOAP', 'Plates', 'TRASH BAGS'],
    'HBA': ['HBA', 'BEAUTY', 'HEALTH', 'COSMETICS', 'HAIR', 'OTC', 'ORAL', 'FEMININE', 'Pads', 'Shampoo', 'Travel', 's Care', 'Mouthwash','Face Wash', 'Skin Care', 'Vitamins', 'Digestion', 'Tampons', 'Shave', 'Toothpaste', 'First Aid', 'PROTEIN', 'MENS'],
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
            uploaded_file.stream.seek(0)  # Ensure the file stream is at the start
            temp_df = pd.read_csv(uploaded_file)
        else:
            return None

        # Convert all values to strings and search for 'Trailer #' in the entire DataFrame
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



@app.route("/upload", methods=["POST"])
def upload_files():
    """Handle file uploads and categorize trailers as HDC or RDC."""
    global all_data, trailer_names, uploaded_files_info
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return redirect(url_for("main_menu"))

    for uploaded_file in uploaded_files:
        try:
            # Read the uploaded file into a DataFrame
            if uploaded_file.filename.endswith('.csv'):
                uploaded_file.stream.seek(0)
                temp_df = pd.read_csv(uploaded_file)
            elif uploaded_file.filename.endswith('.xlsx'):
                temp_df = pd.read_excel(uploaded_file, engine='openpyxl')
            else:
                continue

            # Extract trailer name
            trailer_name = extract_trailer_name(uploaded_file)
            if trailer_name:
                # Check if the trailer has repacks
                temp_df['REPACK CARTONS'] = pd.to_numeric(temp_df['REPACK CARTONS'], errors='coerce').fillna(0)
                if temp_df['REPACK CARTONS'].sum() > 0:
                    trailer_name += " (RDC)"
                else:
                    trailer_name += " (HDC)"
                trailer_names.append(trailer_name)
            else:
                trailer_name = "Unknown Trailer"

            # Store the file name and associated trailer name
            uploaded_files_info.append((uploaded_file.filename, trailer_name))

            # Combine the file data into the main DataFrame
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

    # Map sections
    all_data['Section'] = all_data['CUSTOM BLOCK'].apply(map_to_section)

    # Log initial sections to debug the mapping
    print("Initial Section Counts (Before Filtering):")
    print(all_data['Section'].value_counts())

    # Permanently exclude "Uncategorized" rows from all_data
    all_data = all_data[all_data['Section'] != "Uncategorized"]

    # Log filtered sections to confirm exclusion
    print("Filtered Section Counts (After Removing Uncategorized):")
    print(all_data['Section'].value_counts())

    # If it's a GET request, show the exclusion form
    if request.method == "GET":
        all_sections = sorted(all_data['Section'].unique())
        return render_template("exclude_sections.html", sections=all_sections)

    # If it's a POST request, exclude selected sections
    excluded_sections = request.form.getlist("sections")
    if excluded_sections:
        all_data = all_data[~all_data['Section'].isin(excluded_sections)]

    # Ensure numeric columns for aggregation
    numeric_columns = ['FULL CASE CARTONS', 'REPACK CARTONS', 'STOCKING TIME (HRS)']
    for col in numeric_columns:
        all_data[col] = pd.to_numeric(all_data[col], errors='coerce').fillna(0)

    # Summarize the data
    summary = all_data.groupby('Section')[numeric_columns].sum()

    # Add the Workload % column
    total_stocking_time = summary['STOCKING TIME (HRS)'].sum()
    if total_stocking_time > 0:
        summary['Workload %'] = (summary['STOCKING TIME (HRS)'] / total_stocking_time * 100).round(1)
    else:
        summary['Workload %'] = 0

    # Remove "Uncategorized" again if it still sneaks into summary
    if "Uncategorized" in summary.index:
        print("Uncategorized found in summary, removing it...")
        summary = summary[summary.index != "Uncategorized"]

    # Add a Total row
    total_row = summary.sum(numeric_only=True).rename("Total")
    summary = pd.concat([summary, total_row.to_frame().T])

    # Round all numeric values to the nearest tenth
    summary = summary.round(1)

    # Debug final summary
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
    uploaded_files_info = []  # Clear the uploaded files list
    return redirect(url_for("main_menu"))


@app.route("/generate_chart")
def generate_chart():
    """Generate a pie chart for the summary data."""
    global summary
    if summary is None:
        return "No data to generate chart", 404

    # Exclude the "Total" row and "Uncategorized" section
    chart_data = summary.loc[
        (summary.index != "Total") & (summary.index != "Uncategorized"), "Workload %"
    ]

    # Generate pie chart
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        chart_data,
        labels=chart_data.index,
        autopct='%1.1f%%',
        startangle=140,
        wedgeprops={'edgecolor': 'black'}
    )
    ax.set_title("Workload Distribution by Section")
    
    # Save the figure to a BytesIO stream
    from io import BytesIO
    output = BytesIO()
    plt.savefig(output, format="png")
    plt.close(fig)
    output.seek(0)

    # Serve the image as a response
    return Response(output, content_type="image/png")



@app.route("/summary")
def summary_view():
    """Display the summary."""
    global summary, trailer_names
    if summary is None:
        return redirect(url_for("main_menu"))

    # Pass the chart URL to the template
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

    def format_hours_fraction(hours_value):
        """Round stocking time to the nearest quarter hour and format with clean fraction glyphs.
        Examples: 5.4 -> 5½ hrs, 3.2 -> 3¼ hrs.
        """
        hours = max(0.0, to_float(hours_value))
        quarters = int((hours * 4) + 0.5)
        whole_hours = quarters // 4
        quarter_part = quarters % 4

        fraction_text = {
            0: "",
            1: "¼",
            2: "½",
            3: "¾",
        }[quarter_part]

        if whole_hours and fraction_text:
            return f"{whole_hours}{fraction_text} hours"
        if whole_hours:
            return f"{whole_hours} hours"
        if fraction_text:
            return f"{fraction_text} hours"
        return "0 hours"

    sections = [
        ("Chem/Paper", "Chemical-Paper"),
        ("Pets", "Pets"),
        ("HBA", "HBA"),
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

    # Page and table layout. These values are tuned to match your breakout sheet.
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

    # Main title
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(page_width / 2, 10.48 * inch, "Inbound Breakout")

    # Column titles above the table, centered and without a bordered title row.
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x1 + col1_width / 2, table_top + 0.16 * inch, "During Unload")
    c.drawCentredString(x2 + col2_width / 2, table_top + 0.16 * inch, "After Unload")
    c.drawCentredString(x3 + col3_width / 2, table_top + 0.16 * inch, "Stocking Time (Hrs)")

    # Table grid
    c.setLineWidth(0.8)
    for x in (x1, x2, x3, x4):
        c.line(x, table_top, x, table_bottom)

    for i in range(len(sections) + 1):
        y = table_top - (i * row_height)
        c.line(x1, y, x4, y)

    # Row labels and auto-filled stocking data.
    section_font_size = 9.5
    c.setFont("Helvetica", section_font_size)

    for i, (display_name, summary_key) in enumerate(sections):
        y_top = table_top - (i * row_height)
        label_y = y_top - 0.15 * inch

        # Section labels slightly high in each row for more writing room.
        c.setFont("Helvetica", section_font_size)
        c.drawString(x1 + 0.10 * inch, label_y, display_name)
        c.drawString(x2 + 0.10 * inch, label_y, display_name)

        # Auto-fill cases / repacks and stocking time in the right column.
        if summary_key in summary.index:
            case_repack_text = format_case_repack(
                summary.loc[summary_key, "FULL CASE CARTONS"],
                summary.loc[summary_key, "REPACK CARTONS"]
            )
            hours_text = format_hours_fraction(summary.loc[summary_key, "STOCKING TIME (HRS)"])

            center_x = x3 + col3_width / 2

            # Case/repack count: slightly smaller, regular weight, lowercase labels.
            c.setFont("Helvetica", 7.0)
            c.drawCentredString(center_x, y_top - 0.17 * inch, case_repack_text)

            # Stocking time: bold number/fraction with smaller regular "hrs".
            hours_number = hours_text.replace(" hours", "")
            number_font = "Helvetica-Bold"
            number_size = 13.2
            hrs_font = "Helvetica"
            hrs_size = 8.5
            space = " "

            number_width = pdfmetrics.stringWidth(hours_number, number_font, number_size)
            space_width = pdfmetrics.stringWidth(space, hrs_font, hrs_size)
            hrs_width = pdfmetrics.stringWidth("hours", hrs_font, hrs_size)
            total_width = number_width + space_width + hrs_width
            start_x = center_x - (total_width / 2)
            baseline_y = y_top - 0.42 * inch

            c.setFont(number_font, number_size)
            c.drawString(start_x, baseline_y, hours_number)
            c.setFont(hrs_font, hrs_size)
            c.drawString(start_x + number_width + space_width, baseline_y, "hours")

    # Bottom labels
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

    # Get unique sections available in the data
    all_sections = all_data['Section'].unique() if 'Section' in all_data else []

    if request.method == "POST":
        # Get selected sections to exclude
        sections_to_exclude = request.form.getlist("sections")
        if sections_to_exclude:
            all_data = all_data[~all_data['Section'].isin(sections_to_exclude)]

        # Recalculate the summary after exclusions
        numeric_columns = ['FULL CASE CARTONS', 'REPACK CARTONS', 'STOCKING TIME (HRS)']
        for col in numeric_columns:
            all_data[col] = pd.to_numeric(all_data[col], errors='coerce').fillna(0)

        summary = all_data.groupby('Section')[numeric_columns].sum()

        # Add the Workload % column
        total_stocking_time = summary['STOCKING TIME (HRS)'].sum()
        if total_stocking_time > 0:
            summary['Workload %'] = (summary['STOCKING TIME (HRS)'] / total_stocking_time * 100).round(1)
        else:
            summary['Workload %'] = 0

        # Add a Total row
        total_row = summary.sum(numeric_only=True).rename("Total")
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

    # Categorize into push, backstock, and bulk backstock
    push_sections = ['Kitchen', 'Stationery', 'Style', 'Food']  # Example sections for push
    backstock_sections = ['HBA', 'Sports', 'Toys', 'Chemical-Paper', 'Seasonal']
    bulk_backstock_sections = ['C-D']  # Example section for bulk backstock

    push_data = all_data[all_data['Section'].isin(push_sections)]
    backstock_data = all_data[all_data['Section'].isin(backstock_sections)]
    bulk_backstock_data = all_data[all_data['Section'].isin(bulk_backstock_sections)]

    # Count quantities for each type
    def summarize_data(data):
        summary = {}
        for section in data['Section'].unique():
            section_data = data[data['Section'] == section]
            summary[section] = {
                'flats': section_data['FULL CASE CARTONS'].sum(),
                'carts': section_data['REPACK CARTONS'].sum(),
                'pallets': section_data['STOCKING TIME (HRS)'].sum(),
                # Add 'uboats' if available
            }
        return summary

    push_summary = summarize_data(push_data)
    backstock_summary = summarize_data(backstock_data)
    bulk_backstock_summary = summarize_data(bulk_backstock_data)

    # Format the email content
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
        'C-D', 'Food', 'Chemical-Paper', 'HBA', 'Infants',
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

