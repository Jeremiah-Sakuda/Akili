"""
Run the Akili API server with uvicorn.
"""

from __future__ import annotations

import os

import uvicorn

from akili.api.app import app


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
