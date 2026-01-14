# SnapPy RAW Rip
A lightweight Python utility for photographers that automates RAW and JPG import. This tool scans for connected volumes and copies photos into one or more folders using an ISO date-based hierarchy. This script reads binary to exctract Exif data from Canon, Nikon, Fuji, Sony, and other camera makes without dependencies--should be fast.

## Features
* **Auto-Detection:** Automatically searches for mounted drives with a `DCIM` folder.
* **Manual File Selection:** If no SD card is found, offers to open a native file picker for manual selection.
* **EXIF Date Extraction:** Reads DateTimeOriginal from photo EXIF data for accurate date sorting. Supports Canon CR3, Fujifilm RAF, and other RAW formats.
* **Date-Based Sorting:** Groups photos into `YYYY` -> `YYYY-MM` -> `YYYY-MM-DD` folders based on capture date.
* **Shoot Naming:** Optional prompt to append a specific shoot name to the final folder (e.g., `2026-01-04 Sunrise`). Invalid filesystem characters are automatically sanitized.
* **Multi-Target Backup:** Simultaneously copy photos to multiple destinations (example: your working SSD and NAS).
* **Conflict Resolution:** Manage duplicate files with options to **Skip**, **Overwrite**, or **Rename**.
* **Destination Management:** Save, select, and remove backup locations with an intuitive menu system.
* **GUI Folder Picker:** Use native macOS file dialog to select destination folders instead of manually typing paths.
* **File Size Display:** Shows total size of photos to be copied in human-readable format before proceeding.
* **Flexible Input:** Accepts various confirmation formats (y/yes/Y/Yes/YES) for better usability.

## Supported Formats
Currently configured to detect:

* Standard Images
    '.jpg', '.jpeg', '.png', '.heic', '.tiff', '.tif',
* Generic RAW: / Adobe / DJI / Ricoh
    '.dng',
* Canon
    '.cr2', '.cr3',
* Nikon
    '.nef', '.nrw',
* Sony
    '.arw', '.srf', '.sr2',
* Fuji
    '.raf',
* Olympus
    '.orf',
* Panasonic
    '.rw2', '.raw',
* Phase One / Leaf
    '.iiq',
* Pentax
    '.pef', '.ptx',
* Hasselblad
    '.3fr', '.fff',

## Requirements / Dependencies
* macOS (Script relies on `/Volumes` detection)
* Python 3 with tkinter (included by default in most Python installations)

## Usage
1. Connect your SD Card (or run without one for manual file selection)
2. Run: `python3 snappy_raw_rip.py`
3. Follow the text prompts

## Recent Updates (v1.4)
* **EXIF-based date sorting:** Now reads DateTimeOriginal from EXIF metadata instead of file modification time
* **Manual file selection fallback:** If no SD card is detected, prompts to select files manually via Finder
* **Fixed EXIF parsing:** Improved support for Canon CR3 and Fujifilm RAF files

### Previous Updates (v1.3)
* Improved copy progress display:
  * Single destination: `Copying image 2/30 into /path/to/folder`
  * Multiple destinations: `Copying into folder 1/3, image 2/30 into /path/to/folder`

### Previous Updates (v1.2)
* Added GUI folder picker using native macOS file dialog (tkinter)
* Added option to remove saved destinations from the menu
* Simplified path handling by using native dialog output
* Improved destination management UX

### Previous Updates (v1.1)
* Added shoot name sanitization for invalid filesystem characters
* Enhanced path input with `~` expansion, directory validation, and write permission checks
* Improved confirmation input to accept flexible formats (y/yes in any case)
* Added total file size display in human-readable format before copying
* Enhanced menu readability with visual separators
* Consistent prompt formatting with colons and proper spacing

## Planned Updates
* Windows Support
* Linux Support

