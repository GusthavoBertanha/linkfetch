from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

from linkfetch import __version__
from linkfetch.downloader import DownloadError, Downloader
from linkfetch.resolvers import resolve


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="linkfetch",
        description="Download one link per process with retries and resume support.",
    )
    result.add_argument("url", help="HTTP or HTTPS URL")
    result.add_argument("-o", "--output", type=Path, default=Path.cwd(), help="destination directory (default: current directory)")
    result.add_argument("--name", help="final file name")
    result.add_argument("--retries", type=int, default=5, help="retry count after a failure (default: 5)")
    result.add_argument("--timeout", type=float, default=30, help="network timeout in seconds (default: 30)")
    result.add_argument("--no-resume", action="store_true", help="do not resume partial files")
    result.add_argument("--quiet", action="store_true", help="hide progress output")
    result.add_argument(
        "--resolve-only",
        action="store_true",
        help="resolve and display the destination without downloading",
    )
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        item = resolve(args.url)
        if args.resolve_only:
            parsed = urlsplit(item.url)
            print(f"Destination: {parsed.scheme}://{parsed.netloc}{parsed.path}")
            print(f"Name: {item.filename or '(provided by server)'}")
            print(f"Transport: {item.transport}")
            print(f"Session headers: {', '.join(sorted(item.headers)) or '(none)'}")
            return 0
        downloader = Downloader(
            args.output,
            retries=args.retries,
            timeout=args.timeout,
            resume=not args.no_resume,
            quiet=args.quiet,
        )
        destination = downloader.download(item, args.name)
    except (ValueError, DownloadError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. The partial file was preserved for resuming.", file=sys.stderr)
        return 130

    print(f"Completed: {destination}")
    return 0
