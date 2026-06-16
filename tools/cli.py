"""NovelClaw Unified CLI.

Usage:
    novelclaw translate --ch 42
    novelclaw validate --ch 42
    novelclaw glossary --sync
    novelclaw search "曹星"
    novelclaw dashboard
"""
import argparse
import sys
from pathlib import Path


def main():
    """Main entry point for `novelclaw` CLI."""
    parser = argparse.ArgumentParser(
        prog="novelclaw",
        description="Cross-language web novel translation toolkit",
    )
    parser.add_argument(
        "--novel", "-n",
        default="global-descent",
        help="Novel slug (default: global-descent)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # translate
    t = sub.add_parser("translate", help="Translate a chapter")
    t.add_argument("--ch", type=int, required=True, help="Chapter number")
    t.add_argument("--mock", action="store_true", help="Use mock output (no LLM call)")
    t.add_argument("--provider", choices=["haiku", "gemini", "claude"],
                   help="LLM provider (default: LLM_PROVIDER env or haiku)")

    # validate
    v = sub.add_parser("validate", help="Validate a translated chapter")
    v.add_argument("--ch", type=int, required=True, help="Chapter number")
    v.add_argument("--fix", action="store_true", help="Auto-fix issues")

    # batch-validate
    bv = sub.add_parser("batch-validate", help="Validate all chapters")

    # glossary
    g = sub.add_parser("glossary", help="Glossary management")
    g.add_argument("--sync", action="store_true",
                   help="Sync format_spec.json -> style_rules.yml")
    g.add_argument("--search", type=str, help="Search glossary terms")

    # search (FTS5)
    s = sub.add_parser("search", help="Full-text search across chapters")
    s.add_argument("query", type=str, help="Search query")
    s.add_argument("--limit", type=int, default=5)

    # dashboard
    d = sub.add_parser("dashboard", help="Launch the reader dashboard")

    # status
    st = sub.add_parser("status", help="Show translation progress")

    # version
    sub.add_parser("version", help="Show version")

    args = parser.parse_args()

    # Dispatch to underlying tools
    if args.command == "translate":
        from tools.translate import main as translate_main
        sys.argv = ["translate.py", f"--ch={args.ch}"]
        if args.mock:
            sys.argv.append("--mock")
        if args.provider:
            import os
            os.environ["LLM_PROVIDER"] = args.provider
        translate_main()

    elif args.command == "validate":
        from tools.validate_chapter import main as validate_main
        sys.argv = ["validate_chapter.py", str(args.ch)]
        if args.fix:
            sys.argv.append("--fix")
        validate_main()

    elif args.command == "batch-validate":
        from tools.batch_validate import main as batch_validate_main
        batch_validate_main()

    elif args.command == "glossary":
        from tools.glossary import main as glossary_main
        if args.sync:
            sys.argv = ["glossary.py", "--sync", f"--novel={args.novel}"]
        elif args.search:
            sys.argv = ["glossary.py", "--search", args.search, f"--novel={args.novel}"]
        else:
            sys.argv = ["glossary.py", f"--novel={args.novel}"]
        glossary_main()

    elif args.command == "search":
        from tools.chapter_search import main as search_main
        sys.argv = ["chapter_search.py", "search", args.query, f"--limit={args.limit}"]
        search_main()

    elif args.command == "dashboard":
        import subprocess
        import os
        reader_dir = Path(__file__).parent.parent / "reader"
        print("Starting reader dashboard...")
        subprocess.run(["node", "server.js"], cwd=str(reader_dir))

    elif args.command == "status":
        from tools.glossary import load_format_spec
        spec = load_format_spec(args.novel)
        if spec:
            print(f"Novel: {args.novel}")
            print(f"Format spec sections: {list(spec.keys())}")
        else:
            print(f"No format_spec.json found for '{args.novel}'")

    elif args.command == "version":
        try:
            import importlib.metadata
            version = importlib.metadata.version("novelclaw")
        except Exception:
            version = "1.0.0 (dev)"
        print(f"NovelClaw v{version}")


if __name__ == "__main__":
    main()
