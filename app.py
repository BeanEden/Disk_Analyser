from flask import Flask, render_template, jsonify, request
import os
import shutil
import threading
import time
from scanner import scan_directory, open_file_explorer

app = Flask(__name__)

# Default start path (User's home directory)
DEFAULT_PATH = os.path.expanduser("~")

@app.route('/')
def index():
    return render_template('index.html', current_path=DEFAULT_PATH)

@app.route('/api/scan')
def scan():
    path = request.args.get('path', DEFAULT_PATH)
    if not os.path.exists(path):
        return jsonify({'error': 'Path does not exist'}), 400
    
    data = scan_directory(path)
    return jsonify({'path': path, 'folders': data})

@app.route('/api/open', methods=['POST'])
def open_folder():
    data = request.json
    path = data.get('path')
    if path and open_file_explorer(path):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Could not open folder'}), 400

@app.route('/api/delete', methods=['POST'])
def delete_folder():
    data = request.json
    path = data.get('path')
    
    if not path:
        return jsonify({'success': False, 'error': 'No path provided'}), 400
        
    # Safety check: Prevent deleting root or critical system paths just in case
    if len(path) < 4 or path.lower() in ['c:\\', 'c:\\windows', 'c:\\users']:
        return jsonify({'success': False, 'error': 'Operation not allowed on this path'}), 403

    try:
        if os.path.exists(path):
            # Send to recycle bin would be safer, but shutil.rmtree is permanent.
            # For this prototype, we'll use rmtree but maybe we should use send2trash if available?
            # User asked for "delete", let's stick to standard delete but be careful.
            # Actually, let's try to use send2trash if possible, otherwise rmtree.
            try:
                from send2trash import send2trash
                send2trash(path)
            except ImportError:
                shutil.rmtree(path)
            return jsonify({'success': True})
        else:
             return jsonify({'success': False, 'error': 'Path not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
