import asyncio
from playwright.async_api import async_playwright

async def run_playwright_submission(url, profile_data, form_mappings):
    """
    Core automation wrapper using Playwright to fill a job application page.
    """
    print(f"Launching Playwright runner for: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        
        # Fill standard text elements
        for selector, value in form_mappings.items():
            try:
                await page.fill(selector, value)
            except Exception as e:
                print(f"Could not fill selector {selector}: {e}")
                
        # Handle file uploads
        resume_input = await page.query_selector("input[type='file']")
        if resume_input and "resume_path" in profile_data:
            await resume_input.set_input_files(profile_data["resume_path"])
            
        # Click submit button
        # await page.click("button[type='submit']")
        
        await browser.close()
        print("Playwright automation finished.")
