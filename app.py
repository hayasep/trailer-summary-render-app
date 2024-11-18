from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import re

app = Flask(__name__)

# Define automated mappings based on keywords or patterns
automated_mapping = {
    'Pets': ['PETS', 'DOG', 'CAT', 'LITTER'],
    'Toys': ['TOY', 'LEGOS', 'BOYS ACTION', 'E42'],
    'Chemical/Paper': ['CHEMICAL', 'PAPER', 'BLEACH', 'LAUNDRY', 'HOUSEHOLD', 'AIR FRESHENER'],
    'HBA': ['HBA', 'BEAUTY', 'HEALTH', 'COSMETICS', 'SOAP', 'HAIR', 'OTC', 'ORAL', 'FEMININE'],
    'Infants': ['INFANT', 'BABY', 'NURSING', 'DIAPERS'],
    'C/D': ['C/D', 'BED', 'BATH', 'RUGS', 'LAMP', 'KITCHEN PLUG', 'APPLIANCE', 'PILLOWS', 'FURNITURE', 'STORAGE', 'PLASTIC', 'VACUUM', 'VIGNETTE', 'HEARTH'],
    'Kitchen': ['KITCHEN'],
    'Stationery': ['STATIONERY', 'OFFICE'],
    'BPG/CL/FA': ['BPG', 'CL/FA', 'BULLSEYE'],
    'Sports': ['SPORTS', 'OUTDOORS', 'SPORT', 'LUGG', 'AUTO'],
    'Seasonal': ['SEASONAL', 'HOLIDAY', 'GRILLING', 'SOIL', 'SEED', 'LAWN', 'G43'],
    'Tech': ['TECH', 'ELECTRONICS', '13 - ELEC', 'ENTERTAINMENT'],
    'Style': ['STYLE', 'APPAREL', 'FOLDING', 'INTIMATES', 'NIT', 'HANGING'],
    'Food': ['FOOD', 'GROCERY', 'WATER', 'PASTA', 'SPICES', 'BAKING', 'CEREAL', 'COFFEE', 'CANDY', 'COOKIES', 'CHIPS', 'BEVERAGE']
}

# Initialize global variables
all_data = pd.DataFrame()
summary = None
trailer_names = []

def extract_trailer_name(data):
    """Extract trailer names from a dataframe."""
    trailer_name = None
    for col in data.columns:
        for cell in data[col]:
            if isinstance(cell, str) and re.search(r'Trailer\s?#\S+', cell):
                match = re.search(r'Trailer\s?#\S+', cell)
                if match:
                    return match.group(0)
    return trailer_name

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
    """Main menu page."""
    return render_template("menu.html")

@app.route("/upload", methods=["GET", "POST"])
def upload_files():
    """Upload files and extract trailer names."""
    global all_data, trailer_names
    if request.method == "POST":
        uploaded_files = request.files.getlist("files")
        for file in uploaded_files:
            if file.filename.endswith(".csv"):
                temp_df = pd.read_csv(file)
            elif file.filename.endswith(".xlsx"):
                temp_df = pd.read_excel(file, engine="openpyxl")
            else:
                continue

            trailer_name = extract_trailer_name(temp_df)
            if trailer_name:
                trailer_names.append(trailer_name)

            all_data = pd.concat([all_data, temp_df], ignore_index=True)

        return redirect(url_for("process_data"))
    return render_template("upload.html")

@app.route("/process", methods=["GET", "POST"])
def process_data():
    """Process data, allow section exclusions, and summarize the data."""
    global all_data, summary
    if all_data.empty:
        return "No data uploaded. Please go back and upload files."

    if request.method == "POST":
        excluded_sections = request.form.getlist("exclude_sections")
        all_data["Section"] = all_data["CUSTOM BLOCK"].apply(map_to_section)

        if excluded_sections:
            all_data = all_data[~all_data["Section"].isin(excluded_sections)]
        all_data = all_data[all_data["Section"] != "Uncategorized"]

        numeric_columns = ["FULL CASE CARTONS", "REPACK CARTONS", "STOCKING TIME (HRS)"]
        for col in numeric_columns:
            all_data[col] = pd.to_numeric(all_data[col], errors="coerce").fillna(0)

        summary = all_data.groupby("Section")[numeric_columns].sum()
        total_row = summary.sum(numeric_only=True).rename("Total")
        summary = pd.concat([summary, total_row.to_frame().T])

        total_stocking_time = summary.loc["Total", "STOCKING TIME (HRS)"]
        summary["Workload %"] = (summary["STOCKING TIME (HRS)"] / total_stocking_time * 100).round(2) if total_stocking_time > 0 else 0

        return redirect(url_for("summary_view"))

    sections = automated_mapping.keys()
    return render_template("process.html", sections=sections)

@app.route("/summary")
def summary_view():
    """Display the summary and workload pie chart."""
    global summary, trailer_names
    if summary is None:
        return "No summary available. Please process data first."

    workload_data = summary.loc[summary.index != "Total", "Workload %"]
    img = None
    if not workload_data.empty:
        plt.figure(figsize=(8, 8))
        plt.pie(
            workload_data,
            labels=workload_data.index,
            autopct="%1.1f%%",
            startangle=140,
            wedgeprops={"edgecolor": "black"}
        )
        plt.title(f"Workload Distribution by Section\n{', '.join(trailer_names)}")
        img = io.BytesIO()
        plt.savefig(img, format="png")
        img.seek(0)
        img = base64.b64encode(img.getvalue()).decode()

    return render_template("summary.html", tables=summary.to_html(classes="table"), img=img)

@app.route("/mappings")
def view_mapping():
    """View mappings of custom blocks to sections."""
    global all_data
    if all_data.empty or 'Section' not in all_data.columns:
        return "No mappings available. Please upload and process data first."

    mappings_html = all_data[['CUSTOM BLOCK', 'Section']].to_html(classes="table")
    return render_template("mappings.html", mappings=mappings_html)

if __name__ == "__main__":
    app.run(debug=True)
