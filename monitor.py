import asyncio
import os
import hashlib
import schedule
import time
import platform
from datetime import datetime
from playwright.async_api import async_playwright
from lxml import html
import csv
import threading
import pandas as pd
import difflib

class ContentMonitor:
    def __init__(self, csv_file='urls.csv', cache_dir='.cache', max_concurrent=5, max_retries=2, timeout=10000, monitoring_interval=1, check_interval=1):
        # Set proper event loop policy for Windows subprocess support (needed for Playwright)
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        self.csv_file = csv_file
        self.cache_dir = cache_dir
        self.urls_data = []
        self.max_concurrent = max_concurrent  # Maximum concurrent URL extractions
        self.max_retries = max_retries  # Maximum retries for failed requests
        self.timeout = timeout  # Timeout in milliseconds for page loading
        self.monitoring_interval = monitoring_interval  # Monitoring interval in minutes
        self.check_interval = check_interval  # Check interval in seconds for the monitoring loop
        self.ensure_cache_dir()
        self.is_monitoring = False
        self.monitor_thread = None

    def ensure_cache_dir(self):
        """Ensure cache directory exists"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def load_urls_from_csv(self):
        """Load URLs and XPath selectors from CSV file"""
        try:
            self.urls_data = []
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                for row in reader:
                    if len(row) >= 3 and row[1].strip() and row[2].strip():  # Ensure we have at least 3 columns and both URL and XPath are not empty
                        short_name = row[0].strip()
                        url = row[1].strip()
                        xpath = row[2].strip()
                        self.urls_data.append({
                            'short_name': short_name,
                            'url': url,
                            'xpath': xpath
                        })
            print(f"Loaded {len(self.urls_data)} URLs from {self.csv_file}")
        except Exception as e:
            print(f"Error loading CSV file: {e}")

    def save_urls_to_csv(self):
        """Save current urls_data to CSV file"""
        try:
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                for url_data in self.urls_data:
                    writer.writerow([
                        url_data['short_name'],
                        url_data['url'],
                        url_data['xpath']
                    ])
            print(f"Saved {len(self.urls_data)} URLs to {self.csv_file}")
        except Exception as e:
            print(f"Error saving CSV file: {e}")

    def get_urls_as_dataframe(self):
        """Get URLs data as pandas DataFrame for Streamlit"""
        return pd.DataFrame(self.urls_data)

    def update_urls_from_dataframe(self, df):
        """Update urls_data from pandas DataFrame"""
        self.urls_data = []
        for _, row in df.iterrows():
            short_name = str(row.get('short_name', '')).strip()
            url = str(row.get('url', '')).strip()
            xpath = str(row.get('xpath', '')).strip()
            # Only add rows that have both URL and XPath
            if url and xpath:
                self.urls_data.append({
                    'short_name': short_name,
                    'url': url,
                    'xpath': xpath
                })
        self.save_urls_to_csv()

    def get_cache_file_path(self, short_name):
        """Get cache file path for a given short name"""
        return os.path.join(self.cache_dir, f"{short_name}.cache")

    def get_content_hash(self, content):
        """Get hash of content for comparison"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def is_cloudflare_blocked(self, content):
        """Check if content indicates Cloudflare blocking"""
        if not content:
            return False
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in [
            'cloudflare',
            'attention required',
            'you have been blocked',
            'security service to protect itself',
            'cf-browser-verification'
        ])

    def get_content_diff(self, short_name, new_content=None):
        """Get unified diff between cached content and new content"""
        cached_content = self.load_cached_content(short_name)

        if cached_content is None:
            return None, "No cached content found"

        if new_content is None:
            # Extract new content
            url_data = next((u for u in self.urls_data if u['short_name'] == short_name), None)
            if not url_data:
                return None, "URL data not found"

            new_content = asyncio.run(self.extract_content_with_xpath(url_data['url'], url_data['xpath']))
            if new_content is None:
                return None, "Failed to extract new content"

        # Create unified diff
        old_lines = cached_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f'{short_name} (cached)',
            tofile=f'{short_name} (current)',
            lineterm='',
            n=3  # Context lines
        ))

        return diff, None

    def get_content_comparison(self, short_name):
        """Get both old and new content for comparison"""
        cached_content = self.load_cached_content(short_name)

        if cached_content is None:
            return None, None, "No cached content found"

        # Extract new content
        url_data = next((u for u in self.urls_data if u['short_name'] == short_name), None)
        if not url_data:
            return None, None, "URL data not found"

        new_content = asyncio.run(self.extract_content_with_xpath(url_data['url'], url_data['xpath']))

        if new_content is None:
            return cached_content, None, "Failed to extract new content"

        return cached_content, new_content, None

    def load_cached_content(self, short_name):
        """Load cached content for a given short name"""
        cache_file = self.get_cache_file_path(short_name)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as file:
                    return file.read()
            except Exception as e:
                print(f"Error loading cache for {short_name}: {e}")
        return None

    def save_content_to_cache(self, short_name, content):
        """Save content to cache file"""
        cache_file = self.get_cache_file_path(short_name)
        try:
            with open(cache_file, 'w', encoding='utf-8') as file:
                file.write(content)
        except Exception as e:
            print(f"Error saving cache for {short_name}: {e}")

    async def extract_content_with_xpath(self, url, xpath):
        """Extract content from URL using XPath"""
        async with async_playwright() as p:
            # Use persistent context for better performance
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # Navigate to the URL with retry logic
                for attempt in range(self.max_retries):
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=self.timeout)
                        break
                    except Exception as e:
                        if attempt == self.max_retries - 1:
                            raise e
                        print(f"Retry {attempt + 1}/{self.max_retries} for {url}")
                        await asyncio.sleep(2)

                # Get the full HTML content
                html_content = await page.content()

                if xpath:
                    # Parse HTML and extract content using XPath
                    tree = html.fromstring(html_content)
                    elements = tree.xpath(xpath)

                    if elements:
                        # Extract text content from matched elements
                        extracted_content = ""
                        for element in elements:
                            if hasattr(element, 'text_content'):
                                extracted_content += element.text_content() + "\n"
                            else:
                                extracted_content += str(element) + "\n"
                        return extracted_content.strip()
                    else:
                        print(f"No elements found for XPath: {xpath} on {url}")
                        return html_content
                else:
                    # If no XPath provided, return full HTML
                    return html_content

            except Exception as e:
                print(f"Error extracting content from {url}: {e}")
                return None
            finally:
                await context.close()
                await browser.close()

    async def check_single_url(self, url_data):
        """Check a single URL for changes"""
        short_name = url_data['short_name']
        url = url_data['url']
        xpath = url_data['xpath']

        print(f"Checking {short_name}: {url}")

        # Extract new content
        new_content = await self.extract_content_with_xpath(url, xpath)

        if new_content is None:
            print(f"Failed to extract content for {short_name}")
            return ('failed', 'extraction_failed')

        # Check if content indicates Cloudflare blocking
        if self.is_cloudflare_blocked(new_content):
            print(f"Content blocked by Cloudflare for {short_name}")
            # Still save the blocked content to cache to avoid repeated checks
            self.save_content_to_cache(short_name, new_content)
            return ('blocked', 'cloudflare')

        # Load cached content
        cached_content = self.load_cached_content(short_name)

        if cached_content is None:
            # First time checking this URL
            print(f"First time checking {short_name}, caching content")
            self.save_content_to_cache(short_name, new_content)
            return ('new', 'first_check')

        # Compare content
        new_hash = self.get_content_hash(new_content)
        old_hash = self.get_content_hash(cached_content)

        if new_hash != old_hash:
            print(f"Content changed for {short_name}")
            self.save_content_to_cache(short_name, new_content)
            return ('changed', 'content_modified')
        else:
            print(f"No changes for {short_name}")
            return ('unchanged', 'no_changes')

    async def check_all_urls(self):
        """Check all URLs for changes with concurrent processing"""
        print(f"\n--- Checking all URLs at {datetime.now()} (max concurrent: {self.max_concurrent}) ---")

        # Filter URLs that have actual URLs and XPath selectors
        valid_urls = [url_data for url_data in self.urls_data if url_data['url'] and url_data['xpath']]

        if not valid_urls:
            print("No valid URLs to check")
            return

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def check_with_semaphore(url_data):
            async with semaphore:
                return await self.check_single_url(url_data)

        # Create tasks for concurrent execution
        tasks = [check_with_semaphore(url_data) for url_data in valid_urls]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        changed_urls = []
        blocked_urls = []
        failed_urls = []

        for i, result in enumerate(results):
            url_data = valid_urls[i]
            if isinstance(result, Exception):
                print(f"Error checking {url_data['short_name']}: {result}")
                failed_urls.append((url_data, 'exception', str(result)))
            elif isinstance(result, tuple) and len(result) == 2:
                status, reason = result
                if status == 'changed':
                    changed_urls.append((url_data, status, reason))
                elif status == 'blocked':
                    blocked_urls.append((url_data, status, reason))
                elif status == 'failed':
                    failed_urls.append((url_data, status, reason))
                # 'new' and 'unchanged' statuses don't get reported

        # Create reports for changed and blocked URLs
        reportable_urls = changed_urls + blocked_urls + failed_urls
        if reportable_urls:
            self.create_change_report(reportable_urls)

        print(f"--- Check completed. {len(changed_urls)} URLs changed, {len(blocked_urls)} URLs blocked, {len(failed_urls)} URLs failed ---\n")

    def create_change_report(self, reportable_urls):
        """Create CSV report of changed/blocked URLs"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = '.report'
        report_file = os.path.join(report_dir, f"changes_{timestamp}.csv")

        # Create report directory if it doesn't exist
        os.makedirs(report_dir, exist_ok=True)

        # Create report data with headers
        report_data = [['short_name', 'url', 'xpath', 'status', 'reason']]
        for url_data, status, reason in reportable_urls:
            report_data.append([
                url_data['short_name'],
                url_data['url'],
                url_data['xpath'],
                status,
                reason
            ])

        # Save report
        with open(report_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(report_data)

        print(f"Change report saved to: {report_file}")

    def get_report_files(self):
        """Get list of report files"""
        report_files = []
        report_dir = '.report'
        if os.path.exists(report_dir):
            for file in os.listdir(report_dir):
                if file.startswith('changes_') and file.endswith('.csv'):
                    report_files.append(file)
        return sorted(report_files, reverse=True)

    def get_report_file_path(self, filename):
        """Get full path for a report file"""
        return os.path.join('.report', filename)

    def load_report_file(self, filename):
        """Load a report file as pandas DataFrame"""
        try:
            file_path = self.get_report_file_path(filename)
            return pd.read_csv(file_path, header=0)
        except Exception as e:
            print(f"Error loading report file {filename}: {e}")
            return pd.DataFrame()

    def start_monitoring_thread(self):
        """Start monitoring in a background thread"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring_thread(self):
        """Stop monitoring thread"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def _monitoring_loop(self):
        """Monitoring loop for background thread"""
        print("Starting background monitoring...")

        # Load URLs initially
        self.load_urls_from_csv()

        # Schedule the check to run every minute
        schedule.every(self.monitoring_interval).minutes.do(lambda: asyncio.run(self.check_all_urls()))

        # Run initial check
        asyncio.run(self.check_all_urls())

        # Keep the thread running
        print(f"Background monitoring scheduled to run every {self.monitoring_interval} minute(s).")
        while self.is_monitoring:
            schedule.run_pending()
            time.sleep(self.check_interval)

        print("Background monitoring stopped.")

    def run_monitoring_loop(self):
        """Run the monitoring loop (blocking)"""
        print("Starting content monitoring...")

        # Load URLs initially
        self.load_urls_from_csv()

        # Schedule the check to run every minute
        schedule.every(self.monitoring_interval).minutes.do(lambda: asyncio.run(self.check_all_urls()))

        # Run initial check
        asyncio.run(self.check_all_urls())

        # Keep the script running
        print(f"Monitoring scheduled to run every {self.monitoring_interval} minute(s). Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")
