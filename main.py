import sys
import json
from extractor import extract


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <file_path> [--json]")
        return

    result = extract(sys.argv[1])

    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("-" * 50)
        for key, value in result.items():
            print(f"{key:25}: {value}")
        print("-" * 50)


if __name__ == "__main__":
    main()