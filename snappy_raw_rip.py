#!/usr/bin/env python3

#imports
from pathlib import Path
from datetime import datetime
import shutil
import os
import struct
import binascii
import tkinter as tk
from tkinter import filedialog


#constants
VOLUMES_PATH = Path("/Volumes")
SKIP_VOLUMES = {"Macintosh HD", "Macintosh HD - Data"} # future improvement, enhanced drive detection
PHOTO_EXTENSIONS = {
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

    # Video - Currently disabled
    # ".mp4", ".mov", ".avi", ".m4v", ".mxf", ".lrf" ".r3d",
}

# TIFF signatures for EXIF parsing
TIFF_SIGNATURE_LE = b'\x49\x49\x2A\x00'  # Little-endian (Intel)
TIFF_SIGNATURE_BE = b'\x4D\x4D\x00\x2A'  # Big-endian (Motorola)

# Canon CR3 UUID for metadata location
CANON_CMT1_UUID = "85c0b687820f11e08111f4ce462b6a48"

# EXIF tag IDs
EXIF_TAG_DATETIME_ORIGINAL = 36867
EXIF_TAG_EXIF_IFD_POINTER = 34665

# File extensions by parser type
CR3_EXTENSIONS = {".cr3"}
TIFF_BASED_RAW_EXTENSIONS = {".cr2", ".nef", ".nrw", ".pef", ".iiq", ".3fr", ".fff", ".dng"}
RAF_EXTENSIONS = {".raf"}

# Session-level fallback flag
_fallback_approved = None

DESTINATIONS_FILE = Path(__file__).parent / "destinations.txt"

# --- EXIF Parsing Functions ---

def _parse_date_string(date_str):
    """Convert EXIF date string 'YYYY:MM:DD HH:MM:SS' to date object."""
    try:
        return datetime.strptime(date_str.strip(), "%Y:%m:%d %H:%M:%S").date()
    except (ValueError, AttributeError):
        return None

def _find_datetime_in_ifd(f, ifd_offset, tiff_base, byte_order):
    """Parse IFD entries looking for DateTimeOriginal, following ExifIFD pointer if needed."""
    try:
        f.seek(tiff_base + ifd_offset)
        num_entries = struct.unpack(f'{byte_order}H', f.read(2))[0]

        if num_entries > 200:  # Sanity check
            return None

        for _ in range(num_entries):
            entry = f.read(12)
            if len(entry) < 12:
                return None

            tag_id, tag_type, count = struct.unpack(f'{byte_order}HHI', entry[0:8])
            value_data = entry[8:12]

            # Found DateTimeOriginal
            if tag_id == EXIF_TAG_DATETIME_ORIGINAL:
                if count <= 4:
                    return value_data.split(b'\x00')[0].decode('utf-8', errors='ignore')
                else:
                    offset = struct.unpack(f'{byte_order}I', value_data)[0]
                    current_pos = f.tell()
                    f.seek(tiff_base + offset)
                    date_str = f.read(count).split(b'\x00')[0].decode('utf-8', errors='ignore')
                    f.seek(current_pos)
                    return date_str

            # Follow ExifIFD pointer
            if tag_id == EXIF_TAG_EXIF_IFD_POINTER:
                exif_offset = struct.unpack(f'{byte_order}I', value_data)[0]
                current_pos = f.tell()
                result = _find_datetime_in_ifd(f, exif_offset, tiff_base, byte_order)
                if result:
                    return result
                f.seek(current_pos)

        return None
    except Exception:
        return None

def _extract_date_from_tiff_raw(file_path):
    """Extract DateTimeOriginal from TIFF-based RAW files (CR2, NEF, DNG, etc.)."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
            if len(header) < 8:
                return None

            # Check for TIFF signature and determine byte order
            if header[0:4] == TIFF_SIGNATURE_LE:
                byte_order = '<'
            elif header[0:4] == TIFF_SIGNATURE_BE:
                byte_order = '>'
            else:
                return None

            # Get IFD0 offset
            ifd_offset = struct.unpack(f'{byte_order}I', header[4:8])[0]
            if ifd_offset < 8 or ifd_offset > 65536:
                return None

            date_str = _find_datetime_in_ifd(f, ifd_offset, 0, byte_order)
            return _parse_date_string(date_str) if date_str else None
    except Exception:
        return None

def _extract_date_from_raf(file_path):
    """Extract DateTimeOriginal from Fujifilm RAF files."""
    try:
        with open(file_path, 'rb') as f:
            # Check for FUJIFILM header
            header = f.read(8)
            if not header.startswith(b'FUJIFILM'):
                return None

            # Read EXIF offset at byte 84 (UInt32)
            f.seek(84)
            exif_offset = struct.unpack('>I', f.read(4))[0]

            if exif_offset == 0 or exif_offset > 10000000:
                return None

            # RAF files embed a JPEG with EXIF in APP1 segment
            # The offset points to JPEG SOI marker (FFD8), followed by APP1 (FFE1)
            # Structure: FFD8 FFE1 [2-byte length] "Exif\x00\x00" [TIFF data]
            f.seek(exif_offset)
            jpeg_header = f.read(12)
            if len(jpeg_header) < 12:
                return None

            # Check for JPEG SOI + APP1 markers
            if jpeg_header[0:4] == b'\xff\xd8\xff\xe1':
                # Skip: SOI(2) + APP1 marker(2) + length(2) + "Exif\x00\x00"(6) = 12 bytes
                tiff_base = exif_offset + 12
                f.seek(tiff_base)
                tiff_header = f.read(8)
            else:
                # Fallback: try direct TIFF header
                tiff_base = exif_offset
                tiff_header = jpeg_header[0:8]

            if len(tiff_header) < 8:
                return None

            if tiff_header[0:4] == TIFF_SIGNATURE_LE:
                byte_order = '<'
            elif tiff_header[0:4] == TIFF_SIGNATURE_BE:
                byte_order = '>'
            else:
                return None

            ifd_offset = struct.unpack(f'{byte_order}I', tiff_header[4:8])[0]
            date_str = _find_datetime_in_ifd(f, ifd_offset, tiff_base, byte_order)
            return _parse_date_string(date_str) if date_str else None
    except Exception:
        return None

def _extract_date_from_cr3(file_path):
    """Extract DateTimeOriginal from Canon CR3 files (ISO BMFF format)."""
    try:
        with open(file_path, 'rb') as f:
            file_size = os.path.getsize(file_path)

            while f.tell() < file_size:
                box_start = f.tell()
                header = f.read(8)
                if len(header) < 8:
                    break

                box_size = struct.unpack('>I', header[0:4])[0]
                box_type = header[4:8].decode('utf-8', errors='ignore')

                header_len = 8
                if box_size == 1:
                    ext_size = f.read(8)
                    if len(ext_size) < 8:
                        break
                    box_size = struct.unpack('>Q', ext_size)[0]
                    header_len = 16

                if box_size == 0 or box_size > file_size:
                    break

                if box_type == 'uuid':
                    uuid_bytes = f.read(16)
                    uuid_hex = binascii.hexlify(uuid_bytes).decode('utf-8')

                    if uuid_hex == CANON_CMT1_UUID:
                        # CR3 CMT1 box contains multiple TIFF structures
                        # Search through all TIFF headers for DateTimeOriginal
                        search_start = f.tell()
                        chunk = f.read(min(200000, box_size - header_len - 16))

                        # Find all TIFF signatures and check each for DateTimeOriginal
                        search_pos = 0
                        while search_pos < len(chunk) - 8:
                            tiff_idx = chunk.find(TIFF_SIGNATURE_LE, search_pos)
                            if tiff_idx == -1:
                                tiff_idx = chunk.find(TIFF_SIGNATURE_BE, search_pos)
                            if tiff_idx == -1:
                                break

                            tiff_base = search_start + tiff_idx

                            if chunk[tiff_idx:tiff_idx+2] == b'II':
                                byte_order = '<'
                            else:
                                byte_order = '>'

                            ifd_offset = struct.unpack(f'{byte_order}I', chunk[tiff_idx+4:tiff_idx+8])[0]

                            if 8 <= ifd_offset <= 50000:
                                date_str = _find_datetime_in_ifd(f, ifd_offset, tiff_base, byte_order)
                                if date_str:
                                    return _parse_date_string(date_str)

                            # Move past this TIFF signature to find the next one
                            search_pos = tiff_idx + 1

                # Navigate container boxes
                if box_type in ['moov', 'trak', 'mdia', 'minf', 'stbl']:
                    f.seek(box_start + header_len)
                else:
                    f.seek(box_start + box_size)

        return None
    except Exception:
        return None

def _extract_date_generic_scan(file_path):
    """Fallback: scan first 4KB for TIFF signature if not at byte 0."""
    try:
        with open(file_path, 'rb') as f:
            # First check byte 0
            header = f.read(8)
            if len(header) >= 8:
                if header[0:4] == TIFF_SIGNATURE_LE:
                    ifd_offset = struct.unpack('<I', header[4:8])[0]
                    if 8 <= ifd_offset <= 65536:
                        date_str = _find_datetime_in_ifd(f, ifd_offset, 0, '<')
                        if date_str:
                            return _parse_date_string(date_str)
                elif header[0:4] == TIFF_SIGNATURE_BE:
                    ifd_offset = struct.unpack('>I', header[4:8])[0]
                    if 8 <= ifd_offset <= 65536:
                        date_str = _find_datetime_in_ifd(f, ifd_offset, 0, '>')
                        if date_str:
                            return _parse_date_string(date_str)

            # Scan first 4KB for TIFF signature
            f.seek(0)
            chunk = f.read(4096)

            for sig, byte_order in [(TIFF_SIGNATURE_LE, '<'), (TIFF_SIGNATURE_BE, '>')]:
                idx = chunk.find(sig)
                if idx != -1 and idx + 8 <= len(chunk):
                    ifd_offset = struct.unpack(f'{byte_order}I', chunk[idx+4:idx+8])[0]
                    if 8 <= ifd_offset <= 50000:
                        date_str = _find_datetime_in_ifd(f, ifd_offset, idx, byte_order)
                        if date_str:
                            return _parse_date_string(date_str)

        return None
    except Exception:
        return None

def _get_exif_date(photo_path):
    """Dispatcher: route to appropriate parser based on file extension."""
    ext = photo_path.suffix.lower()

    if ext in CR3_EXTENSIONS:
        return _extract_date_from_cr3(photo_path)
    elif ext in TIFF_BASED_RAW_EXTENSIONS:
        return _extract_date_from_tiff_raw(photo_path)
    elif ext in RAF_EXTENSIONS:
        return _extract_date_from_raf(photo_path)
    else:
        return _extract_date_generic_scan(photo_path)

#functions
def find_sd_card():
    """Scan /Volumes for a drive with DCIM folder at the top level."""
    for volume in VOLUMES_PATH.iterdir():
        if volume.name in SKIP_VOLUMES:
            continue
        dcim = volume / "DCIM"
        if dcim.exists():
            return dcim
    return None

def find_photos(dcim_path):
    """Find all photos in the DCIM folder and its subfolders."""
    photos = []
    for file in dcim_path.rglob("*"):
        if file.suffix.lower() in PHOTO_EXTENSIONS:
            photos.append(file)
    return photos

def select_source_files():
    """Open a file dialog to select photo files."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Bring dialog to front
    root.update()  # Process any pending events

    # Build file type filter from PHOTO_EXTENSIONS
    extensions = " ".join(f"*{ext}" for ext in sorted(PHOTO_EXTENSIONS))
    filetypes = [
        ("Photo files", extensions),
        ("All files", "*.*")
    ]

    files = filedialog.askopenfilenames(
        title="Select Photos to Import",
        filetypes=filetypes
    )

    # Fully clean up tkinter to prevent macOS terminal issues
    root.update()
    root.destroy()
    root.quit()

    return [Path(f) for f in files] if files else []

def get_all_photo_dates(photos):
    """Get dates for all photos, preferring EXIF DateTimeOriginal."""
    global _fallback_approved
    dates = {}
    fallback_needed = []

    for i, photo in enumerate(photos, 1):
        print(f"Reading EXIF data: {i}/{len(photos)}    ", end="\r")
        exif_date = _get_exif_date(photo)
        if exif_date:
            dates[photo] = exif_date
        else:
            fallback_needed.append(photo)
    print()  # Clear the progress line

    # Handle files that need fallback
    if fallback_needed:
        if _fallback_approved is None:
            print(f"\nCould not read EXIF date from {len(fallback_needed)} file(s).")
            if len(fallback_needed) <= 3:
                for f in fallback_needed:
                    print(f"  - {f.name}")
            else:
                print(f"  - {fallback_needed[0].name}")
                print(f"  - ... and {len(fallback_needed) - 1} more")
            response = input("Use file modification time as fallback? (y/n): ").strip().lower()
            _fallback_approved = response in ["y", "yes"]

        if _fallback_approved:
            for photo in fallback_needed:
                timestamp = photo.stat().st_mtime
                dates[photo] = datetime.fromtimestamp(timestamp).date()
        else:
            print(f"Skipping {len(fallback_needed)} files without EXIF dates.")

    return dates


def group_photos_by_date(photos):
    """Group photos by the date they were taken."""
    print("Reading dates from all photos...")
    dates = get_all_photo_dates(photos)
    print(f"Got dates for {len(dates)} photos")
    
    grouped = {}
    for photo, date in dates.items():
        if date not in grouped:
            grouped[date] = []
        grouped[date].append(photo)
    return grouped

def select_directory():
    """Open a file dialog to select a directory."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Bring dialog to front
    root.update()  # Process any pending events
    directory = filedialog.askdirectory(title="Select Destination Directory")

    # Fully clean up tkinter to prevent macOS terminal issues
    root.update()
    root.destroy()
    root.quit()

    return directory

def load_destinations():
    """Load any saved file destinations from txt file."""
    if not DESTINATIONS_FILE.exists():
        return []
    with open(DESTINATIONS_FILE, "r") as file:
        return [line.strip() for line in file if line.strip()]

def save_destinations(destinations):
    """Save new destinations to text file."""
    with open(DESTINATIONS_FILE, "w") as file:
        for destination in destinations:
            file.write(destination + "\n")

def get_destinations():
    """Show destinations menu and get user selections."""
    destinations = load_destinations()
    while True:
        print("\n" + "=" * 50)
        print("=== Select Destinations ===")
        print("=" * 50)
        if destinations:
            for i, dest in enumerate(destinations, 1):
                print(f"  [{i}] {dest}")
            print("-" * 50)
        else:
            print("  No saved destinations.")
            print("-" * 50)
        print("  [a] Add new destination")
        if destinations:
            print("  [b] Remove destination")
        print("=" * 50)
        choice = input("\nEnter selection (e.g., 1, 2, a, or b): ").strip().lower()
        if choice == "a":
            print("Opening folder selector...")
            new_dest = select_directory()
            if not new_dest:
                print("No directory selected.")
                continue
            dest_path = Path(new_dest).resolve()
            # Validate the path
            if not dest_path.exists():
                print(f"Error: Path does not exist: {dest_path}")
            elif not dest_path.is_dir():
                print(f"Error: Path is not a directory: {dest_path}")
            elif not os.access(dest_path, os.W_OK):
                print(f"Error: No write permission for: {dest_path}")
            else:
                # Convert to string for storage
                dest_str = str(dest_path)
                destinations.append(dest_str)
                save_destinations(destinations)
                print(f"Added: {dest_str}")
        elif choice == "b":
            if not destinations:
                print("No destinations to remove.")
                continue
            remove_choice = input("Enter number to remove: ").strip()
            try:
                remove_index = int(remove_choice)
                if 1 <= remove_index <= len(destinations):
                    removed = destinations.pop(remove_index - 1)
                    save_destinations(destinations)
                    print(f"Removed: {removed}")
                else:
                    print(f"Invalid number. Choose between 1 and {len(destinations)}.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        else:
            try:
                indices = [int(x.strip()) for x in choice.split(",")]
                selected = [destinations[i - 1] for i in indices]
                if selected:
                    return selected
            except (ValueError, IndexError):
                print("Invalid selection. Try again?")

def sanitize_shoot_name(name):
    """Remove or replace characters that are invalid in filesystem paths."""
    if not name:
        return ""
    # Invalid characters for most filesystems: / \ : * ? " < > |
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    # Remove leading/trailing whitespace and dots (problematic on some systems)
    sanitized = sanitized.strip('. ')
    return sanitized

def get_shoot_name():
    """Asks the user for a shoot name to add to the destination folder"""
    raw_name = input("Enter shoot name for final folders (or press Enter to skip): ").strip()
    if not raw_name:
        return ""
    sanitized = sanitize_shoot_name(raw_name)
    if sanitized != raw_name:
        print(f"Note: Shoot name sanitized to: '{sanitized}'")
    return sanitized

def format_file_size(size_bytes):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def calculate_total_size(grouped_photos):
    """Calculate total size of all photos to be copied."""
    total_bytes = 0
    for photos in grouped_photos.values():
        for photo in photos:
            total_bytes += photo.stat().st_size
    return total_bytes

def confirm_copy(grouped_photos, destinations, shoot_name):
    """Show summary and ask user to confirm before copying."""
    total_photos = sum(len(photos) for photos in grouped_photos.values())
    total_size = calculate_total_size(grouped_photos)
    print("\n" + "=" * 50)
    print("=== Copy Summary ===")
    print("=" * 50)
    print(f"Photos: {total_photos}")
    print(f"Total size: {format_file_size(total_size)}")
    print(f"Dates: {len(grouped_photos)}")
    print(f"Shoot name: '{shoot_name}'" if shoot_name else "Shoot name: (none)")
    print(f"Destinations ({len(destinations)}):")
    for dest in destinations:
        print(f"  - {dest}")
    print("=" * 50)
    answer = input("\nProceed with copy? (y/n): ").strip().lower()
    return answer in ["y", "yes"]

def check_conflicts(grouped_photos, destinations, shoot_name):
    """Check if any files already exist at destinations."""
    conflicts = []
    for dest in destinations:
        for date, photos in grouped_photos.items():
            folder = build_folder_path(dest, date, shoot_name)
            for photo in photos:
                dest_file = folder / photo.name
                if dest_file.exists():
                    conflicts.append(dest_file)
    return conflicts

def handle_conflicts():
    """Ask user how to handle existing files."""
    print("\n" + "=" * 50)
    print("=== Conflict Resolution ===")
    print("=" * 50)
    print("Some files already exist at the destination.")
    print()
    print("  [s] Skip - Don't copy files that already exist")
    print("  [o] Overwrite - Replace existing files")
    print("  [r] Rename - Add number to filename (e.g., IMG_001 (2).CR3)")
    print("=" * 50)

    while True:
        choice = input("\nHow to handle conflicts? (s/o/r): ").strip().lower()
        if choice in ["s", "o", "r"]:
            return choice
        print("Invalid choice. Enter s, o, or r.")

def build_folder_path(base_path, date, shoot_name):
    """Build the destination folder path: base/yyyy/yyyy-mm/yyyy-mm-dd Shoot Name."""
    year = date.strftime("%Y")
    year_month = date.strftime("%Y-%m")
    if shoot_name:
        folder_name = date.strftime("%Y-%m-%d") + " " + shoot_name
    else:
        folder_name = date.strftime("%Y-%m-%d")
    return Path(base_path) / year / year_month / folder_name
  

def copy_photos(grouped_photos, destinations, shoot_name, conflict_mode=None):
    """Copy photos to specified destinations, organized by date"""
    for dest in destinations:
        for date, photos in grouped_photos.items():
            folder = build_folder_path(dest, date, shoot_name)
            folder.mkdir(parents=True, exist_ok=True)
            total = len(photos)
            for i, photo in enumerate(photos, 1):
                dest_file = folder / photo.name
                
                # Handle conflicts
                if dest_file.exists():
                    if conflict_mode == "s":
                        print(f"Skipped: {photo.name} (already exists)")
                        continue
                    elif conflict_mode == "r":
                        counter = 2
                        stem = dest_file.stem
                        suffix = dest_file.suffix
                        while dest_file.exists():
                            dest_file = folder / f"{stem} ({counter}){suffix}"
                            counter += 1
                
                shutil.copy2(photo, dest_file)
                print(f"Copying to {folder.name}: {i}/{total}    ", end="\r")
            print()



#main
print("Scanning for SD card...")
sd_card = find_sd_card()

if sd_card:
    print(f"Found SD card: {sd_card.parent.name}")
    photos = find_photos(sd_card)
    print(f"Found {len(photos)} photos")
else:
    print("No SD card found.")
    choice = input("Select files manually? (y/n): ").strip().lower()
    if choice in ["y", "yes"]:
        print("Opening file picker...")
        photos = select_source_files()
        if photos:
            print(f"Selected {len(photos)} photos")
        else:
            print("No files selected.")
            photos = []
    else:
        photos = []

if photos:
    grouped = group_photos_by_date(photos)
    print(f"Photos span {len(grouped)} dates")
    destinations = get_destinations()
    shoot_name = get_shoot_name()
    if confirm_copy(grouped, destinations, shoot_name):
        conflicts = check_conflicts(grouped, destinations, shoot_name)
        conflict_mode = None
        if conflicts:
            print(f"\nFound {len(conflicts)} existing files.")
            conflict_mode = handle_conflicts()
        copy_photos(grouped, destinations, shoot_name, conflict_mode)
        print("\nCopy Complete! Close and Re-open program to run again.")
    else:
        print("\nCopy cancelled.")