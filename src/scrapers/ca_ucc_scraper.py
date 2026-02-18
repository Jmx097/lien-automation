#!/usr/bin/env python3
"""
California SOS UCC Lien Scraper - Base Module
Use ca_ucc_scraper_playwright.py for Playwright-based scraping
"""

# Re-export from playwright version for backward compatibility
from src.scrapers.ca_ucc_scraper_playwright import CAUCCScraper, LienRecord

__all__ = ['CAUCCScraper', 'LienRecord']
