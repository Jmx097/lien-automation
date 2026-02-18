from bs4 import BeautifulSoup
import os

temp_dir = os.environ.get('TEMP')
html_path = os.path.join(temp_dir, 'ca_sos_results.html')

if not os.path.exists(html_path):
    print(f"File not found: {html_path}")
    exit(1)

with open(html_path, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print("--- INPUTS ---")
for tag in soup.find_all('input'):
    print(f"Tag: {tag.name}, Type: {tag.get('type')}, ID: {tag.get('id')}, Name: {tag.get('name')}, Placeholder: {tag.get('placeholder')}, Value: {tag.get('value')}")

print("\n--- SELECTS ---")
for tag in soup.find_all('select'):
    print(f"Tag: {tag.name}, ID: {tag.get('id')}, Name: {tag.get('name')}, Label: {tag.get('aria-label')}")
    options = tag.find_all('option')
    print(f"  Options: {[opt.text.strip() for opt in options[:5]]}...")

print("\n--- BUTTONS ---")
for tag in soup.find_all('button'):
    print(f"Tag: {tag.name}, ID: {tag.get('id')}, Text: {tag.text.strip()[:30]}, Class: {tag.get('class')}")

print("\n--- LINKS (possible toggles) ---")
for tag in soup.find_all('a'):
    if 'advanced' in tag.text.lower() or 'filter' in tag.text.lower():
        print(f"Tag: {tag.name}, Text: {tag.text.strip()}, Href: {tag.get('href')}")
