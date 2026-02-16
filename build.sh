#!/bin/bash
# Build script for Cloud Functions with Playwright

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
