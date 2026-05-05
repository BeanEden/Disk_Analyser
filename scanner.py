import os
import ctypes
from concurrent.futures import ThreadPoolExecutor

# Common folders to exclude for performance and relevance
DEFAULT_EXCLUSIONS = {
    '$Recycle.Bin', 'System Volume Information',
    '.git', 'node_modules', '__pycache__', 'venv', '.venv'
}

def get_folder_size(path):
    """Calculates the total size of a folder iteratively."""
    total_size = 0
    
    # Handle long paths on Windows
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        try:
            path = '\\\\?\\' + os.path.abspath(path)
        except:
            pass

    stack = [path]
    while stack:
        current_path = stack.pop()
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        # Recursive exclusion check
                        if entry.name in DEFAULT_EXCLUSIONS:
                            continue
                            
                        if entry.is_file(follow_symlinks=False):
                            # On Windows, st_size is usually available without a new syscall if cached
                            total_size += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue
    return total_size

def format_size(size):
    """Formats bytes into human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def scan_directory(start_path):
    """
    Scans the directory and returns a list of immediate subdirectories with their total sizes.
    """
    results = []
    
    try:
        # Resolve path and handle long paths
        abs_start_path = os.path.abspath(start_path)
        scan_path = abs_start_path
        if os.name == 'nt' and not scan_path.startswith('\\\\?\\'):
            scan_path = '\\\\?\\' + scan_path

        with os.scandir(scan_path) as it:
            dirs = []
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in DEFAULT_EXCLUSIONS:
                            continue
                        if entry.name.startswith('.'):
                            continue
                        dirs.append(entry)
                except (PermissionError, OSError):
                    continue

        # More aggressive threading for I/O bound tasks
        max_workers = min(32, (os.cpu_count() or 1) * 4)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Calculate sizes in parallel
            future_to_entry = {executor.submit(get_folder_size, entry.path): entry for entry in dirs}
            
            for future in future_to_entry:
                entry = future_to_entry[future]
                try:
                    size = future.result()
                    # Clean up the path for the results (remove long path prefix)
                    clean_path = entry.path.replace('\\\\?\\', '')
                    results.append({
                        'name': entry.name,
                        'path': clean_path,
                        'parent': abs_start_path,
                        'size': size,
                        'size_readable': format_size(size)
                    })
                except Exception as e:
                    print(f"Error scanning {entry.path}: {e}")

    except Exception as e:
        print(f"Error accessing {start_path}: {e}")
        return []

    # Sort by size descending
    results.sort(key=lambda x: x['size'], reverse=True)
    return results

def open_file_explorer(path):
    """Opens the file explorer at the given path."""
    # Remove prefix if present before check
    clean_path = path.replace('\\\\?\\', '')
    if os.path.exists(clean_path):
        os.startfile(clean_path)
        return True
    return False
