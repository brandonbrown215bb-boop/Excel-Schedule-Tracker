# main.py
import faulthandler
import os
import sys
import traceback

faulthandler.enable()  # Dump Python + C stack trace on segfault

import yaml
from PyQt5.QtWidgets import QApplication, QMessageBox

from gui.main_window import MainWindow


def main():
    print("Application starting...")
    # Determine the base path for the application (handles PyInstaller bundling)
    if getattr(sys, "frozen", False):
        # Running in a PyInstaller bundle
        application_path = os.path.dirname(sys.executable)
        print(f"Running as frozen executable. Application path: {application_path}")
    else:
        # Running as a script
        application_path = os.path.dirname(os.path.abspath(__file__))
        print(f"Running as script. Application path: {application_path}")

    config_path = os.path.join(application_path, "config.yaml")
    print(f"Looking for config.yaml at: {config_path}")

    # Create QApplication first so QMessageBox works for early error dialogs
    app = QApplication(sys.argv)
    print("QApplication created.")

    if not os.path.exists(config_path):
        print(f"Error: config.yaml not found at {config_path}")
        QMessageBox.critical(
            None,
            "Configuration Error",
            f"config.yaml not found at:\n{config_path}\n\n"
            "Please ensure config.yaml is in the same directory as the application.",
        )
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        print("Error: config.yaml did not parse as a mapping.")
        QMessageBox.critical(
            None, "Configuration Error", "config.yaml did not parse as a valid mapping (dict)."
        )
        sys.exit(1)

    print("config.yaml loaded successfully.")

    # Pass config_path separately — do not inject into the config dict,
    # which gets serialized back to YAML and would pollute the file.
    window = MainWindow(config, config_path=config_path)
    print("MainWindow created.")
    window.show()
    print("MainWindow shown. Entering event loop...")
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")  # Keep console open on error
