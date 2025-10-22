import asyncio
import platform

# Set proper event loop policy for Windows subprocess support (needed for Playwright)
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import pandas as pd
from monitor import ContentMonitor
import os
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Content Monitor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'monitor' not in st.session_state:
    st.session_state.monitor = ContentMonitor()

if 'monitoring_active' not in st.session_state:
    st.session_state.monitoring_active = False

if 'settings_changed' not in st.session_state:
    st.session_state.settings_changed = False

def load_urls_data():
    """Load URLs data and return as DataFrame"""
    st.session_state.monitor.load_urls_from_csv()
    return st.session_state.monitor.get_urls_as_dataframe()

def save_urls_data(df):
    """Save DataFrame to URLs data"""
    st.session_state.monitor.update_urls_from_dataframe(df)

def run_single_check():
    """Run a single check of all URLs"""
    asyncio.run(st.session_state.monitor.check_all_urls())

def start_monitoring():
    """Start background monitoring"""
    if not st.session_state.monitoring_active:
        st.session_state.monitor.start_monitoring_thread()
        st.session_state.monitoring_active = True

def stop_monitoring():
    """Stop background monitoring"""
    if st.session_state.monitoring_active:
        st.session_state.monitor.stop_monitoring_thread()
        st.session_state.monitoring_active = False

# Sidebar navigation
st.sidebar.title("🔍 Content Monitor")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "URL Management", "Reports", "Settings"]
)

# Main content
st.title("Content Monitor Dashboard")

if page == "Dashboard":
    st.header("📊 Monitoring Dashboard")

    # Status cards
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total URLs", len(st.session_state.monitor.urls_data))

    with col2:
        valid_urls = len([u for u in st.session_state.monitor.urls_data if u['url'] and u['xpath']])
        st.metric("Active URLs", valid_urls)

    with col3:
        monitoring_status = "Running" if st.session_state.monitoring_active else "Stopped"
        st.metric("Monitoring Status", monitoring_status)

    # Control buttons
    st.subheader("Controls")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Run Single Check", width='stretch'):
            with st.spinner("Checking URLs..."):
                run_single_check()
            st.success("Check completed!")

    with col2:
        if not st.session_state.monitoring_active:
            if st.button("▶️ Start Monitoring", width='stretch'):
                start_monitoring()
                st.success("Background monitoring started!")
                st.rerun()
        else:
            if st.button("⏹️ Stop Monitoring", width='stretch'):
                stop_monitoring()
                st.success("Background monitoring stopped!")
                st.rerun()

    with col3:
        if st.button("📋 Refresh Data", width='stretch'):
            load_urls_data()
            st.success("Data refreshed!")

    # Current URLs preview
    st.subheader("Current URLs")
    df = load_urls_data()
    if not df.empty:
        st.dataframe(df, width='stretch')
    else:
        st.info("No URLs configured yet. Go to URL Management to add some.")

elif page == "URL Management":
    st.header("🔗 URL Management")

    tab1, tab2 = st.tabs(["Edit URLs", "Upload CSV"])

    with tab1:
        st.subheader("Edit URLs")

        # Load current data
        df = load_urls_data()

        # Add empty rows for new entries
        if st.button("➕ Add New URL"):
            new_row = pd.DataFrame([{"short_name": "", "url": "", "xpath": ""}])
            df = pd.concat([df, new_row], ignore_index=True)

        # Editable dataframe
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "short_name": st.column_config.TextColumn("Short Name", width="small"),
                "url": st.column_config.TextColumn("URL", width="large"),
                "xpath": st.column_config.TextColumn("XPath", width="large")
            }
        )

        # Save button
        if st.button("💾 Save Changes", type="primary"):
            save_urls_data(edited_df)
            st.success("URLs saved successfully!")

    with tab2:
        st.subheader("Upload CSV File")

        st.markdown("""
        Upload a CSV file with the following format:
        ```
        Short Name,URL,XPath Selector
        NTC,https://example.com,/html/body/div[1]
        ```
        """)

        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

        if uploaded_file is not None:
            try:
                # Read uploaded CSV
                uploaded_df = pd.read_csv(uploaded_file)

                # Validate format
                required_columns = ['short_name', 'url', 'xpath']
                if not all(col in uploaded_df.columns for col in required_columns):
                    # Try with different column names or no header
                    if len(uploaded_df.columns) >= 3:
                        uploaded_df.columns = required_columns
                    else:
                        st.error("CSV must have at least 3 columns: Short Name, URL, XPath")
                        st.stop()

                st.success("CSV file uploaded successfully!")

                # Show preview
                st.subheader("Preview")
                st.dataframe(uploaded_df, width='stretch')

                # Replace or merge option
                replace_option = st.radio(
                    "How to handle existing data:",
                    ["Replace all existing URLs", "Merge with existing URLs"],
                    help="Replace will overwrite all current URLs, merge will add new URLs to existing ones."
                )

                if st.button("📥 Import URLs", type="primary"):
                    if replace_option == "Replace all existing URLs":
                        save_urls_data(uploaded_df)
                    else:
                        # Merge with existing
                        existing_df = load_urls_data()
                        merged_df = pd.concat([existing_df, uploaded_df], ignore_index=True)
                        save_urls_data(merged_df)

                    st.success("URLs imported successfully!")
                    st.rerun()

            except Exception as e:
                st.error(f"Error processing CSV file: {str(e)}")

elif page == "Reports":
    st.header("📋 Reports")

    # Get report files
    report_files = st.session_state.monitor.get_report_files()

    if report_files:
        st.subheader(f"Found {len(report_files)} report files")

        # File selector
        selected_file = st.selectbox("Select a report to view:", report_files)

        if selected_file:
            # Load and display report
            report_df = st.session_state.monitor.load_report_file(selected_file)

            if not report_df.empty:
                st.subheader(f"Report: {selected_file}")

                # File info
                full_file_path = st.session_state.monitor.get_report_file_path(selected_file)
                file_stats = os.stat(full_file_path)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Changes", len(report_df))
                with col2:
                    file_date = datetime.fromtimestamp(file_stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    st.metric("Generated", file_date)
                with col3:
                    st.metric("File Size", f"{file_stats.st_size} bytes")

                # Display data
                st.dataframe(report_df, width='stretch')

                # Download button
                csv_data = report_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Report",
                    data=csv_data,
                    file_name=selected_file,
                    mime="text/csv"
                )

                # Diff viewer section
                st.markdown("---")
                st.subheader("🔍 Content Diff Viewer")

                # Filter for URLs that have changed (not blocked or failed)
                changed_urls = report_df[report_df['status'] == 'changed']
                if not changed_urls.empty:
                    # URL selector for diff
                    selected_short_name = st.selectbox(
                        "Select a URL to view content changes:",
                        changed_urls['short_name'].tolist(),
                        key="diff_selector"
                    )

                    if selected_short_name:
                        with st.spinner("Generating diff..."):
                            diff_lines, error = st.session_state.monitor.get_content_diff(selected_short_name)

                            if error:
                                st.error(f"Error generating diff: {error}")
                            elif diff_lines:
                                # Display diff in a nice format
                                st.markdown("**Content Differences:**")

                                # Convert diff lines to colored HTML
                                diff_html = ""
                                for line in diff_lines:
                                    if line.startswith('---') or line.startswith('+++'):
                                        diff_html += f"<div style='color: #666; font-weight: bold;'>{line}</div>"
                                    elif line.startswith('@@'):
                                        diff_html += f"<div style='color: #888; background-color: #f0f0f0; padding: 2px 4px; margin: 2px 0; border-radius: 3px;'>{line}</div>"
                                    elif line.startswith('-'):
                                        diff_html += f"<div style='color: #d73a49; background-color: #ffeef0; padding: 1px 4px; margin: 1px 0; border-left: 3px solid #d73a49;'>{line}</div>"
                                    elif line.startswith('+'):
                                        diff_html += f"<div style='color: #22863a; background-color: #e6ffed; padding: 1px 4px; margin: 1px 0; border-left: 3px solid #22863a;'>{line}</div>"
                                    else:
                                        diff_html += f"<div style='color: #24292e; padding: 1px 4px; margin: 1px 0;'>{line}</div>"

                                st.markdown(
                                    f'<div style="font-family: monospace; font-size: 12px; line-height: 1.4; white-space: pre; overflow-x: auto; max-height: 500px; border: 1px solid #ddd; border-radius: 5px; padding: 10px;">{diff_html}</div>',
                                    unsafe_allow_html=True
                                )

                                # Summary statistics
                                additions = sum(1 for line in diff_lines if line.startswith('+'))
                                deletions = sum(1 for line in diff_lines if line.startswith('-'))

                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Lines Added", additions)
                                with col2:
                                    st.metric("Lines Removed", deletions)
                                with col3:
                                    st.metric("Total Diff Lines", len(diff_lines))
                            else:
                                st.info("No differences found between cached and current content.")
                else:
                    st.info("No URLs with content changes in this report (only blocked or failed URLs found).")

                # Raw content comparison section
                st.markdown("---")
                st.subheader("📄 Raw Content Comparison")

                # Allow comparison for any URL in the report
                if not report_df.empty:
                    selected_comparison = st.selectbox(
                        "Select a URL to compare raw content:",
                        report_df['short_name'].tolist(),
                        key="content_comparison_selector"
                    )

                    if selected_comparison:
                        with st.spinner("Loading content..."):
                            old_content, new_content, error = st.session_state.monitor.get_content_comparison(selected_comparison)

                            if error:
                                st.error(f"Error loading content: {error}")
                            else:
                                tab1, tab2 = st.tabs(["Cached Content", "Current Content"])

                                with tab1:
                                    if old_content:
                                        st.text_area(
                                            "Cached Content",
                                            old_content,
                                            height=300,
                                            disabled=True,
                                            key="old_content"
                                        )
                                    else:
                                        st.info("No cached content available.")

                                with tab2:
                                    if new_content:
                                        st.text_area(
                                            "Current Content",
                                            new_content,
                                            height=300,
                                            disabled=True,
                                            key="new_content"
                                        )
                                    else:
                                        st.info("Could not retrieve current content.")

                                # Show content lengths
                                if old_content and new_content:
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Cached Length", f"{len(old_content)} chars")
                                    with col2:
                                        st.metric("Current Length", f"{len(new_content)} chars")
                                    with col3:
                                        length_diff = len(new_content) - len(old_content)
                                        st.metric("Length Difference", f"{length_diff:+} chars")

            else:
                st.error("Could not load the selected report file.")
    else:
        st.info("No report files found. Reports will be generated when content changes are detected.")

elif page == "Settings":
    st.header("⚙️ Settings")

    st.subheader("Monitoring Configuration")

    # Max concurrent connections
    max_concurrent = st.slider(
        "Maximum Concurrent Connections",
        min_value=1,
        max_value=20,
        value=st.session_state.monitor.max_concurrent,
        help="Number of URLs to check simultaneously"
    )

    # Max retries
    max_retries = st.slider(
        "Maximum Retries",
        min_value=0,
        max_value=10,
        value=st.session_state.monitor.max_retries,
        help="Maximum number of retries for failed requests"
    )

    # Timeout
    timeout = st.slider(
        "Page Load Timeout (ms)",
        min_value=1000,
        max_value=60000,
        value=st.session_state.monitor.timeout,
        step=1000,
        help="Timeout in milliseconds for page loading"
    )

    # Monitoring interval
    monitoring_interval = st.slider(
        "Monitoring Interval (minutes)",
        min_value=1,
        max_value=60,
        value=st.session_state.monitor.monitoring_interval,
        help="How often to check URLs when monitoring is active"
    )

    # Check interval
    check_interval = st.slider(
        "Check Interval (seconds)",
        min_value=0.1,
        max_value=10.0,
        value=float(st.session_state.monitor.check_interval),
        step=0.1,
        help="How often the monitoring loop checks for scheduled tasks (lower values = more responsive but higher CPU usage)"
    )

    # Check if settings changed
    settings_changed = (
        max_concurrent != st.session_state.monitor.max_concurrent or
        max_retries != st.session_state.monitor.max_retries or
        timeout != st.session_state.monitor.timeout or
        monitoring_interval != st.session_state.monitor.monitoring_interval or
        check_interval != st.session_state.monitor.check_interval
    )

    if settings_changed:
        st.session_state.monitor.max_concurrent = max_concurrent
        st.session_state.monitor.max_retries = max_retries
        st.session_state.monitor.timeout = timeout
        st.session_state.monitor.monitoring_interval = monitoring_interval
        st.session_state.monitor.check_interval = check_interval
        st.success("Settings updated successfully!")
        st.session_state.settings_changed = True

    st.subheader("Cache Information")

    # Cache directory info
    cache_dir = st.session_state.monitor.cache_dir
    if os.path.exists(cache_dir):
        cache_files = os.listdir(cache_dir)
        st.metric("Cached URLs", len(cache_files))

        if st.button("🗑️ Clear Cache"):
            import shutil
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
            st.success("Cache cleared!")
    else:
        st.info("Cache directory not found")

    st.subheader("System Information")
    st.write(f"**CSV File:** {st.session_state.monitor.csv_file}")
    st.write(f"**Cache Directory:** {st.session_state.monitor.cache_dir}")
    st.write(f"**Max Concurrent:** {st.session_state.monitor.max_concurrent}")
    st.write(f"**Max Retries:** {st.session_state.monitor.max_retries}")
    st.write(f"**Timeout:** {st.session_state.monitor.timeout}ms")
    st.write(f"**Monitoring Interval:** {st.session_state.monitor.monitoring_interval} minutes")
    st.write(f"**Check Interval:** {st.session_state.monitor.check_interval} seconds")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Built with ❤️ using Streamlit")

# Auto-refresh for monitoring status
if st.session_state.monitoring_active:
    st.sidebar.success("🔄 Monitoring Active")
else:
    st.sidebar.info("⏹️ Monitoring Stopped")
