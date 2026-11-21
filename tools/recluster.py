"""Re-cluster an existing run against a (new) scene vocabulary.

    python tools/recluster.py --db var/topcharts_llm.db \
        --category custom_app_store_top_charts --threshold 0.32 --min-size 3

Scenes are recomputed from each atom's text via ``classify_scene``; atoms are not
re-extracted, so this costs nothing and takes seconds. The run's clusters are
replaced in place (atom_cluster + clusters), and atom.scene is updated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.cluster import cluster_atoms  # noqa: E402
from painradar.config import category as get_category  # noqa: E402
from painradar.schema import PainAtom  # noqa: E402
from painradar.store import Store  # noqa: E402
from painradar.taxonomy import classify_scene  # noqa: E402


def _atom(row) -> PainAtom:
    return PainAtom(
        atom_id=row["atom_id"], comment_uid=row["comment_uid"], quote=row["quote"],
        span_start=row["span_start"], span_end=row["span_end"], match_score=row["match_score"],
        scene=row["scene"], trigger=row["trigger"], job=row["job"], obstacle=row["obstacle"],
        workaround=row["workaround"], cost_type=row["cost_type"], cost_estimate=row["cost_estimate"],
        persona=row["persona"], intensity=row["intensity"], expression=row["expression"],
        level=row["level"], wtp_level=row["wtp_level"], wtp_quote=row["wtp_quote"],
        domain=row["domain"], confidence=row["confidence"], model_version=row["model_version"],
        prompt_version=row["prompt_version"], taxonomy_version=row["taxonomy_version"],
        run_id=row["run_id"],
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--run", default=None)
    ap.add_argument("--threshold", type=float, default=0.32)
    ap.add_argument("--min-size", type=int, default=3)
    args = ap.parse_args()

    spec = get_category(args.category)
    store = Store(args.db)
    row = (
        store._conn.execute("SELECT run_id FROM runs WHERE run_id=?", (args.run,)).fetchone()
        if args.run
        else store._conn.execute(
            "SELECT run_id FROM runs WHERE category=? ORDER BY created_at DESC LIMIT 1",
            (args.category,),
        ).fetchone()
    )
    if row is None:
        print("run not found", file=sys.stderr)
        return 1
    run_id = row["run_id"]
    rows = store._conn.execute("SELECT * FROM atoms WHERE run_id=?", (run_id,)).fetchall()
    if not rows:
        print("no atoms in run", file=sys.stderr)
        return 1

    atoms = []
    scene_updates = []
    for row in rows:
        scene = classify_scene(f"{row['quote']} {row['obstacle'] or ''}", spec)
        atom = _atom({**dict(row), "scene": scene})
        atoms.append(atom)
        scene_updates.append((scene, row["atom_id"]))

    result = cluster_atoms(atoms, threshold=args.threshold, min_size=args.min_size)
    store._conn.execute("DELETE FROM atom_cluster WHERE run_id=?", (run_id,))
    store._conn.execute("DELETE FROM clusters WHERE run_id=?", (run_id,))
    store._conn.executemany(
        "UPDATE atoms SET scene=? WHERE atom_id=? AND run_id=?", [(s, a, run_id) for s, a in scene_updates]
    )
    store._conn.commit()
    store.insert_clusters(
        run_id,
        [
            {
                "cluster_id": c.cluster_id,
                "label": c.label,
                "size": c.size,
                "noise": c.noise,
                "medoid_atom_id": c.medoid_atom_id,
                "members": c.members,
            }
            for c in result.clusters
        ],
        result.assignments,
    )

    stats = json.loads(
        store._conn.execute("SELECT stats_json FROM runs WHERE run_id=?", (run_id,)).fetchone()[0]
    )
    stats.update(
        {
            "clusters": len(result.clusters),
            "noise_rate": round(result.noise_rate, 4),
            "threshold": args.threshold,
            "min_size": args.min_size,
            "reclustered": True,
            "scene_count": len({a.scene for a in atoms}),
        }
    )
    store._conn.execute(
        "UPDATE runs SET stats_json=? WHERE run_id=?", (json.dumps(stats, ensure_ascii=False), run_id)
    )
    store._conn.commit()

    print(f"run {run_id}: atoms={len(atoms)} clusters={len(result.clusters)} "
          f"noise={result.noise_rate:.3f} scenes={stats['scene_count']}")
    for c in sorted(result.clusters, key=lambda x: x.size, reverse=True)[:12]:
        print(f"  {c.size:>3}  {c.label}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
