# google_sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_video_subjects(sheet_id, range_name):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(range_name)
    data = sheet.get_all_records()  # Assuming each row contains one subject and other necessary data
    return data
