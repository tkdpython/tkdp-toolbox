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

    # --- env-replace subcommand ---
    env_replace_parser = subparsers.add_parser(
        "env-replace",
        help="Recursively replace environment-specific values in .md, .yaml, and .yml files.",
    )
    env_replace_parser.add_argument(
        "--src-env",
        required=True,
        metavar="ENV",
        help="Source environment key defined in .far.yml (values to find).",
    )
    env_replace_parser.add_argument(
        "--dst-env",
        required=True,
        metavar="ENV",
        help="Destination environment key defined in .far.yml (values to substitute).",
    )
    env_replace_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory to start searching from (default: current directory).",
    )
    env_replace_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview replacements without modifying any files.",
    )

    args = parser.parse_args()

    if args.command == "mirror":
        from tkdp_toolbox.mirror import run_mirror

        run_mirror(sources_path=args.sources, dry_run=args.dry_run)
    elif args.command == "env-replace":
        from tkdp_toolbox.env_replace import run_env_replace

        run_env_replace(
            src_env=args.src_env,
            dst_env=args.dst_env,
            search_path=args.path,
            dry_run=args.dry_run,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
