# SnapPy RAW Rip
A lightweight Python utility for photographers that automates RAW and JPG import. This tool scans for connected volumes and copies photos into one or more folders using an ISO date-based hierarchy.

## Features
* **Auto-Detection:** Automatically searches for mounted drives with a `DCIM` folder.
* **Date-Based Sorting:** Reads file modification timestamps to group photos into `YYYY` -> `YYYY-MM` -> `YYYY-MM-DD` folders.
* **Shoot Naming:** Optional prompt to append a specific shoot name to the final folder (e.g., `2026-01-04 Sunrise`).
* **Multi-Target Backup:** Simultaneously copy photos to multiple destinations (exmaple: your working SSD and NAS).
* **Conflict Resolution:** Manage duplicate files with options to **Skip**, **Overwrite**, or **Rename**.
* **Save Preivous Destinations:** Remembers your previously used backup locations in a local text file.

## Supported Formats
Currently configured to detect:
# Standard Images
    ".jpg", ".jpeg", ".png", ".heic", ".tiff", ".tif",
    # Generic RAW: / Adobe / DJI / Ricoh
    ".dng",
    # Canon
    ".cr2", ".cr3",
    # Nikon
    ".nef", ".nrw",
    # Sony
    ".arw", ".srf", ".sr2",
    # Fuji
    ".raf",
    # Olympus
    ".orf",
    # Panasonic
    ".rw2", ".raw",
    # Phase One / Leaf
    ".iiq",
    # Pentax
    ".pef", ".ptx",
    # Hasselblad
    ".3fr", ".fff",

## Requirements / Dependencies
* macOS (Script relies on `/Volumes` detection)
* Python 3

## Usage
1. Connect your SD Card
2. Run: `python3 snappy_raw_rip.py`
3. Follow the text prompts


