pipe.py Script Runner

This repository contains a single Python script, pipe.py, which manages its dependencies using the UV dependency management tool. This approach ensures the script runs reliably on any machine with minimal setup.

🚀 Getting Started

The only requirement is to have UV installed on your system.

1. Install UV

UV is a fast, modern tool that replaces pip and virtualenv.

🐧 macOS & Linux (using curl)

Bash

curl -LsSf https://astral.sh/uv/install.sh | sh

    Note: This command will install uv into ~/.cargo/bin/ and add it to your system's PATH.

🪟 Windows (using PowerShell)

PowerShell

(Invoke-WebRequest -Uri https://astral.sh/uv/install.ps1 -UseBasicParsing).Content | Invoke-Expression

    Note: This command will download and install uv.exe and update your system's PATH.

2. Run the Script

Once UV is installed, you can run the script. UV will automatically read the dependencies from the # /// script block in pipe.py, create an isolated environment, install the necessary packages (matplotlib, numpy, etc.), and execute the file.
Bash

uv run pipe.py

    The first run will take a few seconds to set up the environment.

    Subsequent runs will be instantaneous, as the environment will be reused.
