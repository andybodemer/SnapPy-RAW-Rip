import struct
import os
import binascii
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

# --- CONSTANTS ---
CANON_CMT1_UUID = "85c0b687820f11e08111f4ce462b6a48"

# Enable debug mode to see all raw tags
DEBUG_MODE = False

# TIFF5 Canon MakerNote Tags (decoded)
TIFF5_CANON_TAGS = {
    6: "CameraModel",           # Redundant with Model
    7: "FirmwareVersion",
    149: "LensModel",           # Redundant with LensModel
    150: "LensManufacturingCode",
}

# Fields to include in output (whitelist)
OUTPUT_FIELDS = {
    # Camera & Date/Time
    'Make', 'Model', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
    # Lens Information
    'LensModel', 'LensSpecification', 'LensSerialNumber', 'LensMake',
    'FirmwareVersion', 'LensManufacturingCode',
    # Exposure Settings
    'ExposureTime', 'FNumber', 'ISOSpeedRatings', 'ShutterSpeedValue',
    'ApertureValue', 'ExposureBiasValue', 'FocalLength', 'FocalLengthIn35mmFilm',
    'ExposureProgram', 'ExposureMode', 'MeteringMode', 'WhiteBalance', 'Flash',
    # Image Info
    'ImageWidth', 'ImageLength', 'Orientation',
    # Creator Info
    'Artist', 'Copyright',
}

# TIFF Tag Reference (Expanded)
TIFF_TAGS = {
    254: "NewSubfileType",
    255: "SubfileType",
    256: "ImageWidth",
    257: "ImageLength",
    258: "BitsPerSample",
    259: "Compression",
    262: "PhotometricInterpretation",
    270: "ImageDescription",
    271: "Make",
    272: "Model",
    273: "StripOffsets",
    274: "Orientation",
    277: "SamplesPerPixel",
    278: "RowsPerStrip",
    279: "StripByteCounts",
    282: "XResolution",
    283: "YResolution",
    284: "PlanarConfiguration",
    296: "ResolutionUnit",
    305: "Software",
    306: "DateTime",
    315: "Artist",
    316: "HostComputer",
    320: "ColorMap",
    338: "ExtraSamples",
    33432: "Copyright",
    33434: "ExposureTime",
    33437: "FNumber",
    34665: "ExifIFDPointer",
    34850: "ExposureProgram",
    34855: "ISOSpeedRatings",
    36867: "DateTimeOriginal",
    36868: "DateTimeDigitized",
    37377: "ShutterSpeedValue",
    37378: "ApertureValue",
    37380: "ExposureBiasValue",
    37381: "MaxApertureValue",
    37383: "MeteringMode",
    37384: "LightSource",
    37385: "Flash",
    37386: "FocalLength",
    37510: "UserComment",
    40961: "ColorSpace",
    40962: "PixelXDimension",
    40963: "PixelYDimension",
    41486: "FocalPlaneXResolution",
    41487: "FocalPlaneYResolution",
    41488: "FocalPlaneResolutionUnit",
    41989: "FocalLengthIn35mmFilm",
    41990: "SceneCaptureType",
    42034: "LensSpecification",
    42035: "LensMake",
    42036: "LensModel",
    42037: "LensSerialNumber",
    # Additional Canon/EXIF tags
    37121: "ComponentsConfiguration",
    37122: "CompressedBitsPerPixel",
    37500: "MakerNote",
    37520: "SubSecTime",
    37521: "SubSecTimeOriginal",
    37522: "SubSecTimeDigitized",
    40960: "FlashpixVersion",
    41495: "SensingMethod",
    41728: "FileSource",
    41729: "SceneType",
    41985: "CustomRendered",
    41986: "ExposureMode",
    41987: "WhiteBalance",
    41988: "DigitalZoomRatio",
    41991: "GainControl",
    41992: "Contrast",
    41993: "Saturation",
    41994: "Sharpness",
    42016: "ImageUniqueID",
    42080: "CompositeImage",
    42081: "SourceImageNumberOfCompositeImage",
    42082: "SourceExposureTimesOfCompositeImage",
    # IFD pointers
    34853: "GPSIFDPointer",
    40965: "InteroperabilityIFDPointer",
    330: "SubIFDs",
}

def clean_user_input(user_input):
    """
    Cleans user input by removing quotes, improper slashes, and extra spaces.
    """
    # Remove leading/trailing whitespace
    cleaned = user_input.strip()

    # Remove quotes (single and double)
    cleaned = cleaned.replace('"', '').replace("'", '')

    # Remove extra spaces
    cleaned = ' '.join(cleaned.split())

    # Handle escaped spaces (if any)
    cleaned = cleaned.replace('\\ ', ' ')

    return cleaned

def is_cr3_file(file_path):
    """
    Checks if a file is a valid CR3 file by examining its header.
    CR3 files start with ftyp box containing 'crx' brand.
    """
    try:
        with open(file_path, 'rb') as f:
            # Read first 20 bytes
            header = f.read(20)
            if len(header) < 20:
                return False

            # Check for ftyp box and crx brand
            box_size = struct.unpack('>I', header[0:4])[0]
            box_type = header[4:8].decode('utf-8', errors='ignore')
            brand = header[8:12].decode('utf-8', errors='ignore')

            return box_type == 'ftyp' and 'crx' in brand
    except Exception:
        return False

def format_tag_value(tag_type, count, value_data, file_handle, data_offset):
    """
    Formats TIFF tag values based on their type.
    Types: 1=BYTE, 2=ASCII, 3=SHORT, 4=LONG, 5=RATIONAL, 7=UNDEFINED, 9=SLONG, 10=SRATIONAL
    """
    try:
        if tag_type == 2:  # ASCII
            if count <= 4:
                return value_data.split(b'\x00')[0].decode('utf-8', errors='ignore')
            else:
                current_pos = file_handle.tell()
                offset = struct.unpack('<I', value_data)[0]
                file_handle.seek(data_offset + offset)
                string = file_handle.read(count).split(b'\x00')[0].decode('utf-8', errors='ignore')
                file_handle.seek(current_pos)
                return string

        elif tag_type == 3:  # SHORT
            if count == 1:
                return struct.unpack('<H', value_data[0:2])[0]
            else:
                current_pos = file_handle.tell()
                offset = struct.unpack('<I', value_data)[0]
                file_handle.seek(data_offset + offset)
                values = [struct.unpack('<H', file_handle.read(2))[0] for _ in range(count)]
                file_handle.seek(current_pos)
                return values if len(values) > 1 else values[0]

        elif tag_type == 4:  # LONG
            return struct.unpack('<I', value_data)[0]

        elif tag_type == 5:  # RATIONAL
            current_pos = file_handle.tell()
            offset = struct.unpack('<I', value_data)[0]
            file_handle.seek(data_offset + offset)
            numerator = struct.unpack('<I', file_handle.read(4))[0]
            denominator = struct.unpack('<I', file_handle.read(4))[0]
            file_handle.seek(current_pos)
            if denominator == 0:
                return 0
            return numerator / denominator

        elif tag_type == 10:  # SRATIONAL (signed)
            current_pos = file_handle.tell()
            offset = struct.unpack('<I', value_data)[0]
            file_handle.seek(data_offset + offset)
            numerator = struct.unpack('<i', file_handle.read(4))[0]
            denominator = struct.unpack('<i', file_handle.read(4))[0]
            file_handle.seek(current_pos)
            if denominator == 0:
                return 0
            return numerator / denominator

        else:
            return struct.unpack('<I', value_data)[0]

    except Exception as e:
        return f"<parse error: {e}>"

def extract_metadata(file_path):
    """
    Extracts metadata from a CR3 file.
    Returns a dictionary of metadata or None if extraction fails.
    """
    metadata = {}

    try:
        with open(file_path, 'rb') as f:
            file_size = os.path.getsize(file_path)

            while f.tell() < file_size:
                current_pos = f.tell()
                header = f.read(8)
                if len(header) < 8:
                    break

                box_size, = struct.unpack('>I', header[0:4])
                box_type = header[4:8].decode('utf-8', errors='ignore')

                header_len = 8
                if box_size == 1:
                    box_size, = struct.unpack('>Q', f.read(8))
                    header_len = 16

                if box_size == 0 or box_size > file_size:
                    break

                if box_type == 'uuid':
                    uuid_hex = binascii.hexlify(f.read(16)).decode('utf-8')
                    if DEBUG_MODE:
                        print(f"[DEBUG] Found UUID box: {uuid_hex}")
                    if uuid_hex == CANON_CMT1_UUID:
                        # Found Canon UUID, search for ALL TIFF headers
                        search_start = current_pos + header_len + 16
                        f.seek(search_start)
                        chunk = f.read(200000)  # Search 200KB instead of 50KB

                        # Find all TIFF headers
                        tiff_indices = []
                        search_pos = 0
                        while True:
                            tiff_idx = chunk.find(b'\x49\x49\x2A\x00', search_pos)
                            if tiff_idx == -1:
                                break
                            tiff_indices.append(tiff_idx)
                            search_pos = tiff_idx + 1

                        if DEBUG_MODE:
                            print(f"[DEBUG] Found {len(tiff_indices)} TIFF header(s) in Canon UUID")

                        # Process each TIFF structure
                        for tiff_num, tiff_idx in enumerate(tiff_indices):
                            if DEBUG_MODE:
                                print(f"\n[DEBUG] === Processing TIFF #{tiff_num + 1} at offset +{tiff_idx} ===")

                            tiff_base = search_start + tiff_idx

                            try:
                                # Parse IFD0
                                f.seek(tiff_base + 4)
                                ifd_offset, = struct.unpack('<I', f.read(4))

                                # Skip invalid IFD offsets
                                if ifd_offset > 50000 or ifd_offset < 8:
                                    if DEBUG_MODE:
                                        print(f"[DEBUG] Skipping - invalid IFD offset: {ifd_offset}")
                                    continue

                                f.seek(tiff_base + ifd_offset)
                                num_entries, = struct.unpack('<H', f.read(2))

                                # Skip TIFFs with suspiciously high entry counts (likely corrupt)
                                if num_entries > 200:
                                    if DEBUG_MODE:
                                        print(f"[DEBUG] Skipping - too many entries: {num_entries}")
                                    continue

                                if DEBUG_MODE:
                                    print(f"[DEBUG] IFD0 has {num_entries} entries")

                                # Parse main IFD tags
                                for i in range(num_entries):
                                    entry = f.read(12)
                                    if len(entry) < 12:
                                        break

                                    tag_id, tag_type, count = struct.unpack('<HHI', entry[0:8])
                                    value_data = entry[8:12]

                                    # Use TIFF5 Canon tags for TIFF5, otherwise standard TIFF tags
                                    if tiff_num == 4:  # TIFF5 (0-indexed, so tiff_num 4 = TIFF5)
                                        tag_name = TIFF5_CANON_TAGS.get(tag_id, TIFF_TAGS.get(tag_id, f"UnknownTag_{tag_id}"))
                                    else:
                                        tag_name = TIFF_TAGS.get(tag_id, f"UnknownTag_{tag_id}")
                                    prefix = f"TIFF{tiff_num+1}_" if tiff_num > 0 else ""

                                    if DEBUG_MODE:
                                        print(f"[DEBUG]   Tag {tag_id} ({tag_name}): Type={tag_type}, Count={count}")

                                    # Special handling for ExifIFDPointer
                                    if tag_id == 34665:
                                        exif_offset = struct.unpack('<I', value_data)[0]
                                        if DEBUG_MODE:
                                            print(f"[DEBUG]   Following EXIF IFD pointer to offset {exif_offset}")
                                        # Parse EXIF IFD
                                        current_ifd_pos = f.tell()
                                        f.seek(tiff_base + exif_offset)
                                        exif_entries, = struct.unpack('<H', f.read(2))

                                        if DEBUG_MODE:
                                            print(f"[DEBUG]   EXIF IFD has {exif_entries} entries")

                                        for j in range(exif_entries):
                                            exif_entry = f.read(12)
                                            if len(exif_entry) < 12:
                                                break

                                            exif_tag_id, exif_tag_type, exif_count = struct.unpack('<HHI', exif_entry[0:8])
                                            exif_value_data = exif_entry[8:12]

                                            exif_tag_name = TIFF_TAGS.get(exif_tag_id, f"UnknownExifTag_{exif_tag_id}")

                                            if DEBUG_MODE:
                                                print(f"[DEBUG]     EXIF Tag {exif_tag_id} ({exif_tag_name}): Type={exif_tag_type}, Count={exif_count}")

                                            exif_value = format_tag_value(exif_tag_type, exif_count, exif_value_data, f, tiff_base)
                                            metadata[f"{prefix}{exif_tag_name}"] = exif_value

                                        f.seek(current_ifd_pos)

                                    # Handle SubIFDs pointer
                                    elif tag_id == 330:
                                        sub_ifd_offset = struct.unpack('<I', value_data)[0]
                                        if DEBUG_MODE:
                                            print(f"[DEBUG]   Following SubIFD pointer to offset {sub_ifd_offset}")
                                        current_ifd_pos = f.tell()
                                        f.seek(tiff_base + sub_ifd_offset)
                                        sub_entries, = struct.unpack('<H', f.read(2))

                                        if DEBUG_MODE:
                                            print(f"[DEBUG]   SubIFD has {sub_entries} entries")

                                        for k in range(sub_entries):
                                            sub_entry = f.read(12)
                                            if len(sub_entry) < 12:
                                                break

                                            sub_tag_id, sub_tag_type, sub_count = struct.unpack('<HHI', sub_entry[0:8])
                                            sub_value_data = sub_entry[8:12]

                                            sub_tag_name = TIFF_TAGS.get(sub_tag_id, f"UnknownSubTag_{sub_tag_id}")

                                            if DEBUG_MODE:
                                                print(f"[DEBUG]     SubIFD Tag {sub_tag_id} ({sub_tag_name}): Type={sub_tag_type}, Count={sub_count}")

                                            sub_value = format_tag_value(sub_tag_type, sub_count, sub_value_data, f, tiff_base)
                                            metadata[f"{prefix}SubIFD_{sub_tag_name}"] = sub_value

                                        f.seek(current_ifd_pos)

                                    else:
                                        value = format_tag_value(tag_type, count, value_data, f, tiff_base)
                                        metadata[f"{prefix}{tag_name}"] = value

                            except Exception as e:
                                if DEBUG_MODE:
                                    print(f"[DEBUG] Error parsing TIFF #{tiff_num + 1}: {e}")
                                continue

                        if metadata:
                            return metadata

                # Navigate boxes
                if box_type in ['moov', 'trak', 'mdia', 'minf', 'stbl']:
                    f.seek(current_pos + header_len)
                else:
                    f.seek(current_pos + box_size)

    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return None

    return None

def write_sidecar(cr3_path, metadata):
    """
    Writes metadata to a sidecar text file next to the CR3 file.
    """
    # Generate sidecar filename
    cr3_file = Path(cr3_path)
    sidecar_path = cr3_file.parent / f"{cr3_file.stem}_metadata.txt"

    try:
        with open(sidecar_path, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write(f"CR3 METADATA EXTRACTION\n")
            f.write(f"Source File: {cr3_file.name}\n")
            f.write(f"Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")

            # Helper function to find field in metadata (check with and without TIFF prefix)
            def find_field(field_name):
                # Check exact match first
                if field_name in metadata:
                    return field_name, metadata[field_name]
                # Check for TIFF-prefixed versions (prefer higher TIFF numbers as they're more accurate)
                for tiff_num in range(10, 0, -1):
                    prefixed = f"TIFF{tiff_num}_{field_name}"
                    if prefixed in metadata:
                        return prefixed, metadata[prefixed]
                return None, None

            # Write metadata in organized sections
            camera_lens_fields = ['Make', 'Model', 'LensModel', 'LensSpecification']
            exposure_fields = ['ExposureTime', 'FNumber', 'ISOSpeedRatings', 'ShutterSpeedValue',
                             'ApertureValue', 'ExposureBiasValue', 'FocalLength', 'FocalLengthIn35mmFilm',
                             'ExposureProgram', 'ExposureMode', 'MeteringMode', 'WhiteBalance', 'Flash']
            datetime_fields = ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']
            image_fields = ['ImageWidth', 'ImageLength', 'Orientation', 'Artist', 'Copyright']
            serial_fields = ['LensSerialNumber', 'LensManufacturingCode', 'FirmwareVersion']

            used_keys = set()

            # Camera & Lens info
            f.write("CAMERA & LENS:\n")
            f.write("-" * 60 + "\n")
            for field in camera_lens_fields:
                key, value = find_field(field)
                if key:
                    f.write(f"{field:30s}: {value}\n")
                    used_keys.add(key)
            f.write("\n")

            # Exposure settings
            f.write("EXPOSURE SETTINGS:\n")
            f.write("-" * 60 + "\n")
            for field in exposure_fields:
                key, value = find_field(field)
                if key:
                    # Format exposure time as fraction if needed
                    if field == 'ExposureTime' and isinstance(value, float) and value < 1:
                        f.write(f"{field:30s}: 1/{int(1/value)}s ({value:.6f}s)\n")
                    else:
                        f.write(f"{field:30s}: {value}\n")
                    used_keys.add(key)
            f.write("\n")

            # Date/Time info
            datetime_found = []
            for field in datetime_fields:
                key, value = find_field(field)
                if key and key not in used_keys:
                    datetime_found.append((field, value))
                    used_keys.add(key)

            if datetime_found:
                f.write("DATE & TIME:\n")
                f.write("-" * 60 + "\n")
                for field, value in datetime_found:
                    f.write(f"{field:30s}: {value}\n")
                f.write("\n")

            # Image dimensions and creator info
            image_found = []
            for field in image_fields:
                key, value = find_field(field)
                if key and key not in used_keys:
                    image_found.append((field, value))
                    used_keys.add(key)

            if image_found:
                f.write("IMAGE & CREATOR INFO:\n")
                f.write("-" * 60 + "\n")
                for field, value in image_found:
                    f.write(f"{field:30s}: {value}\n")
                f.write("\n")

            # Serial numbers and firmware (bottom section)
            serial_found = []
            for field in serial_fields:
                key, value = find_field(field)
                if key and key not in used_keys:
                    serial_found.append((field, value))
                    used_keys.add(key)

            if serial_found:
                f.write("SERIAL NUMBERS & FIRMWARE:\n")
                f.write("-" * 60 + "\n")
                for field, value in serial_found:
                    f.write(f"{field:30s}: {value}\n")

        return sidecar_path

    except Exception as e:
        print(f"Error writing sidecar file: {e}")
        return None

def process_cr3_file(file_path):
    """
    Processes a single CR3 file: validates, extracts metadata, writes sidecar.
    """
    file_path = Path(file_path)

    # Check if sidecar already exists
    sidecar_path = file_path.parent / f"{file_path.stem}_metadata.txt"
    if sidecar_path.exists():
        print(f"  [SKIP] Sidecar already exists: {sidecar_path.name}")
        return False

    # Validate CR3
    if not is_cr3_file(file_path):
        print(f"  [ERROR] Not a valid CR3 file: {file_path.name}")
        return False

    print(f"  [PROCESSING] {file_path.name}")

    # Extract metadata
    metadata = extract_metadata(file_path)

    if metadata is None or len(metadata) == 0:
        print(f"  [ERROR] Failed to extract metadata from {file_path.name}")
        return False

    # Write sidecar
    sidecar = write_sidecar(file_path, metadata)

    if sidecar:
        print(f"  [SUCCESS] Created sidecar: {sidecar.name}")
        print(f"  [INFO] Extracted {len(metadata)} metadata fields")
        return True
    else:
        return False

def batch_process_folder(folder_path):
    """
    Batch processes all CR3 files in a folder (non-recursive).
    """
    folder = Path(folder_path)

    if not folder.is_dir():
        print(f"[ERROR] Not a valid directory: {folder_path}")
        return

    # Find all CR3 files
    cr3_files = list(folder.glob('*.cr3')) + list(folder.glob('*.CR3'))

    if not cr3_files:
        print(f"[INFO] No CR3 files found in {folder_path}")
        return

    print(f"\n[INFO] Found {len(cr3_files)} CR3 file(s) in {folder.name}/")
    print("="*60)

    success_count = 0
    for cr3_file in cr3_files:
        if process_cr3_file(cr3_file):
            success_count += 1

    print("="*60)
    print(f"[COMPLETE] Processed {success_count}/{len(cr3_files)} files successfully\n")

def select_file_or_folder():
    """
    Opens a tkinter dialog to select a CR3 file or folder.
    Returns the selected path or None if cancelled.
    """
    # Create and hide the root window
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)  # Bring dialog to front

    print("\nSelect an option:")
    print("  [1] Select a single CR3 file")
    print("  [2] Select a folder of CR3 files")
    print("  [3] Enter path manually")

    choice = input("\nEnter choice (1/2/3): ").strip()

    selected_path = None

    if choice == '1':
        selected_path = filedialog.askopenfilename(
            title="Select CR3 File",
            filetypes=[("CR3 Files", "*.cr3 *.CR3"), ("All Files", "*.*")]
        )
    elif choice == '2':
        selected_path = filedialog.askdirectory(
            title="Select Folder Containing CR3 Files"
        )
    elif choice == '3':
        root.destroy()
        return input("Enter CR3 file path OR folder path: ").strip()
    else:
        print("[ERROR] Invalid choice.")
        root.destroy()
        return None

    root.destroy()
    return selected_path if selected_path else None


def main():
    """
    Main function: handles user input and routing.
    """
    print("\n" + "="*60)
    print("CR3 METADATA EXTRACTOR")
    print("="*60)
    print("\nThis tool extracts metadata from Canon CR3 files and creates")
    print("human-readable sidecar text files.\n")

    user_input = select_file_or_folder()

    # Clean the input
    cleaned_path = clean_user_input(user_input) if user_input else None

    if not cleaned_path:
        print("[ERROR] No path provided.")
        return

    path = Path(cleaned_path)

    if not path.exists():
        print(f"[ERROR] Path does not exist: {cleaned_path}")
        return

    # Determine if file or folder
    if path.is_file():
        print(f"\n[INFO] Processing single file...")
        process_cr3_file(path)
    elif path.is_dir():
        batch_process_folder(path)
    else:
        print(f"[ERROR] Invalid path type: {cleaned_path}")

if __name__ == "__main__":
    main()
