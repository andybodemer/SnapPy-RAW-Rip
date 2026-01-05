#!/usr/bin/env python3

#imports
from pathlib import Path 
from datetime import datetime
import shutil


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
    ".pef", "ptx",
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
        print("\n=== Select Destinations ===")
        if destinations:
            for i, dest in enumerate(destinations, 1):
                print(f"  [{i}] {dest}")
        else: 
            print("  No saved destinations.")
        print("  [a] Add new destination")
        choice = input("\nEnter Selection (e.g. 1, 2, or a)").strip().lower()
        if choice == "a":
            new_dest = input("Enter full path: ").strip()
            if new_dest and Path(new_dest).exists():
                destinations.append(new_dest)
                save_destinations(destinations)
                print(f"Added: {new_dest}")
            else:
                print("Invalid path. Make sure the path exists.")
        else:
            try:
                indices = [int(x.strip()) for x in choice.split(",")]
                selected = [destinations[i - 1] for i in indices]
                if selected:
                    return selected
            except (ValueError, IndexError):
                print("Invalid selection. Try again?")

def get_shoot_name():
    """Asks the user for a shoot name to add to the destination folder"""
    return input("Enter shoot name for final folders (or press Enter to skip)").strip()

def confirm_copy(grouped_photos, destinations, shoot_name):
    """Show summary and ask user to confirm before copying."""
    total_photos = sum(len(photos) for photos in grouped_photos.values())
    print("\n=== Copy Summary ===")
    print(f"Photos: {total_photos}")
    print(f"Dates: {len(grouped_photos)}")
    print(f"Shoot name: '{shoot_name}'" if shoot_name else "Shoot name: (none)")
    print(f"Destinations ({len(destinations)}):")
    for dest in destinations:
        print(f"  - {dest}")
    answer = input("\nProceed with copy? (y/n): ").strip().lower()
    return answer == "y"

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
    print("\n=== Conflict Resolution ===")
    print("Some files already exist at the destination.")
    print("  [s] Skip - Don't copy files that already exist")
    print("  [o] Overwrite - Replace existing files")
    print("  [r] Rename - Add number to filename (e.g., IMG_001 (2).CR3)")
    
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
        print("\nCopy Complete!")
    else:
        print("\nCopy cancelled.")