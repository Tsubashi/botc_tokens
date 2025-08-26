# This file contains the configuration for compiling the botc_tokens GUI application
# using Nuitka. It specifies the entry point, compilation mode, plugins, and other
# options.

# NOTE: Make sure to run nuitka from the root of the repository, not from this directory.

# Compilation mode, standalone everywhere, except on macOS there app bundle
# nuitka-project: --mode=app
#
# Debugging options, controlled via environment variable at compile time.
# nuitka-project-if: {OS} == "Windows":
#   nuitka-project-if: os.getenv("DEBUG_COMPILATION", "no") == "yes":
#     nuitka-project: --windows-console-mode=hide
#   nuitka-project-else:
#     nuitka-project: --windows-console-mode=disabled

# The PySide6 plugin covers qt-plugins
# nuitka-project: --enable-plugin=pyside6

# Set the application info
# nuitka-project: --product-name=botc_tokens
# nuitka-project: --output-filename=botc_tokens-gui
# nuitka-project: --windows-icon-from-ico=packaging/icon.png
# nuitka-project: --macos-app-icon=packaging/icon.png


from botc_tokens.gui.__main__ import main

if __name__ == "__main__":
    main()