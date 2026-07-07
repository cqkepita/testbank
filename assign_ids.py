import json
import glob
import os

id_counter = 1
for fname in sorted(glob.glob("chapter*.json")):
    with open(fname, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for q in data:
        q['id'] = id_counter
        id_counter += 1
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
print(f"✅ 分配完成，最大 ID: {id_counter-1}")