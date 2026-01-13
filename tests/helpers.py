from pathlib import Path

from deepdiff import DeepDiff

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "assets"


def pretty_deepdiff(diff: DeepDiff):
    """
    Pretty print a deepdiff
    """
    print("\n=== CHANGED ITEMS ===")
    for path, change in diff.get('values_changed', {}).items():
        print(f"{path}:")
        print(f"  OLD: {change['old_value']}")
        print(f"  NEW: {change['new_value']}")
        print("-" * 50)

    print("\n=== ADDED ITEMS ===")
    for path, item in diff.get('iterable_item_added', {}).items():
        print(f"{path}: {item}")
        print("-" * 50)

    print("\n=== REMOVED ITEMS ===")
    for path, item in diff.get('iterable_item_removed', {}).items():
        print(f"{path}: {item}")
        print("-" * 50)


def load_asset(alias: str) -> str:
    """
    Load a file by it's name with or without extension
    Optionally parse it as Json
    """
    p = FIXTURES_DIR / alias
    # Direct search, then search with any extension
    if not p.exists():
        matches = list(FIXTURES_DIR.glob(f"{alias}.*"))
        if matches:
            p = matches[0]
        else:
            p = FIXTURES_DIR / f"{alias}.json"

    if not p.exists():
        raise FileNotFoundError(
            f"No fixture found for alias {alias!r} in {FIXTURES_DIR}")

    text = p.read_text(encoding="utf-8")
    return text
