import json
import time

# Load the cookies from the file you have
with open('../cookies/xhs_cookies_raw.json', 'r') as infile:
    raw_cookies = json.load(infile)

# Function to map sameSite values
def map_same_site(value):
    if value.lower() == 'no_restriction':
        return 'None'
    elif value.lower() == 'lax' or value.lower() == 'unspecified':
        return 'Lax'
    elif value.lower() == 'strict':
        return 'Strict'
    else:
        return 'Lax'  # Default to 'Lax' if unspecified

# Transform the cookies to Playwright's expected format
transformed_cookies = []

for cookie in raw_cookies:
    transformed_cookie = {
        'name': cookie['name'],
        'value': cookie['value'],
        'domain': cookie['domain'],
        'path': cookie['path'],
        'expires': int(cookie.get('expirationDate', 0)),
        'httpOnly': cookie['httpOnly'],
        'secure': cookie['secure'],
        'sameSite': map_same_site(cookie.get('sameSite', 'Lax')),
    }
    transformed_cookies.append(transformed_cookie)

# Create the storage state structure
storage_state = {
    'cookies': transformed_cookies,
    'origins': []
}

# Save the transformed cookies to a new file
with open('../cookies/xhs_cookies3.json', 'w') as outfile:
    json.dump(storage_state, outfile, indent=2)

print("Cookies have been converted and saved to xhs_cookies3.json")