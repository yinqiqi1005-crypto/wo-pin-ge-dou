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


REVIEW_FIELDS = (
    "human_subject_recognizable",
    "human_severe_subject_error",
    "human_making_feasible",
    "human_advanced_conformance",
)

REVIEW_CSS = """body {
  margin: 0 auto; max-width: 1400px; padding: 24px;
  font: 16px/1.5 system-ui, sans-serif; color: #222;
}
.notice { padding: 16px; border: 2px solid #9a5200; background: #fff4df; }
.toolbar {
  position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap;
  gap: 10px; align-items: center; padding: 12px; background: #fff; border: 2px solid #146c94;
}
button { padding: 10px 14px; font: inherit; font-weight: 700; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .55; }
.case { margin: 28px 0; padding: 18px; border: 1px solid #bbb; break-inside: avoid; }
.images { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
figure { margin: 0; }
img {
  display: block; width: 100%; height: 320px;
  object-fit: contain; background: #eee;
}
figcaption { margin-top: 6px; text-align: center; font-weight: 700; }
.rubric { padding: 10px; background: #eef7ff; }
.scores { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
fieldset { border: 1px solid #999; }
label { display: inline-block; margin: 4px 12px 4px 0; }
textarea { box-sizing: border-box; width: 100%; min-height: 70px; font: inherit; }
@media (max-width: 760px) {
  .images, .scores { grid-template-columns: 1fr; }
  .toolbar { position: static; }
}
"""

REVIEW_JS = r"""(() => {
  "use strict";
  const payload = window.WPGD_REVIEW_DATA;
  const rows = payload.rows;
  const fields = [
    "human_subject_recognizable",
    "human_severe_subject_error",
    "human_making_feasible",
    "human_advanced_conformance",
  ];
  const storageKey = `wo-pin-ge-dou-review:${location.pathname}:${payload.resultsFilename}`;
  const status = document.getElementById("review-status");
  const finalButton = document.getElementById("download-final");

  function selectedValue(caseId, field) {
    const checked = document.querySelector(`input[name="${caseId}-${field}"]:checked`);
    return checked ? checked.value : "pending";
  }

  function collectRows() {
    return rows.map((original) => {
      const row = { ...original };
      fields.forEach((field) => {
        row[field] = selectedValue(row.case_id, field);
      });
      row.human_review_notes = document.getElementById(`${row.case_id}-notes`).value;
      row.human_review = fields.every((field) => row[field] !== "pending")
        ? "complete"
        : "pending";
      return row;
    });
  }

  function updateProgress() {
    const current = collectRows();
    const complete = current.filter((row) => row.human_review === "complete").length;
    status.textContent = `已完成 ${complete} / ${current.length}`;
    finalButton.disabled = complete !== current.length;
    return current;
  }

  function saveLocally() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(collectRows()));
      document.getElementById("storage-status").textContent = "进度已保存在本机浏览器";
    } catch (_error) {
      document.getElementById("storage-status").textContent =
        "浏览器不允许本地保存，请下载进度 CSV";
    }
  }

  function restoreLocally() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (!Array.isArray(saved)) return;
      saved.forEach((row) => {
        fields.forEach((field) => {
          const selector = `input[name="${row.case_id}-${field}"][value="${row[field]}"]`;
          const input = document.querySelector(selector);
          if (input) input.checked = true;
        });
        const notes = document.getElementById(`${row.case_id}-notes`);
        if (notes) notes.value = row.human_review_notes || "";
      });
    } catch (_error) {
      document.getElementById("storage-status").textContent = "无法读取本机保存的进度";
    }
  }

  function csvCell(value) {
    const text = String(value ?? "");
    return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }

  function downloadCsv(filename, requireComplete) {
    const current = updateProgress();
    const pending = current.filter((row) => row.human_review !== "complete");
    if (requireComplete && pending.length) return;
    const columns = Object.keys(rows[0]);
    const lines = [columns, ...current.map((row) => columns.map((key) => row[key]))];
    const csv = lines.map((line) => line.map(csvCell).join(",")).join("\r\n") + "\r\n";
    const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  document.getElementById("review-form").addEventListener("input", () => {
    updateProgress();
    saveLocally();
  });
  document.getElementById("download-progress").addEventListener("click", () => {
    downloadCsv("test-results-40-progress.csv", false);
  });
  finalButton.addEventListener("click", () => {
    downloadCsv(payload.resultsFilename, true);
  });
  restoreLocally();
  updateProgress();
})();
"""


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


def _radio_group(case_id, field, legend, options, selected):
    labels = []
    for value, label in options:
        checked = " checked" if value == selected else ""
        labels.append(
            f'<label><input type="radio" name="{case_id}-{field}" '
            f'value="{value}"{checked}> {escape(label)}</label>'
        )
    return f"<fieldset><legend>{escape(legend)}</legend>{''.join(labels)}</fieldset>"


def _render_html(entries, *, generated_at, results_filename):
    cards = []
    for entry in entries:
        review = entry["review_values"]
        score_controls = "".join(
            (
                _radio_group(
                    entry["case_id"],
                    "human_subject_recognizable",
                    "主体是否可辨认",
                    (("pending", "待评"), ("pass", "通过"), ("fail", "不通过")),
                    review["human_subject_recognizable"],
                ),
                _radio_group(
                    entry["case_id"],
                    "human_severe_subject_error",
                    "是否有严重主体错误",
                    (("pending", "待评"), ("no", "没有"), ("yes", "有")),
                    review["human_severe_subject_error"],
                ),
                _radio_group(
                    entry["case_id"],
                    "human_making_feasible",
                    "是否可制作",
                    (("pending", "待评"), ("pass", "通过"), ("fail", "不通过")),
                    review["human_making_feasible"],
                ),
                _radio_group(
                    entry["case_id"],
                    "human_advanced_conformance",
                    "高级创作符合度",
                    (
                        ("pending", "待评"),
                        ("pass", "通过"),
                        ("fail", "不通过"),
                        ("not_applicable", "本图不适用"),
                    ),
                    review["human_advanced_conformance"],
                ),
            )
        )
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
  <div class="scores">{score_controls}</div>
  <label for="{escape(entry["case_id"])}-notes">人工评审备注</label>
  <textarea id="{escape(entry["case_id"])}-notes">{escape(review["human_review_notes"])}</textarea>
</article>"""
        )
    return f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>我拼个豆 · 40 图人工质量评审包</title>
  <link rel="stylesheet" href="review.css">
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
  <div class="toolbar" aria-label="评审进度与导出">
    <strong id="review-status" aria-live="polite">已完成 0 / 40</strong>
    <button type="button" id="download-progress">下载进度 CSV</button>
    <button type="button" id="download-final" disabled>下载最终 CSV</button>
    <span id="storage-status" aria-live="polite"></span>
  </div>
  <form id="review-form">{"".join(cards)}</form>
  <script src="review-data.js"></script>
  <script src="review.js"></script>
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
                    "review_values": {field: row[field] for field in REVIEW_FIELDS}
                    | {"human_review_notes": row["human_review_notes"]},
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

        results_rows = [results[case.case_id] for case in CASES]
        review_data = {
            "resultsFilename": Path(results_path).name,
            "rows": results_rows,
        }
        safe_review_json = json.dumps(review_data, ensure_ascii=False).replace("<", "\\u003c")
        (temporary / "review-data.js").write_text(
            f"window.WPGD_REVIEW_DATA = {safe_review_json};\n",
            encoding="utf-8",
        )
        (temporary / "review.js").write_text(REVIEW_JS, encoding="utf-8")
        (temporary / "review.css").write_text(REVIEW_CSS, encoding="utf-8")
        (temporary / "index.html").write_text(
            _render_html(
                entries,
                generated_at=generated_at,
                results_filename=Path(results_path).name,
            ),
            encoding="utf-8",
        )
        manifest = {
            "generated_at": generated_at,
            "case_count": len(entries),
            "source": "scikit-image bundled legal samples with deterministic transforms",
            "results_filename": Path(results_path).name,
            "cases": entries,
            "review_assets": {
                filename: _sha256(temporary / filename)
                for filename in ("index.html", "review.css", "review-data.js", "review.js")
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination
