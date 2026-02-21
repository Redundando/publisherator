import sys
import argparse
from pathlib import Path
from logorator import Logger
from .publisher import Publisher, PublishError


def main():
    parser = argparse.ArgumentParser(
        description="One-command Python package publishing",
        prog="publisherator"
    )
    
    parser.add_argument(
        "bump_type",
        nargs="?",
        default="patch",
        choices=["major", "minor", "patch"],
        help="Version bump type (default: patch)"
    )
    
    parser.add_argument(
        "--message", "-m",
        help="Custom commit message (default: 'Bump version to X.Y.Z')"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )
    
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Skip git operations (only publish to PyPI)"
    )
    
    parser.add_argument(
        "--skip-pypi",
        action="store_true",
        help="Skip PyPI upload (only push to git)"
    )
    
    args = parser.parse_args()
    
    # Get current directory
    package_dir = Path.cwd()
    
    try:
        publisher = Publisher(package_dir)
        new_version = publisher.publish(
            bump_type=args.bump_type,
            commit_msg=args.message,
            skip_git=args.skip_git,
            skip_pypi=args.skip_pypi,
            dry_run=args.dry_run
        )
        
        if args.dry_run:
            print(f"\n✓ Would publish version {new_version}")
        else:
            print(f"\n✓ Successfully published version {new_version}")
        
        sys.exit(0)
        
    except PublishError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
