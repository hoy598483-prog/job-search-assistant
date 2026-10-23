"""第 1 天：读取、保存、重新读取 JSON。只使用 Python 标准库。"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main():
    source = ROOT / "data" / "profile.json"
    destination = ROOT / "output" / "profile.practice.json"
    profile = load_json(source)

    # 你的练习：在这里设置 profile 的 weekly_prep_hours 字段。

    save_json(destination, profile)
    restored = load_json(destination)
    if restored != profile:
        raise ValueError("保存后读回的数据不一致")
    print("读写核对通过")
    print("目标方向：", "、".join(restored["target_directions"]))
    print("每周准备小时数：", restored["weekly_prep_hours"])
    print("练习文件：", destination)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"读写失败，请检查文件路径和 JSON 格式：{error}")
