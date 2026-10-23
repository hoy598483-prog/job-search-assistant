# 求职助理

Chrome 扩展 + 本机 Agent：收集岗位文本，与 Codex 制定计划，通过每日课程和学习笔记持续准备。

在原“求职准备 Agent”上增量扩展：从 Chrome 主动采集招聘页面，分析和比较原文、收藏岗位、手动记录进度，并围绕同一个产品完成七天训练。

新入口：[Windows Chrome 运行步骤](docs/browser-companion.md)。学习主线：[七天实战计划](docs/browser-project-week.md)。原有聊天、Dify、能力地图和计划内核保留。新浏览器工作台复用引用校验与 Session 版本/审阅机制；不会把未审阅 JD 自动导入旧样本映射。

当前 MVP：Chrome 扩展源码、本机受口令保护的服务、离线/Codex/可选 API Provider、文本样本比较、收藏、手动状态和用户选择式七天训练。扩展只收藏用户选中的文字或当前页面正文，不识别岗位卡片、标签页或职位链接。核心目标是类别能力地图。Codex 已用合成文本真实调用成功；Chrome 实际加载试用尚待完成。跨来源语义去重和个性化能力地图连接尚未实现。

## 从 GitHub 安装

仓库仅包含源码和示例，不包含本人简历、背景、运行记录、本机注册配置或已编译程序。

1. 安装 Python 3.10+、Windows Chrome；在线模型功能还需安装并登录官方 Codex CLI。
2. 下载仓库后，在项目目录运行以下命令，初始化旧版工具所需的空白资料，并构建 Native Host：

```powershell
Copy-Item data/profile.example.json data/profile.json
python -m pip install pyinstaller
.\build_native_host.ps1
```

3. Chrome 打开 `chrome://extensions`，开启开发者模式，加载 `browser_companion` 文件夹。
4. 复制扩展 ID，运行 `.\install_native_host.ps1 -ExtensionId 你的扩展ID`，然后重新加载扩展。
5. 从扩展进入“数据收集”或“Codex 计划”。个人背景在独立页面由本人提供和确认。

PyInstaller 仅用于打包本机启动程序，不是后端运行依赖。升级源码后需要重新构建 Native Host，避免继续执行旧程序。

## 从这里开始

1. 按 [浏览器运行步骤](docs/browser-companion.md) 加载扩展并启动本机服务。
2. 查看 [用户资料](data/profile.json) 和 [招聘样本](data/jobs.json)。
3. 按 [新的七天实战计划](docs/browser-project-week.md) 逐步交付；原 [第 1 天记录](docs/day1.md) 保留作为历史。

所有运行命令都在本项目目录执行。当前代码仅使用 Python 标准库，无需 API 密钥或额外依赖。
无密钥可运行离线功能；浏览器工作台的 Codex 模式调用官方 CLI 的已有登录。下方旧 `extract_job.py` 在线入口仍需要 API Key，不同于 Codex CLI 模式。

## 新招聘文本提取

```powershell
# 离线校验合成样本，不调用模型
python extract_job.py data/extraction-example.txt --candidate data/extraction-example.json
# 在线/本地网关调用：配置 OPENAI_API_KEY；默认模型为 luna-light
python extract_job.py path/to/job.txt
```

不在聊天中发送密钥，不将密钥提交到仓库；程序直接读取环境变量，不自动加载 .env。

调用使用 OpenAI Responses 兼容接口，仅发送指定招聘文本，不读取个人资料。默认模型名为 `luna-light`；可用 `LOCAL_MODEL` 覆盖模型名，或用 `OPENAI_MODEL` 覆盖。若本地服务不是默认地址，用 `OPENAI_BASE_URL` 指定网关地址。模型需支持结构化输出。配置缺失时明确报错，不降级成伪造模型结果。

结果包含职责/必须项/加分项/不明确、条件关系、原文字符位置与全文指纹。引用必须逐字出现在源文本中；部分明显的“优先”与“至少一项”冲突会被拦截。格式有效不等于理解正确：语义和提取完整性仍需审阅。结果独立保存到 output/extractions，不自动更新岗位库、能力档案或计划。

合成样本和模拟响应测试只验证程序行为，不能作为真实模型质量或联网成功的证据。API拒绝、响应不完整或校验失败均不会保存为有效结果。当前不自动重试。

## GPT-5.6 Terra 离线模拟评估

```powershell
python simulate_terra.py
```

这会使用当前助手生成的八条合成招聘文本和候选提取结果，运行本地引用校验，并生成 `output/terra-simulated-evaluation.md` 供人工查看。它覆盖职责/必需项/加分项、择一与并列条件、模糊条件、否定条件、注入式文本和非招聘文本。

它是对“使用 GPT-5.6 Terra 的预期行为”的离线模拟，不是 GPT-5.6 Terra 模型调用、基准测试或质量声明。人工审阅重点写在报告每一项之后。

## 原型运行（由 AI 代为操作也可以）

```powershell
python coach.py
python coach.py --minutes 20
python -m unittest -v
```

默认分析 job_01 和 job_02，使用每天两小时的项目预算。结果写入 output/ 的 Markdown 和 JSON 文件；原始个人资料不被报告生成覆盖。可通过 --jobs 指定样本；没有已审阅映射的样本只展示原文和未知状态，不生成无依据任务。

data/assessment_rules.json 是人工审阅映射，coach.py 执行来源引用、证据状态与预算规则；test_coach.py 验证预算缩减、要求隔离、原文追溯和未知状态。新增招聘材料先在聊天分析，再扩展映射。

用户无需填写 JSON 或做教学式问答。AI 编写实现、运行测试并讲解关键原理；用户按实际使用需要反馈。

## 岗位类别计划

用户可以针对岗位类别而非单个岗位填写一至五条招聘简介。`data/role-brief-template.json` 定义聊天入口需要保存的资料；`role_scope.py` 只聚合已审阅的简介，生成 core、targeted、watch 和 optional 能力地图。它不根据关键词自行猜测两条要求相同，`capability_key` 需要由提取后的审阅阶段提供。

当前面向 AI 产品岗位的一周作品计划见 `docs/ai-product-role-plan.md`。
AI 产品经理基础知识与项目化训练见 `docs/ai-pm-core-training.md`。
AI 产品与量化研究双轨推进计划见 `docs/dual-track-plan.md`；量化研究原型定义见 `docs/quant-research-project.md`。
量化研究最小数据与时间切分内核在 `quant_research.py`；它只处理研究数据，不执行交易。

## 工作分区

`workspace_manager.py` 为每个工作保存独立状态，当前包括 AI 产品求职 Agent 与小市值量化策略。详见 `docs/workspaces.md`。默认不跨分区读取或汇总资料；共享需要显式登记。

## 聊天状态与计划历史

session.py 提供资料更新、消息记录、计划草案与采用、成果提交、带理由的审阅、当前计划导出。聊天助手调用这些接口；它不是独立自然语言聊天模型。

状态保存在 data/session.json。新计划先成为草案，采用后旧版仍保留。成果提交默认待审阅，不会因“我懂了”自动完成；验收不自动升级个人能力。资料更新通过带聊天来源的覆盖记录保存，不修改原始资料。

接口调用由单一聊天助手顺序执行，目前不支持多进程并发写入。消息含义、用户是否明确采用计划、成果是否合格仍由聊天助手判断，不应将该模块作为面向不可信客户端的授权服务。

当前计划查看 output/current-plan.md；测试使用临时目录，不向真实会话添加模拟成果。

截图样本没有岗位链接、公司和发布日期，不代表已经验证有效的在招岗位。个人资料只用于本地练习；后续接入模型时需明确发送哪些字段。
# 删除准备方向

工作台分为“数据收集”和“Codex 计划”两个分页，左侧导航切换。数据收集页处理采集原文、分析对比和收藏；Codex 计划页处理选择样本、讨论项目、接受或修改一周计划和每日课程。分页采用独立地址 `panel.html#collect`、`panel.html#plan`，在同一工作台内切换，保留当前连接、生成中的回复和未发送的草稿。个人背景、学习笔记本继续使用独立页面。

在扩展工作台的“准备方向”旁点击“删除当前方向”，确认后清除该方向在本浏览器中的文本样本、主聊天、课程、计划、进度和待保存文本。全局个人背景、学习笔记保留；已标记完成的任务与计划会先归档到笔记本，并保留原方向名称和原完成日期。未完成任务不会作为已完成成果归档。

可以删除最后一个方向；工作台保持空状态，点击“新建准备方向”即可重新开始。删除操作不会清理旧版后端文件或独立的划词问答记录。更新后在 Chrome 扩展管理页重新加载扩展，并关闭旧工作台后重新打开；本次改动无需重装 Native Host。

