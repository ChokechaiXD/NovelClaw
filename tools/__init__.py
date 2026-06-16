"""NovelClaw tools package.

Each tool is a standalone CLI script (python tools/<name>.py).
The tools/ directory is auto-added to sys.path by each script:

    sys.path.insert(0, str(Path(__file__).parent))
    from constants import NOVEL_ROOT

This __init__.py is a package marker — tools are NOT imported as
library modules (they use argparse + CLI, not library APIs).

Library-level imports (available for scripts that want cleaner imports):
    from tools.constants import NOVEL_ROOT, GLOSSARY_DIR
    from tools.schema import Chapter  # noqa: E402
from tools.chapter_io import load_chapter, save_chapter  # noqa: E402
    from tools.load_glossary import load_terms
"""
