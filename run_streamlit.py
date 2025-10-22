#!/usr/bin/env python3
"""
Streamlit app runner for Content Monitor
"""
import subprocess
import sys
import os

def main():
    """Run the Streamlit app"""
    # Ensure we're in the correct directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Run streamlit
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py"]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
