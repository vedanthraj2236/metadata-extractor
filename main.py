import json
import sys

from extractor import extract, privacy_report


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <file_path> [--json]")
        return
    path = sys.argv[1]
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        print(f"File not found: {path}")
        return
    result = extract(data, path)
    result["privacy"] = privacy_report(result)
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, default=str))
        return
    print("-" * 56)
    print(f"{'File':22}: {result['name']}  ({result['size_kb']} KB)")
    for k, v in result["details"].items():
        print(f"{k:22}: {v}")
    print(f"{'Privacy exposure':22}: {result['privacy']['score']}/100 ({result['privacy']['level']})")
    if result["error"]:
        print("Error:", result["error"])
    print("-" * 56)


if __name__ == "__main__":
    main()