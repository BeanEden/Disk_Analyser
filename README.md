# 🔍 Disk Usage Analyzer

A modern, fast, and intuitive web-based disk usage analyzer built with Python and Flask. This tool helps you identify large folders on your system and manage your storage efficiently.

![Interface Preview](https://img.shields.io/badge/Status-Active-brightgreen)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Flask](https://img.shields.io/badge/Framework-Flask-lightgrey)

## ✨ Features

-   **⚡ High Performance:** Uses multi-threaded scanning to process large directories quickly.
-   **📂 Visual Navigation:** Interactive breadcrumbs and folder-based navigation.
-   **📊 Accurate Sizing:** Calculates recursive folder sizes with human-readable formatting (KB, MB, GB).
-   **🖥️ Integrated Actions:**
    -   Open any scanned folder directly in Windows File Explorer.
    -   Delete unwanted folders securely (uses `send2trash` for safety).
-   **🎨 Modern UI:** Clean, responsive design with dark mode aesthetics and smooth transitions.
-   **🔗 Long Path Support:** Specifically optimized for Windows long path handling.

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
