from __future__ import annotations

from datetime import datetime
from pathlib import Path


OUTPUT_FILE = Path(__file__).resolve().parent / "scheduler_test_output.txt"


def main() -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT_FILE.write_text(f"Scheduler test executed at {timestamp}\n", encoding="utf-8")
    print(f"Scheduler test output written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
