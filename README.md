# 🔍 Disk Usage Analyzer

A modern, fast, and intuitive web-based disk usage analyzer built with Python and Flask. This tool helps you identify large folders on your system and manage your storage efficiently.

![Interface Preview](https://img.shields.io/badge/Status-Active-brightgreen)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Flask](https://img.shields.io/badge/Framework-Flask-lightgrey)

## ✨ Features

-   **⚡ High Performance & Multi-threading:** Fast multi-threaded directory traversal and folder sizing with automatic thread balancing.
-   **🚀 Multi-Stage Duplicate Finder:** Advanced 3-tier duplicate detection (File size grouping → 8 KB header hash → parallel confirmation hash). Eliminates 99% of non-duplicates without reading file contents, guaranteeing 0 false positives.
-   **⚡ Real-Time Async Background Worker:** Duplicate scans run asynchronously in background threads with live metrics (files/s, progress %, cancel at any time).
-   **💾 Smart In-Memory & Client Caching:** Folder visits and sizing results are cached for near-instant navigation back and forth.
-   **📂 Visual Navigation & File Support:** Interactive breadcrumbs, folder and loose file display with sortable columns (by Name and by Size).
-   **📊 Accurate Sizing & Wasted Space:** Shows recursive sizes and total reclaimable wasted space across duplicate groups.
-   **🖥️ Integrated Actions:**
    -   Open any folder or select files directly in Windows File Explorer.
    -   Safe deletion via `send2trash` (Recycle Bin).
    -   One-click smart duplicate selection (keeps recommended originals).
-   **🎨 Modern Dark UI:** Responsive interface with live progress bars, metrics cards, and smooth CSS transitions.
-   **🔗 Windows Junction & Long Path Safety:** Handles `\\?\` long paths and safely skips junction loops / reparse points.

## 🚀 Getting Started

### Prerequisites

-   Python 3.8 or higher
-   pip (Python package manager)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/BeanEden/Disk_Analyser.git
    cd Disk_Analyser
    ```

2.  **Set up a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application

Simply run the batch script:
```bash
run_app.bat
```
Or start it manually:
```bash
python app.py
```
The application will be available at `http://127.0.0.1:5000`.

## 🛠️ Tech Stack

-   **Backend:** Python 3, Flask
-   **Frontend:** HTML5, CSS3 (Vanilla), JavaScript (ES6)
-   **Icons:** Font Awesome 6
-   **Fonts:** Inter (Google Fonts)

## 🛡️ Safety Notes

-   **Exclusions:** By default, system-critical folders (like `$Recycle.Bin`, `System Volume Information`) and development folders (`node_modules`, `.git`, `__pycache__`) are excluded from scanning for speed and safety.
-   **Deletion:** The delete function attempts to move folders to the Recycle Bin. If `send2trash` is not installed, it will perform a permanent deletion. Use with caution.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---
Developed with ❤️ for efficient data management.
