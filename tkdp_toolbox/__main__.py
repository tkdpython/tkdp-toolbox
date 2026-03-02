"""Entry point for tkdp_toolbox when invoked as python3 -m tkdp_toolbox."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="tkdp_toolbox - Swiss army knife toolbox for a devops engineer.")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # --- mirror subcommand ---
    mirror_parser = subparsers.add_parser(
        "mirror",
        help="Mirror container images and Helm charts to a private registry.",
    )
    mirror_parser.add_argument(
        "--sources",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to sources.yaml (default: ./sources.yaml).",
    )
    mirror_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )

    args = parser.parse_args()

    if args.command == "mirror":
        from tkdp_toolbox.mirror import run_mirror

        run_mirror(sources_path=args.sources, dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
