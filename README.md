# ImagingTriage

## Program Name: ImagingTriage
**Version:** 2025-06-28.0
**Author:** Andrea Orlando
**Purpose:** This script analyzes a folder containing image files and their .XMP sidecars, extracts rating and color label metadata, and moves the files into subfolders. It supports configurable file types.

## Features:
- Process images based on XMP metadata (ratings and labels).
- Organize files into subfolders based on extracted metadata.
- Gather files back from subfolders to the main directory (undo operation).
- Configurable supported file extensions (e.g., ARW, JPG, TIFF, HEIF).
- Multilingual support (English and Italian).
- User documentation accessible directly from the application.

## License:
This project is licensed under the GPLv3 License. See the `LICENSE` file for more details.

## How to Use:

### Prerequisites:
- Python 3.x installed.
- `PyInstaller` library installed (`pip install pyinstaller`).

### Running the Application:
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/ImagingTriage.git
    cd ImagingTriage
    ```
    (Replace `YOUR_USERNAME` with your actual GitHub username and `ImagingTriage.git` with your repository URL)

2.  **Navigate to the application directory:**
    ```bash
    cd ImagingTriage
    ```

3.  **Run directly (for development/testing):**
    ```bash
    python imaging_triage.py
    ```

### Building the Executable:
To create a standalone executable (`.exe` for Windows), use the provided `build.bat` script:

1.  **Navigate to the application directory:**
    ```bash
    cd ImagingTriage
    ```

2.  **Run the build script:**
    ```bash
    build.bat
    ```
    This will create the executable in the `dist` folder within the `ImagingTriage` directory.

### Application Interface:
-   **Folder to process:** Select the directory containing your image files.
-   **Process:** Analyzes and organizes files based on XMP metadata.
-   **Gather files back from subfolders (Undo):** Moves files from generated subfolders back to the main processing folder.
-   **Config:** Opens a configuration window to change language and supported file extensions.
-   **Help:** Opens the user documentation in your default web browser.
-   **Exit:** Closes the application.

## Configuration:
The application uses `config.xml` to store settings such as language and supported file extensions. This file is automatically created/updated when you change settings via the "Config" button.

## Contributing:
Feel free to fork the repository, make improvements, and submit pull requests.
