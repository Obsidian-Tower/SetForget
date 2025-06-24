#!/usr/bin/env python3
"""
move_csv_to_grids.py

This script moves all `.csv` files from the current directory into a subfolder named `grids`.
If the `grids` folder does not exist, it will be created.

Usage:
    chmod +x move_csv_to_grids.py
    ./move_csv_to_grids.py
"""

import os
import shutil

def main():
    # Define source and target directories
    source_dir = os.getcwd()
    target_dir = os.path.join(source_dir, "grids")

    # Create target directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)

    moved_count = 0

    # Iterate over all files in the source directory
    for filename in os.listdir(source_dir):
        # Check for .csv extension
        if filename.lower().endswith(".csv"):
            source_path = os.path.join(source_dir, filename)
            dest_path   = os.path.join(target_dir, filename)
            if os.path.isfile(source_path):
                shutil.move(source_path, dest_path)
                print(f"Moved: {filename}")
                moved_count += 1

    print(f"\nTotal CSV files moved: {moved_count}")

if __name__ == "__main__":
    main()
