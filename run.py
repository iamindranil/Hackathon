"""
Entrypoint runner for RESOLV.AI Dispute Investigation Agent.
Allows running the server with: python run.py
"""

import os
import sys

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  RESOLV.AI // Card & Payment Dispute Investigation Agent")
    print("  Server starting at: http://127.0.0.1:8000")
    print("=" * 60 + "\n")
    uvicorn.run("backend.api.app:app", host="127.0.0.1", port=8000, reload=True)
