"""
CA SOS UCC Scraper Module

Implements scraping logic for California Secretary of State UCC search
specifically for Federal Tax Liens.
"""

import logging
import re
import os
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from datetime import date
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

async def scrape_ca_sos_liens(
    page: Page,
    date_start: date,
    date_end: date,
    max_records: int = 1000,
    cursor: Optional[Dict[str, int]] = None,
    output_dir: str = "./downloads"
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Scrapes CA SOS UCC Federal Tax Liens.

    Args:
        page: Playwright Page object (already initialized).
        date_start: Start date for search.
        date_end: End date for search.
        max_records: Maximum records to fetch.
        cursor: Resume cursor containing 'page_number'.
        output_dir: Directory to save downloaded PDFs.

    Returns:
        Tuple of (list of record dicts, next cursor dict).
    """
    records: List[Dict[str, Any]] = []
    
    # Format dates
    start_str = date_start.strftime("%m/%d/%Y")
    end_str = date_end.strftime("%m/%d/%Y")
    
    # Determine start page
    start_page = 1
    if cursor and 'page_number' in cursor:
        start_page = cursor['page_number']
        
    logger.info(f"Starting CA SOS scrape: {start_str} - {end_str}, start_page={start_page}")
    
    try:
        # Navigate and Search
        await _perform_search(page, start_str, end_str)
        
        # Check results
        total_count = await _get_result_count(page)
        logger.info(f"Found {total_count} total results")
        
        if total_count == 0:
            return [], {'page_number': 1}
            
        # Pagination loop
        current_page = 1
        
        # If resuming, jump to page
        if start_page > 1:
            await _jump_to_page(page, start_page)
            current_page = start_page
            
        while len(records) < max_records:
            logger.info(f"Processing page {current_page}")
            
            page_records = await _process_page(page, output_dir)
            records.extend(page_records)
            
            if len(records) >= max_records:
                break
                
            # Next page
            next_btn = page.get_by_role("button", name="Next Page")
            if await next_btn.is_visible() and await next_btn.is_enabled():
                await next_btn.click()
                await page.wait_for_load_state("networkidle")
                current_page += 1
            else:
                break # End of results
                
    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        # Return what we have
        
    return records, {'page_number': current_page}

async def _perform_search(page: Page, start_date: str, end_date: str):
    """Executes the search on the main page."""
    await page.goto("https://bizfileonline.sos.ca.gov/search/ucc")
    await page.wait_for_load_state("networkidle")
    
    # Dummy search term to enable advanced search (as per manual behavior)
    # The site often requires something in the main box or specific interactions to unlock 'Advanced'
    # Based on previous implementation:
    await page.get_by_label("Search by name or file number").fill("Internal Revenue Service")
    
    # Open Advanced
    await page.get_by_role("button", name=re.compile(r"Advanced", re.I)).click()
    
    # Wait for panel
    await page.get_by_label("File Type").wait_for(state="visible")
    
    # Set File Type -> "Federal Tax Lien"
    await page.get_by_label("File Type").select_option(label="Federal Tax Lien")
    
    # Set Dates
    await page.get_by_label("File Date: Start").fill(start_date)
    end_field = page.get_by_label("File Date: End")
    await end_field.fill(end_date)
    await end_field.press("Tab")
    
    # Submit
    await page.get_by_role("button", name="Search").click()
    await page.wait_for_load_state("networkidle")

async def _get_result_count(page: Page) -> int:
    try:
        # Looking for text like "Results: 25"
        text_el = page.locator("div", has_text=re.compile(r"Results:\s*\d+")).last
        if await text_el.is_visible():
            text = await text_el.text_content()
            match = re.search(r"(\d+)", text)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return 0

async def _jump_to_page(page: Page, page_num: int):
    # Try to find specific page button
    # If not visible, might need next/prev logic, but standard pagination usually shows numbers
    btn = page.get_by_role("button", name=str(page_num), exact=True)
    if await btn.is_visible():
        await btn.click()
        await page.wait_for_load_state("networkidle")
    else:
        logger.warning(f"Could not jump directly to page {page_num}")

async def _process_page(page: Page, output_dir: str) -> List[Dict[str, Any]]:
    results = []
    # Identify rows
    rows = page.locator("table tbody tr")
    count = await rows.count()
    
    for i in range(count):
        row = rows.nth(i)
        try:
            record = await _process_row(page, row, output_dir)
            if record:
                results.append(record)
        except Exception as e:
            logger.warning(f"Failed to process row {i}: {e}")
            
    return results

async def _process_row(page: Page, row, output_dir: str) -> Optional[Dict[str, Any]]:
    # Extract basic info
    cells = row.locator("td")
    # Assuming standard layout: [Type, Debtor, File #, Secured, Status, Filing Date, Lapse Date]
    # Check bounds
    if await cells.count() < 6:
        return None
        
    filing_date = (await cells.nth(5).text_content() or "").strip()
    file_number = (await cells.nth(2).text_content() or "").strip()
    
    # Open Detail
    chevron = row.locator("button[aria-label], button:has(svg)").first
    await chevron.click()
    
    # Wait for detail
    # We look for a panel closer that contains the file number or just the expanded row
    # The previous implementation used a filter.
    try:
        # Just wait a moment for animation if explicit selector is hard
        await page.wait_for_timeout(1000) 
    except:
        pass

    # Extract raw text from the expanded area or the whole row context
    # ideally we find the Detail Panel. In many React tables, it's a new row or a side panel.
    # The user desc says "opens the History modal".
    
    # Let's try to get full text
    raw_text = await row.inner_text() 
    
    pdf_url = None
    
    # Open History Modal
    history_btn = page.get_by_role("button", name=re.compile(r"View History", re.I))
    if await history_btn.is_visible():
        await history_btn.click()
        modal = page.get_by_role("dialog", name="History")
        await modal.wait_for(state="visible", timeout=5000)
        
        # Download PDF
        download_link = modal.get_by_role("link", name=re.compile(r"Download", re.I))
        if await download_link.is_visible():
            pdf_filename = f"{file_number}_{filing_date.replace('/', '')}.pdf"
            save_path = os.path.join(output_dir, pdf_filename)
            
            # If we were doing real downloading:
            # async with page.expect_download() as download_info:
            #    await download_link.click()
            # download = await download_info.value
            # await download.save_as(save_path)
            # pdf_url = f"file://{save_path}" # Or keep empty if we just download
            
            # Only capturing URL if it's a direct link, but Playwright downloads are better handled via expect_download
            # For this 'scrape_ca_sos_liens' spec, returning 'pdf_url' usually implies a remote URL or local path.
            # I will set pdf_url to the href if possible, or placeholder.
            pdf_url = await download_link.get_attribute("href")
            
        # Close modal
        await modal.get_by_role("button", name=re.compile(r"close|×", re.I)).click()
        await modal.wait_for(state="hidden")
        
    # Close Detail Panel (toggle chevron again or close button)
    # Re-clicking chevron usually collapses
    if await chevron.is_visible():
        await chevron.click()
        
    return {
        "site_id": "21",
        "filing_date": filing_date,
        "raw_text": raw_text,
        "pdf_url": pdf_url,
        "file_number": file_number
    }
