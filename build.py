"""Inject data.json into template.html to produce index.html."""
import json, pathlib

root = pathlib.Path(__file__).parent
data = (root / "data.json").read_text()
template = (root / "template.html").read_text()
if "__DATA_JSON__" not in template:
    raise SystemExit("template.html has no __DATA_JSON__ placeholder")
out = template.replace("__DATA_JSON__", json.dumps(json.loads(data), ensure_ascii=False, separators=(",", ":")))
(root / "index.html").write_text(out)
print(f"index.html rebuilt ({len(out):,} chars)")
