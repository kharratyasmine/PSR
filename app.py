from collections import defaultdict
import os
from flask import Flask, redirect, render_template, request, jsonify, send_from_directory, send_file, url_for
from werkzeug.utils import secure_filename
import pandas as pd
import re
from datetime import datetime, timedelta
from hijri_converter import convert
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXPORT_FOLDER'] = 'exports'
app.config['HOLIDAYS_FILE'] = 'holidays.json'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

# Dictionnaire pour mapper les mois à leurs numéros correspondants
month_map = {
    'January': '01', 'Jan': '01', 'jan': '01',
    'February': '02', 'Feb': '02', 'feb': '02',
    'March': '03', 'Mar': '03', 'mar': '03',
    'April': '04', 'Apr': '04', 'apr': '04',
    'May': '05', 'may': '05',
    'June': '06', 'Jun': '06', 'jun': '06',
    'July': '07', 'Jul': '07', 'jul': '07',
    'August': '08', 'Aug': '08', 'aug': '08',
    'September': '09', 'Sep': '09', 'sep': '09',
    'October': '10', 'Oct': '10', 'oct': '10',
    'November': '11', 'Nov': '11', 'nov': '11',
    'December': '12', 'Dec': '12', 'dec': '12'
}

# Default fixed holidays
fixed_holidays = [
    {"name": "New Year's Day", "date": "01/01"},
    {"name": "Independence Day", "date": "20/03"},
    {"name": "Martyrs' Day", "date": "09/04"},
    {"name": "Labour Day", "date": "01/05"},
    {"name": "Republic Day", "date": "25/07"},
    {"name": "Women's Day", "date": "13/08"},
    {"name": "Evacuation Day", "date": "15/10"},
    {"name": "Revolution Day", "date": "17/12"},
]

# Function to get Islamic holidays
def calculate_islamic_holidays(year):
    holidays = []
    try:
        # Convert to Hijri year
        hijri_year = convert.Gregorian(year, 1, 1).to_hijri().year

        # Calculate Eid al-Fitr (1 Shawwal)
        eid_al_fitr = convert.Hijri(hijri_year, 10, 1).to_gregorian()
        holidays.append(("Eid al-Fitr", eid_al_fitr.strftime("%d/%m")))

        # Calculate Eid al-Adha (10 Dhu al-Hijjah)
        eid_al_adha = convert.Hijri(hijri_year, 12, 10).to_gregorian()
        holidays.append(("Eid al-Adha", eid_al_adha.strftime("%d/%m")))

        # Calculate Islamic New Year (1 Muharram)
        islamic_new_year = convert.Hijri(hijri_year, 1, 1).to_gregorian()
        holidays.append(("Islamic New Year", islamic_new_year.strftime("%d/%m")))

        # Calculate Ramadan start (1 Ramadan)
        ramadan_start = convert.Hijri(hijri_year, 9, 1).to_gregorian()
        holidays.append(("Ramadan Start", ramadan_start.strftime("%d/%m")))

        # Calculate Mawlid al-Nabi (12 Rabi' al-Awwal)
        mawlid = convert.Hijri(hijri_year, 3, 12).to_gregorian()
        holidays.append(("Mawlid al-Nabi", mawlid.strftime("%d/%m")))

    except Exception as e:
        print(f"Error calculating Islamic holidays: {e}")

    return holidays

def load_holidays():
    if os.path.exists(app.config['HOLIDAYS_FILE']):
        with open(app.config['HOLIDAYS_FILE'], 'r') as file:
            holidays = json.load(file)
    else:
        holidays = fixed_holidays + [{"name": name, "date": date} for name, date in calculate_islamic_holidays(datetime.now().year)]
    return holidays

# Save holidays to JSON file
def save_holidays(holidays):
    with open(app.config['HOLIDAYS_FILE'], 'w') as file:
        json.dump(holidays, file, indent=4)

public_holidays = load_holidays()

def format_date(day, month, year=None):
    if year is None:
        year = datetime.now().year
    try:
        return datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").strftime("%d/%m/%Y")
    except ValueError:
        return None

def determine_duration(text):
    if 'days' in text:
        return text.split('days')[0].strip()
    return "Unknown"

def validate_date(date):
    try:
        datetime.strptime(date, '%d/%m/%Y')
        return True
    except ValueError:
        return False

def date_range(start_date, end_date):
    start = datetime.strptime(start_date, '%d/%m/%Y')
    end = datetime.strptime(end_date, '%d/%m/%Y')
    step = timedelta(days=1)
    dates = []
    while start <= end:
        dates.append(start.strftime('%d/%m/%Y'))
        start += step
    return dates

def week_to_date_range(year, week_number):
    start_date = datetime.strptime(f'{year}-W{week_number}-1', "%Y-W%W-%w")
    end_date = start_date + timedelta(days=6)
    return start_date.strftime('%d/%m/%Y'), end_date.strftime('%d/%m/%Y')

patterns = [
    r'(\d+[.,]?\d*)\s*day(?:s)?\s*(?:off|holiday)?\s*\((\d{2}/\d{2}/\d{4})\)',  # Format: "2 days off (01/02/2024)"
    r'(\d+[.,]?\d*)\s*days?\s*holiday\s*\(\s*from\s*(\d{2}/\d{2}/\d{4})\s*to\s*(\d{2}/\d{2}/\d{4})\)',  # "3 days holiday (from 18/06/2024 to 20/06/2024)"
    r'(\d+[.,]?\d*)\s*days?:\s*(\d{2}/\d{2}/\d{4}(?:,\s*\d{2}/\d{2}/\d{4})*(?:\s*and\s*\d{2}/\d{2}/\d{4})?)',  # Format: "4 days: 04/07/2024, 05/07/2024, 22/07/2024 and 26/07/2024"
    r'(\w+)\s+off\s+(sick\s+)?for\s+(\d+)\s+days\s+\((\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})\)',  # e.g., "RES off for 3 days (03/07/2024 to 05/07/2024)" et #"AMD off sick for 3 days (03/01/2024 to 05/01/2024)"
    r'(\d{2}/\d{2})\s*(afternoon|public holiday|Afternoon)?',  # 06/06 afternoon
    r'(\d{2}/\d{2})\s*(Public Holiday|Day OFF|afternoon)?',  # e.g., "09/04 Public Holiday"
    r'(\d{2}/\d{2})(?:,| and )?(\d{2}/\d{2})?(?:,| and )?(\d{2}/\d{2})?\s*(Public Holidays|Public Holiday|Day OFF|afternoon)?',
    r'(\d+)\s*days?\s*off\s*:\s*((?:\d{2}-\d{2}-\d{4})\s*/\s*(?:\d{2}-\d{2}-\d{4}))',  # "02 days off : 20-06-2024 / 21-06-2024"
    r'(\d+[.,]?\d*)\s*d:\s*(\d{2}/\d{2}/\d{4})',  # Format: "1.5 d: 01/02/2024"
    r'(\d+(\.\d+)?)\s*MD:\s*(\d{2}/\d{2}/\d{4})',  # Format: "0.5 MD: 12/02/2024"
    r'(\d{2}/\d{2}/\d{4})\s*Afternoon',  # Format: "01/02/2024 Afternoon"
    r'(\d+):(\d{2}-\d{2}-\d{4})(?:->(\d{2}-\d{2}-\d{4}))?',  # e.g., "01:17-06-2024"
    r'(\d+)\s*days?\s*off\s*:\s*((\d{2}-\d{2}-\d{4})\s*/\s*(\d{2}-\d{2}-\d{4}))',  # New pattern
    r'(\d+)\s*days?\s*off\s*:\s*(\w+\s+\d{1,2}(?:,\s*\d{1,2})*\s*,\s*\d{4})',  # e.g., "02 days off : June 20 and 21, 2024"
    r'(\d{1,2}(?:th|st|nd|rd)\s+of\s+\w+)',  # Format: "23rd of February"
    r'(\d{1,2}(?:th|st|nd|rd)\s+of\s+\w+)\s*\((\w+)\)',  # e.g., "0,5 day of 23rd of February (Uplanned leave)"
    r'(\d{2}/\d{2}/\d{4})',  # Format: "01/02/2024"
    r'(\w+)\s*off\s*during\s*week\s*(\d+)',  # CKA off during week 27
    r'(\d{1,2})\s+(\w+)\s*(?:\((Half day off|Sick Day|Day off)\))?',  # e.g., "01 January", "10 January (Day off)"
    r'(\w+)\s*:\s*((?:\d{1,2}(?:\(\d{1,2}[.,]?\d*d\))?(?:,\s*)?)+)',
  
]

current_year = datetime.now().year
def is_holiday(date_str):
    for holiday in public_holidays:
        if date_str == holiday["date"]:
            return True
    return False

def extract_durations_and_dates(text, name):
    results = []
 
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches: 
            if isinstance(match, tuple):
                if len(match) == 2 and pattern == patterns[0]:
                    duration_text, date = match
                    duration_text = duration_text.replace(',', '.')
                    duration = float(duration_text) if '.' in duration_text else int(duration_text)
                    if not is_holiday(date):
                        results.append((name, duration, date))   
                elif len(match) == 3 and pattern == patterns[1]:
                    duration_text, start_date, end_date = match
                    duration_text = duration_text.replace(',', '.')
                    duration = float(duration_text) if '.' in duration_text else int(duration_text)
                    date_list = date_range(start_date, end_date)
                    for date in date_list:
                        if not is_holiday(date):
                            results.append((name, duration / len(date_list), date))
                elif len(match) == 2 and pattern == patterns[2]:
                    duration_text, dates = match
                    date_list = re.findall(r'\d{2}/\d{2}/\d{4}', dates)
                    duration = float(duration_text.replace(',', '.'))
                    for date in date_list:
                        if not is_holiday(date):
                            results.append((name, duration / len(date_list), date))     
                elif len(match) == 5 and pattern == patterns[3]:
                    Aname = match[0]
                    duration_text = match[2]
                    start_date = match[3]
                    end_date = match[4]
                    duration = int(duration_text)
                    start_date_formatted = datetime.strptime(start_date, '%d/%m/%Y').strftime('%d/%m/%Y')
                    end_date_formatted = datetime.strptime(end_date, '%d/%m/%Y').strftime('%d/%m/%Y')
                    date_list = date_range(start_date_formatted, end_date_formatted)
                    for date in date_list:
                        if not is_holiday(date):
                            results.append((name, duration / len(date_list), date))              
                elif 'AFTERNOON' in text.upper() and len(matches) == 1:
                    date = match[0]
                    duration = 0.5
                    if len(date.split('/')) == 2:
                        date += f'/{current_year}'
                    formatted_date = datetime.strptime(date, '%d/%m/%Y').strftime('%d/%m/%Y')
                    results.append((name, duration, formatted_date))
                elif isinstance(match, tuple) and len(match) == 1:
                    date = match[0]
                    if ('AFTERNOON' in text.upper()) or ('aFTERNOON' in text.upper()):
                        duration = 0.5
                    else:
                        duration = 1  # Default to 1 day if no specific duration mentioned
                    if len(date.split('/')) == 2:
                        date += f'/{current_year}'
                    formatted_date = datetime.strptime(date, '%d/%m/%Y').strftime('%d/%m/%Y')
                    results.append((name, duration, formatted_date))                   
                elif len(match) == 2 and pattern == patterns[4] :
                    day_month, day_type = match
                    day, month = day_month.split('/')
                    date_formatted = f"{day.zfill(2)}/{month.zfill(2)}/{current_year}"
                    duration = 1 if not day_type or day_type.lower() == "public holiday" else 0.5
                    if not is_holiday(date_formatted):
                        results.append((name, duration, date_formatted))

                elif len(match) == 3 and pattern == patterns[6]:
                    day_month_1, day_month_2, day_month_3, day_type = match
                    day_month_list = [day_month_1, day_month_2, day_month_3]
                    for day_month in day_month_list:
                        if day_month:
                            day, month = day_month.split('/')
                            date_formatted = f"{day.zfill(2)}/{month.zfill(2)}/{current_year}"
                            duration = 1 if not day_type or day_type.lower() == "public holiday" else 0.5
                            if not is_holiday(date_formatted):
                                results.append((name, duration, date_formatted))

                elif len(match) == 2 and pattern == patterns[7]:
                    duration_text, date_str = match
                    date_list = re.findall(r'\d{2}-\d{2}-\d{4}', date_str)
                    duration = 1
                    for date in date_list:
                        formatted_date = datetime.strptime(date, '%d-%m-%Y').strftime('%d/%m/%Y')
                        if not is_holiday(formatted_date):
                            results.append((name, duration, formatted_date))

                elif len(match) == 2 and pattern == patterns[9]:  # Assurez-vous que ce pattern correspond à "0.5 MD: ..."
                    # Gérer le format spécifique "0.5 MD: 12/02/2024"
                    duration_text, _, date = match
                    duration_text = duration_text.replace(',', '.')
                    duration = float(duration_text) if '.' in duration_text else int(duration_text)
                    formatted_date = datetime.strptime(date, '%d/%m/%Y').strftime('%d/%m/%Y')
                    results.append((name, duration, formatted_date))
            
            
                elif len(match) >= 2 and pattern == patterns[11]:
                    duration_text = match[0]
                    start_date = match[1]
                    end_date = match[2] if len(match) > 2 and match[2] else start_date
                    duration = 1
                    formatted_start_date = datetime.strptime(start_date, '%d-%m-%Y').strftime('%d/%m/%Y')
                    formatted_end_date = datetime.strptime(end_date, '%d-%m-%Y').strftime('%d/%m/%Y')
                    if not is_holiday(formatted_start_date):
                        if formatted_start_date == formatted_end_date:
                            results.append((name, duration, formatted_start_date))
                        else:
                            date_range_list = date_range(formatted_start_date, formatted_end_date)
                            for date in date_range_list:
                                results.append((name, duration, date))  
                      
                elif len(match) == 2 and pattern == patterns[17]:
                    person = match[0]
                    week = int(match[1])
                    for i in range(0, 7):
                        date = (datetime.strptime(f'{current_year}-W{week-1}-1', "%Y-W%W-%w") + timedelta(days=i)).strftime('%d/%m/%Y')
                        if not is_holiday(date):
                            results.append((name, 1.0, date)) 

                elif len(match) >= 2 and pattern == patterns[18]:
                    day, month = match[:2]
                    day_type = match[2] if len(match) > 2 else None
                    if month in month_map:
                        date = f"{day.zfill(2)}/{month_map[month]}/{current_year}"
                        duration = 1  # Default duration for full days
                        if day_type == "Half day off":
                            duration = 0.5
                        if not is_holiday(date):
                            results.append((name, duration, date))
                    else:
                        print(f"Error: Month '{month}' not recognized.")  

                elif len(match) == 2 and pattern == patterns[19]:
                    month_name, dates = match
                    normalized_month_name = month_name.capitalize()  # Normalize the month name
                    if normalized_month_name in month_map:
                        month = month_map[normalized_month_name]
                        date_list = re.findall(r'(\d{1,2})(?:\((\d{1,2}[.,]?\d*)d\))?', dates)
                        for day, duration in date_list:
                            day = day.zfill(2)
                            duration = float(duration.replace(',', '.')) if duration else 1.0
                            date_with_year = f"{day}/{month}/{current_year}"
                            if not is_holiday(date_with_year):
                                results.append((name, duration, date_with_year))
                    else:
                        print(f"Error: Month '{month_name}' not recognized.")  
            elif isinstance(match, str):    
                if re.match(r'\d{1,2}(?:th|st|nd|rd)\s+of\s+\w+', match):
                    day, month = match.split(' of ')
                    month = datetime.strptime(month, '%B').month
                    day = int(day[:-2])
                    date = f"{day:02d}/{month:02d}/{current_year}"
                    if ("0.5" in text) or ("0,5" in text): 
                        duration = 0.5  # Default to 0.5 day for "Unplanned leave"
                    else:
                        duration = 1
                    results.append((name, duration, date))
        if matches: 
            break
    return results 
def calculer_charge_effective_par_initial(df, new_column_name='effective workload'):

    result = df.groupby('Initial')['Duration'].sum().reset_index()
    result.columns = ['Initial', new_column_name]
    return df.merge(result, on='Initial', how='left')

def process_texts(df):
    holidays = []
    for index, row in df.iterrows():
        name = row['Initial']
        if str(row['Holiday']) != "NaN":
            holiday_texts = str(row['Holiday']).split('\n')
            for text in holiday_texts:
                holidays.extend(extract_durations_and_dates(text, name))
    return holidays
# Function to retrieve uploaded files list
def get_file_list():
    uploads_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(uploads_folder):
        return []
    files = os.listdir(uploads_folder)
    file_info = [{'filename': f, 'uploaded_at': datetime.fromtimestamp(os.path.getmtime(os.path.join(uploads_folder, f)))} for f in files]
    return sorted(file_info, key=lambda x: x['uploaded_at'], reverse=True)

# Function to retrieve sorted exported files
def get_sorted_files():
    exports_folder = app.config['EXPORT_FOLDER']
    if not os.path.exists(exports_folder):
        return []
    files = os.listdir(exports_folder)
    file_info = [{'filename': f, 'created_at': datetime.fromtimestamp(os.path.getmtime(os.path.join(exports_folder, f)))} for f in files]
    return sorted(file_info, key=lambda x: x['created_at'], reverse=True)

@app.route('/add_public_holiday', methods=['POST'])
def add_public_holiday():
    data = request.get_json()
    holiday_name = data.get('name')
    holiday_date = data.get('date')
    
    if holiday_name and holiday_date:
        # Assuming holiday_date is in "dd/mm" format
        try:
            # Extract day and month from the input date
            day, month = holiday_date.split('/')
            # Format the date with the current year
            formatted_date = format_date(day, month)
            if formatted_date:
                # Check for duplicates in the public_holidays list
                if any(h for h in public_holidays if h['name'] == holiday_name or h['date'] == formatted_date):
                    return jsonify({"error": "Holiday with this name or date already exists"}), 400
                
                # Add the new holiday
                public_holidays.append({"name": holiday_name, "date": formatted_date})
                save_holidays(public_holidays)
                return jsonify({"message": "Holiday added successfully"}), 200
            else:
                return jsonify({"error": "Invalid date format"}), 400
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
    return jsonify({"error": "Missing holiday name or date"}), 400

@app.route('/delete_public_holiday', methods=['DELETE'])
def delete_public_holiday():
    data = request.get_json()
    holiday_date = data.get('date')
    holiday_name = data.get('name')
    
    if holiday_name and holiday_date:
        # Remove the holiday from the public_holidays list
        global public_holidays
        public_holidays = [h for h in public_holidays if not (h['name'] == holiday_name and h['date'] == holiday_date)]
        save_holidays(public_holidays)
        return jsonify({"message": "Holiday deleted successfully"}), 200
    
    return jsonify({"error": "Missing holiday name or date"}), 400


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route to upload files
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    files = request.files.getlist('files')
    processed_files_path = 'processed_files.json'
    try:
        with open(processed_files_path, 'r') as f:
            processed_files = json.load(f)
    except FileNotFoundError:
        processed_files = []
    if not files:
        return jsonify({'error': 'No selected files'}), 400
    uploaded_files_info = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        
        if filename in processed_files:
                return jsonify({'message': 'File already processed'}), 400
            
        file_info = {
            'filename': filename,
            'uploaded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        uploaded_files_info.append(file_info)
    
    return jsonify({'message': 'Files uploaded successfully', 'files': uploaded_files_info})

@app.route('/delete_file/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        # Path to the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Remove file from server if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            return jsonify({"error": "File not found"}), 404
        
        # Path to the processed files JSON
        processed_files_path = 'processed_files.json'
        
        # Read the list of processed files
        try:
            with open(processed_files_path, 'r') as f:
                processed_files = json.load(f)
        except FileNotFoundError:
            processed_files = []
        
        # Remove the filename from the list if it exists
        if filename in processed_files:
            processed_files.remove(filename)
            with open(processed_files_path, 'w') as f:
                json.dump(processed_files, f)
        
        return jsonify({"message": "File deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_export/<filename>', methods=['DELETE'])
def delete_export(filename):
    try:
        # Path to the file
        file_path = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        # Remove file from server if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            return jsonify({"error": "File not found"}), 404
        
        return jsonify({"message": "File deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Function to group dates by week and format the output
def group_dates_by_week(dates_and_durations):
    grouped_data = defaultdict(lambda: defaultdict(list))

    for initial, duration, date in dates_and_durations:
        date_obj = datetime.strptime(date, '%d/%m/%Y')
        year, week_num, _ = date_obj.isocalendar()
        grouped_data[initial][week_num].append((date, duration))

    formatted_output = []

    for initial, weeks in grouped_data.items():
        week_strings = []
        total_workload = 0
        all_dates = []
        all_durations = []
        
        for week_num, data in sorted(weeks.items()):
            dates = [d[0] for d in data]
            total_duration = sum(d[1] for d in data)
            dates_str = ", ".join(dates[:-1]) + ", and " + dates[-1] if len(dates) > 1 else dates[0]
            week_strings.append(f"{total_duration} MD ({dates_str})")
            total_workload += total_duration
            all_dates.extend(dates)
            all_durations.extend([d[1] for d in data])
        
        details_str = ", and ".join(week_strings)
        formatted_output.append([initial, details_str, total_workload, ", ".join(all_dates), ", ".join(map(str, all_durations))])
    
    return formatted_output


@app.route('/export', methods=['GET'])
def export_data():
    uploads_folder = app.config['UPLOAD_FOLDER']
    all_holidays = []
    processed_files_path = 'processed_files.json'
    
    # Load the list of processed files
    try:
        with open(processed_files_path, 'r') as f:
            processed_files = json.load(f)
    except FileNotFoundError:
        processed_files = []

    # Track newly processed files
    newly_processed_files = []
    
    # Load and process data from all uploaded files
    for filename in os.listdir(uploads_folder):
        if filename.endswith('.xlsx') and filename not in processed_files:
            file_path = os.path.join(uploads_folder, filename)
            data = pd.read_excel(file_path, skiprows=3)
            holidays = process_texts(data)
            all_holidays.extend(holidays)
            newly_processed_files.append(filename)

    # Update the list of processed files
    processed_files.extend(newly_processed_files)
    with open(processed_files_path, 'w') as f:
        json.dump(processed_files, f)

    # Filter out public holidays
    # Ensure public_holidays contains only strings
    public_holidays_set = set()
    for holiday in public_holidays:
        if isinstance(holiday, dict):
            public_holidays_set.update(holiday.values())
        elif isinstance(holiday, str):
            public_holidays_set.add(holiday)
    
    # Function to check if a date is a public holiday
    def is_public_holiday(date):
        if not isinstance(date, str):
            return False
        return any(date.startswith(ph) for ph in public_holidays_set)
    
    filtered_holidays = [holiday for holiday in all_holidays 
                         if isinstance(holiday, tuple) 
                         and len(holiday) == 3 
                         and not is_public_holiday(holiday[2])]

    # Group dates by week and sum durations within each week
    formatted_output = group_dates_by_week(filtered_holidays)

    # Create DataFrame
    df = pd.DataFrame(formatted_output, columns=['Initial', 'Details', 'Effective Workload', 'Dates', 'Durations'])
    
    # Save to Excel file
    output_file = os.path.join(app.config['EXPORT_FOLDER'], f"holidays_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    df.to_excel(output_file, index=False)

    # Return JSON response
    return jsonify({
        'exported_file': os.path.basename(output_file),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })




def combine_by_initials(df):
    # Convert all values in 'Date' and 'Duration' columns to string
    df['Date'] = df['Date'].astype(str)
    df['Duration'] = df['Duration'].astype(str)
    df['Details'] = df['Details'].astype(str)
    
    # Combine rows by initials
    combined_df = df.groupby('Initial').agg({
        'Date': lambda x: ', '.join(x),
        'Duration': lambda x: ', '.join(x),
        'Details': lambda x: ', '.join(x)
    }).reset_index()
    
    return combined_df




@app.route('/exported/<filename>')
def exported_file(filename):
    return send_from_directory(app.config['EXPORT_FOLDER'], filename)


# Route to download exporteded files
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(app.config['EXPORT_FOLDER'], filename, as_attachment=True)

# Route to download exporteded files
@app.route('/downloadupload/<filename>', methods=['GET'])
def download_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# Route to render index.html with uploaded files and extracted holidays
@app.route('/')
def index():
    return render_template('index.html', files=get_file_list(), exported_files=get_sorted_files(), fixed_holidays=fixed_holidays, islamic_holidays=calculate_islamic_holidays(datetime.now().year), public_holidays=public_holidays)

if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['EXPORT_FOLDER']):  # Fixed typo here
        os.makedirs(app.config['EXPORT_FOLDER'])
    app.run(debug=True)