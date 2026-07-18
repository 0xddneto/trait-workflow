"""Entrada do servidor MCP: py -3.12 server.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trait_workflow.mcp_server import main

if __name__ == "__main__":
    main()
