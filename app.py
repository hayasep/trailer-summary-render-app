import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for rendering
from flask import Flask, render_template, request, redirect, url_for
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
    'Toys': ['TOY', 'LEGOS', 'BOYS ACTION', 'E42'],
    'Chemical-Paper': ['CHEMICAL', 'PAPER', 'BLEACH', 'LAUNDRY', 'HOUSEHOLD', 'AIR FRESHENER'],
    'HBA': ['HBA', 'BEAUTY', 'HEALTH', 'COSMETICS', 'SOAP', 'HAIR', 'OTC', 'ORAL', 'FEMININE'],
    'Infants': ['INFANT', 'BABY', 'NURSING', 'DIAPERS'],
    'C-D': ['C/D', 'BED', 'BATH', 'RUGS', 'LAMP', 'KITCHEN PLUG', 'APPLIANCE', 'PILLOWS', 'FURNITURE', 'STORAGE', 'PLASTIC', 'VACUUM', 'VIGNETTE', 'HEARTH'],
    'Kitchen': ['KITCHEN'],
    'Stationery': ['STATIONERY', 'OFFICE'],
    'BPG-CL-FA': ['BPG', 'CL/FA', 'BULLSEYE'],
    'Sports': ['SPORTS', 'OUTDOORS', 'SPORT', 'LUGG', 'AUTO'],
    'Seasonal': ['SEASONAL', 'HOLIDAY', 'GRILLING', 'SOIL', 'SEED', 'LAWN', 'G43'],
    'Tech': ['TECH', 'ELECTRONICS', '13 - ELEC', 'ENTERTAINMENT'],
    'Style': ['STYLE', 'APPAREL', 'FOLDING', 'INTIMATES', 'NIT', 'HANGING'],
    'Food': ['FOOD', 'GROCERY', 'WATER', 'PASTA', 'SPICES', 'BAKING', 'CEREAL', 'COFFEE', 'CANDY', 'COOKIES', 'CHIPS', 'BEVERAGE']
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
    return render_template("main_menu.html", uploaded_files_info=uploaded_files_info)

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

    # If it's a GET request, show the exclusion form
    if request.method == "GET":
        all_sections = sorted(all_data['Section'].unique())
        return render_template("exclude_sections.html", sections=all_sections)

    # If it's a POST request, exclude selected sections
    excluded_sections = request.form.getlist("sections")
    if excluded_sections:
        all_data = all_data[~all_data['Section'].isin(excluded_sections)]

    # Exclude Uncategorized rows
    all_data = all_data[all_data['Section'] != "Uncategorized"]

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

    # Add a Total row
    total_row = summary.sum(numeric_only=True).rename("Total")
    summary = pd.concat([summary, total_row.to_frame().T])

    # Round all numeric values to the nearest tenth
    summary = summary.round(1)

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
    global summary
    if summary is None:
        return "No data to generate chart", 404

    # Exclude the "Total" row
    chart_data = summary.loc[summary.index != "Total", "Workload %"]

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
    from flask import Response
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
    global all_data
    if all_data.empty:
        return redirect(url_for("main_menu"))

    # Get unique sections available in the data
    all_sections = all_data['Section'].unique() if 'Section' in all_data else []

    if request.method == "POST":
        # Get selected sections to exclude
        sections_to_exclude = request.form.getlist("sections")
        if sections_to_exclude:
            all_data.drop(all_data[all_data['Section'].isin(sections_to_exclude)].index, inplace=True)

        return redirect(url_for("process_data"))

    return render_template("exclude_sections.html", sections=all_sections)


if __name__ == "__main__":
    app.run(debug=True)
