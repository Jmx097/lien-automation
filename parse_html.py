from bs4 import BeautifulSoup
import os

temp_dir = os.environ.get('TEMP')
html_path = os.path.join(temp_dir, 'ca_sos_results.html')

if not os.path.exists(html_path):
    print(f"File not found: {html_path}")
    exit(1)

with open(html_path, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print(f"Page Title: {soup.title.string if soup.title else 'No Title'}")

tables = soup.find_all('table')
print(f"Tables found: {len(tables)}")

for i, table in enumerate(tables):
    rows = table.find_all('tr')
    print(f"Table {i} rows: {len(rows)}")
    if len(rows) > 0:
        headers = [th.text.strip() for th in rows[0].find_all('th')]
        print(f"Headers: {headers}")

# Check for pagination
page_links = soup.find_all('a', class_='page-link') # Common class, might vary
print(f"Pagination links found: {len(page_links)}")
for link in page_links:
    print(f"Link: {link.text.strip()}, Href: {link.get('href')}")

# Check for "No results" message
if "no records found" in soup.text.lower() or "0 result" in soup.text.lower():
    print("Likely NO RESULTS found.")
