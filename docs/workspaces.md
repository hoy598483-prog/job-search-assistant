# 工作分区

工作分区让同一 Agent 管理多个独立目标而不混合上下文。每个分区独立保存：目标、参考资料、计划、成果和消息；默认不读取另一分区的内容。

当前分区：

| ID | 工作 | 状态 |
| --- | --- | --- |
| `ai-product-job-agent` | AI 产品求职 Agent | active |
| `quant-smallcap-strategy` | 小市值量化策略 | ready |

跨分区复用必须显式登记，并只共享说明或指定产物。例如可复用通用测试设计，但不能自动把求职资料、量化数据或结论带入另一分区。

```powershell
python workspace_manager.py init
python workspace_manager.py list
python workspace_manager.py use quant-smallcap-strategy
python workspace_manager.py active
```

运行 `use` 仅切换活动分区，不会复制、合并或删除任何资料。
