from flask import Flask, render_template, jsonify, request
import os
import shutil
import threading
import time
from scanner import (
    scan_directory, 
    open_file_explorer, 
    find_duplicates, 
    clear_cache
)

app = Flask(__name__)

# Default start path (User's home directory)
DEFAULT_PATH = os.path.expanduser("~")

# State for asynchronous duplicate scan job
SCAN_LOCK = threading.Lock()
SCAN_CANCEL_EVENT = threading.Event()
SCAN_THREAD = None

SCAN_JOB = {
    "status": "idle",       # "idle", "running", "completed", "cancelled", "error"
    "stage": 0,
    "stage_name": "",
    "message": "En attente...",
    "progress": 0,
    "files_scanned": 0,
    "speed": 0,
    "path": DEFAULT_PATH,
    "duplicates": [],
    "duplicates_count": 0,
    "wasted_readable": "0 B",
    "error": None
}

def duplicate_scan_worker(target_path, show_hidden=True, include_appdata=True):
    """Background worker for duplicate file scanning."""
    global SCAN_JOB
    
    def on_status_update(data):
        with SCAN_LOCK:
            SCAN_JOB["stage"] = data.get("stage", SCAN_JOB["stage"])
            SCAN_JOB["stage_name"] = data.get("stage_name", SCAN_JOB["stage_name"])
            SCAN_JOB["message"] = data.get("message", SCAN_JOB["message"])
            SCAN_JOB["progress"] = data.get("progress", SCAN_JOB["progress"])
            SCAN_JOB["files_scanned"] = data.get("files_scanned", SCAN_JOB["files_scanned"])
            SCAN_JOB["speed"] = data.get("speed", SCAN_JOB["speed"])
            if "duplicates_count" in data:
                SCAN_JOB["duplicates_count"] = data["duplicates_count"]
            if "wasted_readable" in data:
                SCAN_JOB["wasted_readable"] = data["wasted_readable"]

    try:
        results = find_duplicates(
            start_path=target_path,
            show_hidden=show_hidden,
            include_appdata=include_appdata,
            status_callback=on_status_update,
            cancel_event=SCAN_CANCEL_EVENT
        )
        
        with SCAN_LOCK:
            if SCAN_CANCEL_EVENT.is_set():
                SCAN_JOB["status"] = "cancelled"
                SCAN_JOB["message"] = "Analyse annulée par l'utilisateur."
            else:
                SCAN_JOB["status"] = "completed"
                SCAN_JOB["duplicates"] = results
                SCAN_JOB["duplicates_count"] = len(results)
                SCAN_JOB["progress"] = 100
    except Exception as e:
        with SCAN_LOCK:
            SCAN_JOB["status"] = "error"
            SCAN_JOB["error"] = str(e)
            SCAN_JOB["message"] = f"Erreur : {str(e)}"

@app.route('/')
def index():
    return render_template('index.html', current_path=DEFAULT_PATH)

@app.route('/api/scan')
def scan():
    path = request.args.get('path', DEFAULT_PATH)
    force_refresh = request.args.get('refresh', '0') in ['1', 'true', 'True']
    show_hidden = request.args.get('hidden', '1') in ['1', 'true', 'True']
    include_appdata = request.args.get('appdata', '1') in ['1', 'true', 'True']
    
    if not os.path.exists(path):
        return jsonify({'error': 'Path does not exist'}), 400
    
    data = scan_directory(path, show_hidden=show_hidden, include_appdata=include_appdata, force_refresh=force_refresh)
    return jsonify({'path': path, 'folders': data, 'hidden': show_hidden, 'appdata': include_appdata})

@app.route('/api/open', methods=['POST'])
def open_folder():
    data = request.json or {}
    path = data.get('path')
    if path and open_file_explorer(path):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Could not open folder'}), 400

@app.route('/api/delete', methods=['POST'])
def delete_folder():
    data = request.json or {}
    path = data.get('path')
    
    if not path:
        return jsonify({'success': False, 'error': 'No path provided'}), 400
        
    # Safety check: Prevent deleting root or critical system paths
    if len(path) < 4 or path.lower() in ['c:\\', 'c:\\windows', 'c:\\users']:
        return jsonify({'success': False, 'error': 'Operation not allowed on this path'}), 403

    try:
        if os.path.exists(path):
            try:
                from send2trash import send2trash
                send2trash(path)
            except ImportError:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            
            # Invalidate parent cache
            parent_dir = os.path.dirname(path)
            clear_cache(parent_dir)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Path not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scan-duplicates/start', methods=['POST'])
def start_duplicate_scan():
    global SCAN_THREAD, SCAN_JOB, SCAN_CANCEL_EVENT
    data = request.json or {}
    target_path = data.get('path') or request.args.get('path') or DEFAULT_PATH
    show_hidden = data.get('hidden', True)
    include_appdata = data.get('appdata', True)

    if not os.path.exists(target_path):
        return jsonify({'success': False, 'error': 'Le dossier spécifié n\'existe pas.'}), 400

    with SCAN_LOCK:
        if SCAN_JOB["status"] == "running":
            return jsonify({
                'success': True, 
                'message': 'Un scan est déjà en cours d\'exécution.',
                'already_running': True
            })

        SCAN_CANCEL_EVENT.clear()
        SCAN_JOB = {
            "status": "running",
            "stage": 1,
            "stage_name": "Démarrage",
            "message": "Démarrage de l'analyse...",
            "progress": 0,
            "files_scanned": 0,
            "speed": 0,
            "path": target_path,
            "duplicates": [],
            "duplicates_count": 0,
            "wasted_readable": "0 B",
            "error": None
        }

        SCAN_THREAD = threading.Thread(
            target=duplicate_scan_worker, 
            args=(target_path, show_hidden, include_appdata), 
            daemon=True
        )
        SCAN_THREAD.start()

    return jsonify({'success': True, 'message': 'Scan démarré avec succès.', 'path': target_path})

@app.route('/api/scan-duplicates/status')
def duplicate_scan_status():
    with SCAN_LOCK:
        # Return a copy of the current state
        status_copy = dict(SCAN_JOB)
    return jsonify(status_copy)

@app.route('/api/scan-duplicates/cancel', methods=['POST'])
def cancel_duplicate_scan():
    SCAN_CANCEL_EVENT.set()
    with SCAN_LOCK:
        if SCAN_JOB["status"] == "running":
            SCAN_JOB["message"] = "Annulation en cours..."
    return jsonify({'success': True, 'message': 'Demande d\'annulation envoyée.'})

# Backward compatibility routes
@app.route('/api/scan-status')
def scan_status():
    with SCAN_LOCK:
        return jsonify({
            'status': SCAN_JOB['status'].capitalize(),
            'message': SCAN_JOB['message'],
            'progress': SCAN_JOB['progress']
        })

@app.route('/api/scan-duplicates')
def scan_duplicates_legacy():
    # If legacy client calls GET /api/scan-duplicates, check if running, else trigger start
    with SCAN_LOCK:
        if SCAN_JOB["status"] == "completed":
            return jsonify({
                'success': True, 
                'duplicates': SCAN_JOB['duplicates'], 
                'scanned_path': SCAN_JOB['path']
            })
        elif SCAN_JOB["status"] == "running":
            return jsonify({'success': False, 'message': 'Scan déjà en cours', 'status': 'running'})
            
    # Trigger start and wait for completion for legacy callers
    target_path = request.args.get('path') or DEFAULT_PATH
    start_duplicate_scan()
    # Wait up to 5 seconds, otherwise return status running
    for _ in range(10):
        time.sleep(0.5)
        with SCAN_LOCK:
            if SCAN_JOB["status"] == "completed":
                return jsonify({
                    'success': True, 
                    'duplicates': SCAN_JOB['duplicates'], 
                    'scanned_path': SCAN_JOB['path']
                })
    return jsonify({'success': True, 'message': 'Scan en cours d\'arrière-plan', 'status': 'running'})

@app.route('/api/delete-files', methods=['POST'])
def delete_files():
    data = request.json or {}
    files = data.get('files', [])
    
    if not files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400
        
    deleted_count = 0
    errors = []
    
    for path in files:
        if len(path) < 10 or path.lower() in ['c:\\', 'c:\\windows', 'c:\\users']:
            errors.append(f"{path}: Operation not allowed")
            continue
            
        try:
            if os.path.exists(path):
                try:
                    from send2trash import send2trash
                    send2trash(path)
                except ImportError:
                    os.remove(path)
                deleted_count += 1
        except Exception as e:
            errors.append(f"{path}: {str(e)}")
            
    # Invalidate cache
    clear_cache()
    
    # Also update in-memory duplicate list to remove deleted files
    with SCAN_LOCK:
        if SCAN_JOB["duplicates"]:
            deleted_set = set(files)
            updated_dups = []
            for group in SCAN_JOB["duplicates"]:
                remaining = [f for f in group['files'] if f not in deleted_set]
                if len(remaining) > 1:
                    group['files'] = remaining
                    updated_dups.append(group)
            SCAN_JOB["duplicates"] = updated_dups
            SCAN_JOB["duplicates_count"] = len(updated_dups)

    return jsonify({
        'success': True, 
        'deleted_count': deleted_count,
        'errors': errors
    })

@app.route('/api/clear-cache', methods=['POST'])
def clear_api_cache():
    clear_cache()
    return jsonify({'success': True, 'message': 'Cache vidé avec succès.'})

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    def shutdown_server():
        time.sleep(1)
        os._exit(0)
    
    thread = threading.Thread(target=shutdown_server)
    thread.start()
    return jsonify({'success': True, 'message': 'Server shutting down...'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
