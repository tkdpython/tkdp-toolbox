"""Entry point for tkdp_toolbox when invoked as python3 -m tkdp_toolbox."""

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="tkdp_toolbox - Swiss army knife toolbox for a devops engineer."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Print hello world.",
    )
    args = parser.parse_args()

    if args.test:
        print("hello world")


if __name__ == "__main__":
    main()
