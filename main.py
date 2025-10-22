import asyncio
import os
import hashlib
import schedule
import time
from datetime import datetime
from playwright.async_api import async_playwright
from lxml import html
import csv

class ContentMonitor:
    def __init__(self, csv_file='urls.csv', cache_dir='.cache', max_concurrent=5):
        self.csv_file = csv_file
        self.cache_dir = cache_dir
        self.urls_data = []
        self.max_concurrent = max_concurrent  # Maximum concurrent URL extractions
        self.ensure_cache_dir()

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
                    if len(row) >= 3 and row[1].strip():  # Ensure we have at least 3 columns and URL is not empty
                        short_name = row[0].strip()
                        url = row[1].strip()
                        xpath = row[2].strip() if len(row) > 2 else ""
                        self.urls_data.append({
                            'short_name': short_name,
                            'url': url,
                            'xpath': xpath
                        })
            print(f"Loaded {len(self.urls_data)} URLs from {self.csv_file}")
        except Exception as e:
            print(f"Error loading CSV file: {e}")

    def get_cache_file_path(self, short_name):
        """Get cache file path for a given short name"""
        return os.path.join(self.cache_dir, f"{short_name}.cache")

    def get_content_hash(self, content):
        """Get hash of content for comparison"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

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
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=10000)
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        print(f"Retry {attempt + 1}/{max_retries} for {url}")
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
            return False

        # Load cached content
        cached_content = self.load_cached_content(short_name)

        if cached_content is None:
            # First time checking this URL
            print(f"First time checking {short_name}, caching content")
            self.save_content_to_cache(short_name, new_content)
            return False

        # Compare content
        new_hash = self.get_content_hash(new_content)
        old_hash = self.get_content_hash(cached_content)

        if new_hash != old_hash:
            print(f"Content changed for {short_name}")
            self.save_content_to_cache(short_name, new_content)
            return True
        else:
            print(f"No changes for {short_name}")
            return False

    async def check_all_urls(self):
        """Check all URLs for changes with concurrent processing"""
        print(f"\n--- Checking all URLs at {datetime.now()} (max concurrent: {self.max_concurrent}) ---")

        # Filter URLs that have actual URLs
        valid_urls = [url_data for url_data in self.urls_data if url_data['url']]

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
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error checking {valid_urls[i]['short_name']}: {result}")
            elif result:  # True means content changed
                changed_urls.append(valid_urls[i])

        if changed_urls:
            self.create_change_report(changed_urls)

        print(f"--- Check completed. {len(changed_urls)} URLs changed ---\n")

    def create_change_report(self, changed_urls):
        """Create CSV report of changed URLs"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"changes_{timestamp}.csv"

        # Read original CSV
        original_data = []
        os.makedirs('.report', exist_ok=True)
        with open(os.path.join('.report', self.csv_file), 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            original_data = list(reader)

        # Create report data
        report_data = []
        for row in original_data:
            if len(row) >= 3:
                short_name = row[0].strip()
                url = row[1].strip()
                xpath = row[2].strip() if len(row) > 2 else ""

                # Check if this URL changed
                changed = any(cu['short_name'] == short_name for cu in changed_urls)
                # change_status = "CHANGED" if changed else ""

                if changed:
                    report_data.append([short_name, url])

        # Save report
        with open(report_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(report_data)

        print(f"Change report saved to: {report_file}")

    def run_monitoring_loop(self):
        """Run the monitoring loop"""
        print("Starting content monitoring...")

        # Load URLs initially
        self.load_urls_from_csv()

        # Schedule the check to run every minute
        schedule.every(1).minutes.do(lambda: asyncio.run(self.check_all_urls()))

        # Run initial check
        asyncio.run(self.check_all_urls())

        # Keep the script running
        print("Monitoring scheduled to run every minute. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")

async def main(max_concurrent=5):
    """Main function for single run"""
    monitor = ContentMonitor(max_concurrent=max_concurrent)

    # Load URLs
    monitor.load_urls_from_csv()

    # Check all URLs once
    await monitor.check_all_urls()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Content monitoring tool')
    parser.add_argument('--monitor', action='store_true', help='Run continuous monitoring every minute')
    parser.add_argument('--max-concurrent', type=int, default=5,
                       help='Maximum number of concurrent URL extractions (default: 5)')

    args = parser.parse_args()

    if args.monitor:
        # Run continuous monitoring
        monitor = ContentMonitor(max_concurrent=args.max_concurrent)
        monitor.run_monitoring_loop()
    else:
        # Run single check
        asyncio.run(main(args.max_concurrent))
