
import re
import sys

try:
    with open('panel_dump.html', 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
except FileNotFoundError:
    print("panel_dump.html not found.")
    sys.exit(1)

print("=== BUTTONS IN FIRST 20kb ===")
buttons = re.findall(r'<button[^>]*>.*?</button>', html[:20000], re.DOTALL | re.IGNORECASE)
for b in buttons[:10]:
    print(b)
    print("-" * 20)

print("\n=== ROWS WITH BUTTONS ===")
# Find table rows that contain buttons
rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL | re.IGNORECASE)
print(f"Total rows found: {len(rows)}")

if rows:
    first_data_row = None
    # Skip header row if possible
    for r in rows:
        if '<th' not in r:
            first_data_row = r
            break
            
    if first_data_row:
        print("First data row content (truncated):")
        print(first_data_row[:500] + "...")
        
        # Check for buttons within this row
        row_buttons = re.findall(r'<button[^>]*>.*?</button>', first_data_row, re.DOTALL | re.IGNORECASE)
        print(f"\nButtons in first data row: {len(row_buttons)}")
        for b in row_buttons:
            print(b)
    else:
        print("No data rows found.")
