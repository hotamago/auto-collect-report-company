# Content Monitor

A Python tool for monitoring web content changes using XPath selectors with concurrent processing for improved speed. Now includes a modern Streamlit web interface for easy management and monitoring.

## Features

- Extract content from URLs using XPath selectors
- Cache extracted content for change detection
- Concurrent processing for multiple URLs
- Automatic CSV reports when content changes
- Scheduled monitoring with cron-like functionality
- **NEW**: Modern web interface with Streamlit
- **NEW**: Upload and edit URLs through the UI
- **NEW**: Background monitoring with real-time status
- **NEW**: View and download change reports

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

### Web Interface (Recommended)

Run the Streamlit web application:

```bash
python run_streamlit.py
```

Or directly with streamlit:

```bash
streamlit run app.py
```

The web interface provides:
- **Dashboard**: Overview of monitoring status and controls
- **URL Management**: Edit URLs in a table or upload CSV files
- **Reports**: View and download change reports
- **Settings**: Configure monitoring parameters

### CSV Format

The `urls.csv` file should have the following format:
```csv
Short Name,URL,XPath Selector
NTC,https://namtanuyen.com.vn/bao-cao-tai-chinh,/html/body/form/div[3]/div[2]
IDC,https://www.idico.com.vn/vi/quan-he-co-dong/cong-bo-thong-tin?slug=cbtt-bctt,/html/body/div[1]/div[2]/div[1]/div/div[2]/div[1]/main/div
```

### Command Line (Legacy)

#### Single Check

Run a one-time check of all URLs:
```bash
python main.py --max-concurrent 5
```

#### Continuous Monitoring

Run continuous monitoring every minute:
```bash
python main.py --monitor --max-concurrent 5
```

#### Configuration Options

- `--max-concurrent N`: Maximum number of concurrent URL extractions (default: 5)
- `--max-retries N`: Maximum number of retries for failed requests (default: 2)
- `--timeout N`: Timeout in milliseconds for page loading (default: 10000)
- `--interval N`: Monitoring interval in minutes (default: 1)
- `--check-interval N`: Check interval in seconds for monitoring loop (default: 1.0)
- `--monitor`: Run continuous monitoring at specified interval

## How It Works

1. **Content Extraction**: Uses Playwright to load web pages and extract content using XPath selectors
2. **Caching**: Saves extracted content to `.cache/{SHORT_NAME}.cache` files
3. **Change Detection**: Compares MD5 hashes of new vs cached content
4. **Reporting**: Creates timestamped CSV files (`changes_YYYYMMDD_HHMMSS.csv`) when changes are detected
5. **Concurrency**: Processes multiple URLs simultaneously up to the configured limit

## Output

When changes are detected, a CSV file is created with the format:
```csv
Short Name,URL,XPath Selector
NTC,https://namtanuyen.com.vn/bao-cao-tai-chinh,/html/body/form/div[3]/div[2]
IDC,https://www.idico.com.vn/vi/quan-he-co-dong/cong-bo-thong-tin?slug=cbtt-bctt,/html/body/div[1]/div[2]/div[1]/div/div[2]/div[1]/main/div
```

## Web Interface Features

### Dashboard
- Real-time monitoring status
- Quick controls for starting/stopping monitoring
- URL statistics overview

### URL Management
- **Edit Mode**: Interactive table to add, edit, and delete URLs
- **Upload Mode**: Upload CSV files to bulk import URLs
- Support for merging or replacing existing URLs

### Reports
- List all generated change reports
- View report contents in the interface
- Download reports as CSV files
- File metadata (creation date, size, etc.)

### Settings
- Configure maximum concurrent connections
- Set maximum retries for failed requests
- Adjust page load timeout
- Set monitoring interval
- Configure check interval for monitoring loop
- Cache management (view and clear cache)
- System information

## Performance Tips

- **Increase concurrency**: Use `--max-concurrent 10` for faster processing if you have many URLs
- **Reduce concurrency**: Use `--max-concurrent 2` if websites have rate limiting
- **Adjust retries**: Increase `--max-retries` for unreliable connections, decrease for faster processing
- **Set appropriate timeout**: Use `--timeout` based on your network speed (5000-30000ms is typical)
- **Monitoring frequency**: Adjust `--interval` based on how frequently content changes (1-60 minutes)
- **Check interval tuning**: Lower `--check-interval` for more responsive monitoring (0.1-1.0s), higher for reduced CPU usage (1.0-5.0s)
- **Monitor resources**: Higher concurrency uses more memory and network bandwidth
- **Background monitoring**: Use the web interface's background monitoring for continuous operation

## Stopping Monitoring

When running in monitor mode, press `Ctrl+C` to stop the monitoring loop. In the web interface, use the "Stop Monitoring" button.
