import csv
import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime
from html import escape
from io import BytesIO
from pathlib import Path

from services.evaluation import CASES, build_case_image
from services.image_processing import (
    create_pattern,
    render_effect_preview,
    render_grid_preview,
)


class HumanReviewPackError(ValueError):
    pass


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_results(path):
    with Path(path).open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    expected_ids = {case.case_id for case in CASES}
    actual_ids = {row.get("case_id") for row in rows}
    if len(rows) != 40 or actual_ids != expected_ids:
        raise HumanReviewPackError("Results table must contain exactly the fixed 40 cases.")
    return {row["case_id"]: row for row in rows}


def _render_html(entries, *, generated_at, results_filename):
    cards = []
    for entry in entries:
        cards.append(
            f"""
<article class="case" id="{escape(entry["case_id"])}">
  <h2>{escape(entry["case_id"])} · {escape(entry["category"])}</h2>
  <p>预期主体：{escape(entry["expected_subject"])}；风险：{escape(entry["expected_risk"])}；
     参数：{entry["grid_size"]}×{entry["grid_size"]} / {entry["color_limit"]} 色；
     实际：{entry["actual_color_count"]} 色 / {entry["total_beads"]} 颗。</p>
  <div class="images">
    <figure>
      <img src="{escape(entry["source_file"])}" alt="{escape(entry["case_id"])} 原图">
      <figcaption>原图</figcaption>
    </figure>
    <figure>
      <img src="{escape(entry["effect_file"])}" alt="{escape(entry["case_id"])} 拼豆效果">
      <figcaption>拼豆效果</figcaption>
    </figure>
    <figure>
      <img src="{escape(entry["grid_file"])}" alt="{escape(entry["case_id"])} 编号网格">
      <figcaption>编号网格</figcaption>
    </figure>
  </div>
  <p class="rubric">请在 CSV 中填写：主体是否可辨认、是否存在严重主体错误、
     是否可制作；如本图参与高级创作评测，再填写高级符合度和备注。</p>
</article>"""
        )
    return f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>我拼个豆 · 40 图人工质量评审包</title>
  <style>
    body {{
      margin: 0 auto; max-width: 1400px; padding: 24px;
      font: 16px/1.5 system-ui, sans-serif; color: #222;
    }}
    .notice {{ padding: 16px; border: 2px solid #9a5200; background: #fff4df; }}
    .case {{ margin: 28px 0; padding: 18px; border: 1px solid #bbb; break-inside: avoid; }}
    .images {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    figure {{ margin: 0; }}
    img {{
      display: block; width: 100%; height: 320px;
      object-fit: contain; background: #eee;
    }}
    figcaption {{ margin-top: 6px; text-align: center; font-weight: 700; }}
    .rubric {{ padding: 10px; background: #eef7ff; }}
    @media (max-width: 760px) {{ .images {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>我拼个豆 · 40 图人工质量评审包</h1>
  <p>生成时间：{escape(generated_at)}</p>
  <p class="notice"><strong>本页面不自动判定人工指标。</strong>
    逐图观察后，请编辑 <code>{escape(results_filename)}</code>：把人工字段由
    <code>pending</code> 改为真实结果，并填写备注。不要仅凭缩略图评分编号可读性，
    必要时打开原始 PNG。
  </p>
  <h2>统一评分口径</h2>
  <ol>
    <li>主体可辨认：不知道原图文件名的人仍能识别主要主体；</li>
    <li>严重主体错误：身份、肢体、轮廓或关键结构发生会误导制作的错误；</li>
    <li>可制作：网格连续、细节不过碎、材料数量合理，能够按图放豆；</li>
    <li>高级符合度：主体身份保留且完成指定修改，没有越界编辑或不安全内容。</li>
  </ol>
  {"".join(cards)}
</body>
</html>
"""


def build_human_review_pack(output_dir, *, results_path):
    destination = Path(output_dir)
    if destination.exists():
        raise HumanReviewPackError(f"Output directory already exists: {destination}")
    results = _load_results(results_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    generated_at = datetime.now(UTC).isoformat()
    try:
        for folder in ("sources", "effects", "grids"):
            (temporary / folder).mkdir()
        entries = []
        for case in CASES:
            source_bytes = build_case_image(case)
            pattern = create_pattern(
                BytesIO(source_bytes),
                size=case.grid_size,
                color_limit=case.color_limit,
            )
            source_path = temporary / "sources" / f"{case.case_id}.png"
            effect_path = temporary / "effects" / f"{case.case_id}.png"
            grid_path = temporary / "grids" / f"{case.case_id}.png"
            source_path.write_bytes(source_bytes)
            render_effect_preview(pattern.grid, palette=pattern.palette, bead_pixels=12).save(
                effect_path,
                format="PNG",
            )
            render_grid_preview(pattern.grid, palette=pattern.palette, cell_pixels=24).save(
                grid_path,
                format="PNG",
            )
            row = results[case.case_id]
            entries.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "expected_subject": case.expected_subject,
                    "expected_risk": case.expected_risk,
                    "grid_size": case.grid_size,
                    "color_limit": case.color_limit,
                    "actual_color_count": pattern.grid.color_count,
                    "total_beads": pattern.total_beads,
                    "material_consistency": row["material_consistency"],
                    "human_review": row["human_review"],
                    "source_file": f"sources/{case.case_id}.png",
                    "effect_file": f"effects/{case.case_id}.png",
                    "grid_file": f"grids/{case.case_id}.png",
                    "sha256": {
                        "source": _sha256(source_path),
                        "effect": _sha256(effect_path),
                        "grid": _sha256(grid_path),
                    },
                }
            )

        manifest = {
            "generated_at": generated_at,
            "case_count": len(entries),
            "source": "scikit-image bundled legal samples with deterministic transforms",
            "results_filename": Path(results_path).name,
            "cases": entries,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (temporary / "index.html").write_text(
            _render_html(
                entries,
                generated_at=generated_at,
                results_filename=Path(results_path).name,
            ),
            encoding="utf-8",
        )
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination
