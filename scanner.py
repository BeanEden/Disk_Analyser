import os
import time
import hashlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Security exclusions: paths that must never be scanned / deleted
SYSTEM_PROTECTED = {
    '$Recycle.Bin', 'System Volume Information'
}

# Default noise exclusions (can be bypassed by user toggles)
DEFAULT_NOISE = {
    '.git', 'node_modules', '__pycache__', 'venv', '.venv'
}

# Cache for folder sizes: { (norm_path, show_hidden, include_appdata): (timestamp, size) }
FOLDER_SIZE_CACHE = {}
CACHE_TTL = 300  # 5 minutes

def clear_cache(path=None):
    """Clears the folder size cache completely or for a specific path."""
    global FOLDER_SIZE_CACHE
    if path is None:
        FOLDER_SIZE_CACHE.clear()
    else:
        norm_path = os.path.normpath(path).lower()
        keys_to_remove = [k for k in FOLDER_SIZE_CACHE if k[0].startswith(norm_path)]
        for k in keys_to_remove:
            FOLDER_SIZE_CACHE.pop(k, None)

def to_win_long_path(path):
    """Prepends Windows long path prefix if on NT and not already present."""
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        try:
            return '\\\\?\\' + os.path.abspath(path)
        except Exception:
            return path
    return path

def clean_win_path(path):
    """Removes Windows long path prefix for display and normal usage."""
    if path.startswith('\\\\?\\'):
        return path[4:]
    return path

def is_link_or_junction(entry):
    """Checks if entry is a symlink or Windows junction to prevent recursion loops."""
    try:
        if entry.is_symlink():
            return True
        if hasattr(entry, 'is_junction') and entry.is_junction():
            return True
    except (OSError, PermissionError):
        return True
    return False

def get_folder_size(path, show_hidden=True, include_appdata=True, use_cache=True):
    """
    Calculates the total size of a folder iteratively.
    Optimized to use os.scandir and avoid redundant syscalls.
    """
    clean_p = clean_win_path(path)
    norm_key = (os.path.normpath(clean_p).lower(), bool(show_hidden), bool(include_appdata))
    
    now = time.time()
    if use_cache and norm_key in FOLDER_SIZE_CACHE:
        cached_time, cached_size = FOLDER_SIZE_CACHE[norm_key]
        if now - cached_time < CACHE_TTL:
            return cached_size

    total_size = 0
    scan_root = to_win_long_path(clean_p)
    stack = [scan_root]

    while stack:
        current_path = stack.pop()
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        name = entry.name
                        if name in SYSTEM_PROTECTED:
                            continue
                        if not include_appdata and name.lower() == 'appdata':
                            continue
                        if not show_hidden and name.startswith('.'):
                            continue
                        if name in DEFAULT_NOISE:
                            continue
                        if is_link_or_junction(entry):
                            continue
                            
                        if entry.is_file(follow_symlinks=False):
                            total_size += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue

    if use_cache:
        FOLDER_SIZE_CACHE[norm_key] = (now, total_size)

    return total_size

def format_size(size):
    """Formats bytes into human readable string."""
    if size < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def scan_directory(start_path, show_hidden=True, include_appdata=True, force_refresh=False):
    """
    Scans the directory and returns subdirectories and loose files with their sizes.
    Uses multi-threading and caching for high performance.
    """
    if force_refresh:
        clear_cache(start_path)

    abs_start_path = os.path.abspath(start_path)
    scan_path = to_win_long_path(abs_start_path)
    
    dirs = []
    files = []
    
    try:
        with os.scandir(scan_path) as it:
            for entry in it:
                try:
                    name = entry.name
                    if name in SYSTEM_PROTECTED:
                        continue
                    if not include_appdata and name.lower() == 'appdata':
                        continue
                    if not show_hidden and name.startswith('.'):
                        continue
                    if name in DEFAULT_NOISE:
                        continue
                    if is_link_or_junction(entry):
                        continue
                        
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        files.append(entry)
                except (PermissionError, OSError):
                    continue
    except Exception as e:
        print(f"Error accessing {start_path}: {e}")
        return []

    results = []

    # Process loose files in the directory directly (instantaneous)
    for f_entry in files:
        try:
            f_size = f_entry.stat(follow_symlinks=False).st_size
            clean_p = clean_win_path(f_entry.path)
            results.append({
                'name': f_entry.name,
                'path': clean_p,
                'parent': abs_start_path,
                'type': 'file',
                'size': f_size,
                'size_readable': format_size(f_size)
            })
        except (PermissionError, OSError):
            continue

    # Process subdirectories in parallel
    if dirs:
        max_workers = min(24, max(4, (os.cpu_count() or 2) * 2))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_entry = {
                executor.submit(get_folder_size, entry.path, show_hidden, include_appdata, not force_refresh): entry 
                for entry in dirs
            }
            
            for future in future_to_entry:
                entry = future_to_entry[future]
                try:
                    size = future.result()
                    clean_p = clean_win_path(entry.path)
                    results.append({
                        'name': entry.name,
                        'path': clean_p,
                        'parent': abs_start_path,
                        'type': 'folder',
                        'size': size,
                        'size_readable': format_size(size)
                    })
                except Exception as e:
                    print(f"Error scanning {entry.path}: {e}")

    # Sort descending by size (largest first)
    results.sort(key=lambda x: x['size'], reverse=True)
    return results

def open_file_explorer(path):
    """Opens the file explorer at the given path."""
    clean_p = clean_win_path(path)
    if os.path.exists(clean_p):
        try:
            if os.path.isfile(clean_p):
                os.system(f'explorer.exe /select,"{clean_p}"')
            else:
                os.startfile(clean_p)
            return True
        except Exception:
            return False
    return False

def get_header_hash(filepath, header_size=8192):
    """Reads the first header_size bytes of a file and returns MD5 hash."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(header_size)
            hasher.update(buf)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None

def get_full_file_hash(filepath, blocksize=131072):
    """Reads the entire file in 128KB blocks and returns full MD5 hash."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(blocksize):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None

def find_duplicates(start_path=None, show_hidden=True, include_appdata=True, status_callback=None, cancel_event=None):
    """
    High-performance duplicate detection engine in 3 stages:
    1. Fast tree traversal & grouping strictly by file size (instant filtering of 99% files).
    2. Fast header hash (first 8KB) in parallel using ThreadPoolExecutor.
    3. Full hash confirmation in parallel for collision groups.
    
    Supports real-time progress updates and graceful cancellation.
    """
    if not start_path:
        start_path = os.path.expanduser("~")

    abs_start_path = os.path.abspath(start_path)
    scan_root = to_win_long_path(abs_start_path)

    def is_cancelled():
        return cancel_event is not None and cancel_event.is_set()

    def notify(stage, stage_name, message, progress=0, files_scanned=0, speed=0, extra=None):
        if status_callback:
            data = {
                'stage': stage,
                'stage_name': stage_name,
                'message': message,
                'progress': round(progress, 1),
                'files_scanned': files_scanned,
                'speed': round(speed, 1),
            }
            if extra:
                data.update(extra)
            status_callback(data)

    start_time = time.time()
    files_by_size = defaultdict(list)
    files_scanned = 0
    dirs_scanned = 0
    last_notify_time = start_time

    notify(1, "Indexation", "Étape 1/3 : Analyse rapide des tailles de fichiers...", progress=0)

    # -------------------------------------------------------------
    # STAGE 1: Fast directory traversal and group by file size
    # -------------------------------------------------------------
    stack = [scan_root]

    while stack:
        if is_cancelled():
            notify(0, "Annulé", "Analyse annulée par l'utilisateur.")
            return []

        current_path = stack.pop()
        dirs_scanned += 1

        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        name = entry.name
                        if name in SYSTEM_PROTECTED:
                            continue
                        if not include_appdata and name.lower() == 'appdata':
                            continue
                        if not show_hidden and name.startswith('.'):
                            continue
                        if name in DEFAULT_NOISE:
                            continue
                        if is_link_or_junction(entry):
                            continue

                        if entry.is_file(follow_symlinks=False):
                            size = entry.stat(follow_symlinks=False).st_size
                            if size > 0:  # Exclude 0-byte empty files
                                clean_path = clean_win_path(entry.path)
                                files_by_size[size].append(clean_path)
                            files_scanned += 1
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue

        now = time.time()
        if now - last_notify_time >= 0.3:
            elapsed = max(0.001, now - start_time)
            speed = files_scanned / elapsed
            notify(1, "Indexation", 
                   f"Étape 1/3 : {files_scanned:,} fichiers analysés ({int(speed):,} fich/s)...", 
                   progress=min(95, (files_scanned / 50000) * 100),
                   files_scanned=files_scanned, 
                   speed=speed)
            last_notify_time = now

    potential_by_size = {size: paths for size, paths in files_by_size.items() if len(paths) > 1}
    total_potential_files = sum(len(paths) for paths in potential_by_size.values())

    if not potential_by_size or is_cancelled():
        notify(3, "Terminé", "Aucun doublon trouvé.", progress=100, files_scanned=files_scanned)
        return []

    notify(2, "Filtrage rapide", 
           f"Étape 2/3 : {total_potential_files:,} candidats trouvés. Vérification des en-têtes (8 Ko)...", 
           progress=10, 
           files_scanned=files_scanned,
           extra={'potential_count': total_potential_files})

    # -------------------------------------------------------------
    # STAGE 2: Fast header hash (first 8 KB) in parallel
    # -------------------------------------------------------------
    candidate_list = []
    for size, paths in potential_by_size.items():
        for p in paths:
            candidate_list.append((size, p))

    header_results = defaultdict(list)
    processed_candidates = 0
    max_workers = min(24, max(4, (os.cpu_count() or 2) * 2))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(get_header_hash, to_win_long_path(p)): (size, p)
            for size, p in candidate_list
        }

        for future in as_completed(future_to_item):
            if is_cancelled():
                executor.shutdown(wait=False, cancel_futures=True)
                notify(0, "Annulé", "Analyse annulée par l'utilisateur.")
                return []

            size, p = future_to_item[future]
            processed_candidates += 1
            try:
                h_hash = future.result()
                if h_hash:
                    header_results[(size, h_hash)].append(p)
            except Exception:
                continue

            now = time.time()
            if now - last_notify_time >= 0.3:
                pct = (processed_candidates / total_potential_files) * 100
                notify(2, "Filtrage rapide", 
                       f"Étape 2/3 : En-têtes vérifiés ({processed_candidates:,}/{total_potential_files:,})...",
                       progress=pct,
                       files_scanned=files_scanned)
                last_notify_time = now

    confirmed_header_groups = {k: v for k, v in header_results.items() if len(v) > 1}
    
    if not confirmed_header_groups or is_cancelled():
        notify(3, "Terminé", "Aucun doublon trouvé.", progress=100, files_scanned=files_scanned)
        return []

    # -------------------------------------------------------------
    # STAGE 3: Full hash confirmation in parallel
    # -------------------------------------------------------------
    notify(3, "Confirmation", 
           "Étape 3/3 : Confirmation minutieuse des fichiers identiques...", 
           progress=0, 
           files_scanned=files_scanned)

    final_duplicate_groups = []
    files_to_full_hash = []
    
    for (size, h_hash), paths in confirmed_header_groups.items():
        if size <= 8192:
            final_duplicate_groups.append({
                'size': size,
                'size_readable': format_size(size),
                'wasted_size': (len(paths) - 1) * size,
                'wasted_readable': format_size((len(paths) - 1) * size),
                'files': paths
            })
        else:
            for p in paths:
                files_to_full_hash.append((size, p))

    total_full_hash = len(files_to_full_hash)
    if total_full_hash > 0:
        full_hash_results = defaultdict(list)
        processed_full = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(get_full_file_hash, to_win_long_path(p)): (size, p)
                for size, p in files_to_full_hash
            }

            for future in as_completed(future_to_item):
                if is_cancelled():
                    executor.shutdown(wait=False, cancel_futures=True)
                    notify(0, "Annulé", "Analyse annulée par l'utilisateur.")
                    return []

                size, p = future_to_item[future]
                processed_full += 1
                try:
                    f_hash = future.result()
                    if f_hash:
                        full_hash_results[(size, f_hash)].append(p)
                except Exception:
                    continue

                now = time.time()
                if now - last_notify_time >= 0.3:
                    pct = (processed_full / total_full_hash) * 100
                    notify(3, "Confirmation", 
                           f"Étape 3/3 : Confirmation des gros fichiers ({processed_full:,}/{total_full_hash:,})...",
                           progress=pct,
                           files_scanned=files_scanned)
                    last_notify_time = now

        for (size, f_hash), paths in full_hash_results.items():
            if len(paths) > 1:
                final_duplicate_groups.append({
                    'size': size,
                    'size_readable': format_size(size),
                    'wasted_size': (len(paths) - 1) * size,
                    'wasted_readable': format_size((len(paths) - 1) * size),
                    'files': paths
                })

    final_duplicate_groups.sort(key=lambda x: x['wasted_size'], reverse=True)

    total_wasted = sum(g['wasted_size'] for g in final_duplicate_groups)
    notify(3, "Terminé", 
           f"Terminé ! {len(final_duplicate_groups)} groupes de doublons détectés ({format_size(total_wasted)} récupérables).", 
           progress=100,
           files_scanned=files_scanned,
           extra={
               'duplicates_count': len(final_duplicate_groups),
               'wasted_size': total_wasted,
               'wasted_readable': format_size(total_wasted)
           })

    return final_duplicate_groups
