"""运行 GPT-5.6 Terra 离线模拟生成的招聘提取测试集。

这不是 GPT-5.6 Terra API 或模型推理；候选输出由当前助手生成并保存为合成夹具。
"""
import json
from pathlib import Path

from extract_job import validate

ROOT = Path(__file__).resolve().parent


def run(path=None):
    dataset_path = Path(path) if path else ROOT / "data" / "terra_simulated_testset.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    results = []
    for case in dataset["cases"]:
        try:
            result = validate(case["source"], case["candidate"])
            results.append({"id": case["id"], "focus": case["focus"], "status": "passed",
                            "items": result["items"], "review_notes": case["review_notes"]})
        except ValueError as error:
            results.append({"id": case["id"], "focus": case["focus"], "status": "failed",
                            "error": str(error), "review_notes": case["review_notes"]})
    return dataset, results


def markdown(dataset, results):
    count = sum(result["status"] == "passed" for result in results)
    lines = ["# GPT-5.6 Terra 离线模拟：招聘文本提取测试", "",
             f"来源：{dataset['generator']}。", "",
             "注意：这是由当前助手生成的合成测试集与候选输出，未调用真实模型。通过表示本地引用校验通过，不表示真实模型质量。", "",
             f"本地校验：{count}/{len(results)} 通过。", ""]
    cases = {case["id"]: case for case in dataset["cases"]}
    for result in results:
        case = cases[result["id"]]
        lines += [f"## {result['id']} · {result['focus']}", "", "**输入文本**", "", "> " + case["source"].replace("\n", "\n> "), "", "**模拟输出**", ""]
        if result["status"] == "passed":
            for item in result["items"]:
                lines += [f"- `{item['kind']}` / `{item['relation']}`：{item['summary']}",
                          f"  - 引用：{item['quote']}"]
        else:
            lines += [f"- 校验失败：{result['error']}"]
        lines += ["", f"人工查看重点：{result['review_notes']}", ""]
    return "\n".join(lines)


def main():
    dataset, results = run()
    output = ROOT / "output" / "terra-simulated-evaluation.md"
    output.parent.mkdir(exist_ok=True)
    output.write_text(markdown(dataset, results), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
