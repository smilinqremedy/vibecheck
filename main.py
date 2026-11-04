#!/usr/bin/env python3
"""VibeCheck AI - Main Entry Point.

Festival Feedback Detective: Evidence-grounded review intelligence CLI.
Run without arguments for interactive CLI, or with flags for automated audits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.cli import VibeCheckCLI
from app.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VibeCheck AI: Festival Feedback Detective & Evidence-Grounded Review Intelligence CLI"
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Path to initial CSV or JSON review file to import immediately on startup",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Optional path to custom .env configuration file",
    )
    args = parser.parse_args()

    config = Config(env_path=Path(args.config)) if args.config else Config()
    app = VibeCheckCLI(config=config)

    if args.file:
        print(f"[*] Pre-loading reviews from: {args.file}")
        try:
            from app.ingest import import_reviews
            res = import_reviews(args.file)
            app.reviews.extend(res.accepted)
            print(f"[+] Loaded {res.num_accepted} reviews ({res.num_rejected} rejected).")
        except Exception as exc:
            print(f"[!] Warning: Could not pre-load '{args.file}': {exc}")

    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting cleanly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
