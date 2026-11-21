"""Developer utility: sweep the clustering threshold for one category."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.cluster import cluster_atoms  # noqa: E402
from painradar.config import DB_PATH, category as get_category  # noqa: E402
from painradar.extract import RuleExtractor  # noqa: E402
from painradar.schema import RawItem  # noqa: E402
from painradar.store import Store  # noqa: E402


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else "pet_water_fountain"
    store = Store(DB_PATH)
    spec = get_category(key)
    items = store.items(key)
    ex = RuleExtractor(spec)
    atoms = []
    for row in items:
        raw = RawItem(row["platform"], row["item_id"], row["url"], row["text_masked"],
                      row["published_at"], row["category"])
        a = ex.extract(raw, row["text_masked"], row["comment_uid"], "tune")
        if a:
            atoms.append(a)
    print(f"{key}: items={len(items)} atoms={len(atoms)}")
    for th in (0.10, 0.14, 0.18, 0.22, 0.26, 0.30, 0.34):
        res = cluster_atoms(atoms, threshold=th, min_size=3)
        sizes = sorted((c.size for c in res.clusters), reverse=True)
        print(f"  th={th:<5} clusters={len(res.clusters):<2} sizes={sizes} noise={res.noise_rate:.0%}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
