"""CLI for querygpt."""
import sys, json, argparse
from .core import Querygpt

def main():
    parser = argparse.ArgumentParser(description="QueryGPT — Natural Language to SQL. Convert plain English questions into optimized SQL queries.")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "run", "info"])
    parser.add_argument("--input", "-i", default="")
    args = parser.parse_args()
    instance = Querygpt()
    if args.command == "status":
        print(json.dumps(instance.get_stats(), indent=2))
    elif args.command == "run":
        print(json.dumps(instance.process(input=args.input or "test"), indent=2, default=str))
    elif args.command == "info":
        print(f"querygpt v0.1.0 — QueryGPT — Natural Language to SQL. Convert plain English questions into optimized SQL queries.")

if __name__ == "__main__":
    main()
