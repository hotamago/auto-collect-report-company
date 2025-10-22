# Content Monitor

A Python tool for monitoring web content changes using XPath selectors with concurrent processing for improved speed.

## Features

- Extract content from URLs using XPath selectors
- Cache extracted content for change detection
- Concurrent processing for multiple URLs
- Automatic CSV reports when content changes
- Scheduled monitoring with cron-like functionality

## Installation

1. Install dependencies:
```bash
uv sync
```

2. Install Playwright browsers:
```bash
playwright install
```

## Usage

### CSV Format

The `urls.csv` file should have the following format:
```csv
Short Name,URL,XPath Selector
NTC,https://namtanuyen.com.vn/bao-cao-tai-chinh,/html/body/form/div[3]/div[2]
IDC,https://www.idico.com.vn/vi/quan-he-co-dong/cong-bo-thong-tin?slug=cbtt-bctt,/html/body/div[1]/div[2]/div[1]/div/div[2]/div[1]/main/div
```

### Single Check

Run a one-time check of all URLs:
```bash
python main.py --max-concurrent 5
```

### Continuous Monitoring

Run continuous monitoring every minute:
```bash
python main.py --monitor --max-concurrent 5
```

### Configuration Options

- `--max-concurrent N`: Maximum number of concurrent URL extractions (default: 5)
- `--monitor`: Run continuous monitoring every minute

## How It Works

1. **Content Extraction**: Uses Playwright to load web pages and extract content using XPath selectors
2. **Caching**: Saves extracted content to `.cache/{SHORT_NAME}.cache` files
3. **Change Detection**: Compares MD5 hashes of new vs cached content
4. **Reporting**: Creates timestamped CSV files (`changes_YYYYMMDD_HHMMSS.csv`) when changes are detected
5. **Concurrency**: Processes multiple URLs simultaneously up to the configured limit

## Output

When changes are detected, a CSV file is created with the format:
```csv
Short Name,URL,XPath Selector,Change Status
NTC,https://namtanuyen.com.vn/bao-cao-tai-chinh,/html/body/form/div[3]/div[2],CHANGED
IDC,https://www.idico.com.vn/vi/quan-he-co-dong/cong-bo-thong-tin?slug=cbtt-bctt,/html/body/div[1]/div[2]/div[1]/div/div[2]/div[1]/main/div,
```

## Performance Tips

- **Increase concurrency**: Use `--max-concurrent 10` for faster processing if you have many URLs
- **Reduce concurrency**: Use `--max-concurrent 2` if websites have rate limiting
- **Monitor resources**: Higher concurrency uses more memory and network bandwidth

## Stopping Monitoring

When running in monitor mode, press `Ctrl+C` to stop the monitoring loop.
