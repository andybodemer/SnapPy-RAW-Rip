#!/usr/bin/env python3

#imports
from pathlib import Path
from datetime import datetime
import shutil
import os


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



DESTINATIONS_FILE = Path(__file__).parent / "destinations.txt"

#fucntions
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

def get_all_photo_dates(photos):
    """Get dates for all photos from file modification time."""
    dates = {}
    for photo in photos:
        timestamp = photo.stat().st_mtime
        dates[photo] = datetime.fromtimestamp(timestamp).date()
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
        print("=" * 50)
        choice = input("\nEnter selection (e.g., 1, 2, or a): ").strip().lower()
        if choice == "a":
            new_dest = input("Enter full path: ").strip()
            if not new_dest:
                print("No path entered.")
                continue
            # Remove surrounding quotes if present
            new_dest = new_dest.strip('\'"')
            # Expand ~ and resolve relative paths
            dest_path = Path(new_dest).expanduser().resolve()
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
sd_card = find_sd_card()
if not sd_card:
    print("No SD Card Found")
else:
    print(f"SD Card: {sd_card}")
    photos = find_photos(sd_card)
    print(f"Found {len(photos)} photos")
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