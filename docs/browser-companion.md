# Windows Chrome 浏览器求职助理 MVP

这是对当前 `agent product` 的实际增量，不是迁移或重写 9 月的独立岗位发现项目。核心单位是同一岗位类别的多个样本；单个岗位链接只承担来源定位。9 月项目含另一套 pipeline，但当前项目有不同的计划和审阅模型，因此本次复用当前项目的提取校验、工作分区和 Session，不强行合并两套状态。

## 安装（一次）

只需现有 Python 3.10+ 和 Windows Chrome，后端没有新增第三方包。

1. Chrome 地址栏输入 `chrome://extensions`，打开“开发者模式”。
2. 点击“加载已解压的扩展程序”，选择本项目 `browser_companion` 文件夹。
3. 复制扩展卡片上的 32 位 ID。在本项目目录的 PowerShell 执行一次：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_native_host.ps1 -ExtensionId 这里替换成扩展ID
```

4. 在 `chrome://extensions` 点击扩展“重新加载”。以后点击扩展 → 打开工作台时，Chrome 会自动启动 Native Host 和 `companion.server`，不需要手动启动终端或复制口令。服务默认只监听 `127.0.0.1:8765`，每次启动都会生成新口令；口令仍只用于本次服务会话。
5. 在任意页面选中需要的文字后点击扩展“收藏当前文本”；有选区时只保存选区，没有选区时保存当前页面正文。不识别岗位卡片、标签页或职位链接。不要在私信或个人资料页面采集。采集只存入扩展的临时会话存储。
6. 回到工作台，刷新、检查或删改文本。离线模式保留原文而不伪造提取结果；Codex 模式会在发送前确认。逐页采集最多六页，勾选后即可并排比较。
7. 保存原文、记录状态、生成计划草案和采用计划都有单独确认。系统先给出最多三个项目候选，只有用户选择并再次确认后才成为当前计划。成果提交后仍待审阅。关闭终端停止服务；工作台清空采集可清除暂存页面。

扩展使用固定端口 8765；若自行改后端端口，也需同步改扩展地址与 CSP。扩展当前只展示求职分区，后端按已注册分区校验，拒绝任意目录路径。工作台不会操作招聘网站 DOM、点击申请或发送消息。

## 模型后端与登录边界

- `mock`：默认无网络，仅保留原文，`items=[]`，明确提示未执行模型理解。
- `codex`：调用未修改的官方 `codex exec`，使用 CLI 自己的已有登录；不读取、复制或代理 OAuth token。没有登录时在官方终端执行 `codex login`。临时工作目录、read-only、禁 shell/应用连接/插件/浏览器工具、忽略用户配置、结构化 schema、90 秒超时、逐字校验。失败明确报错，不自动切换付费 API。
- `api`：复用原 `extract_job.extract`，只在用户主动选择并确认后调用。沿用 `OPENAI_API_KEY`、`OPENAI_MODEL`/`LOCAL_MODEL`、`OPENAI_BASE_URL`。建议明确设置服务商实际支持的模型名，旧默认 `luna-light` 不代表 OpenAI 公共 API 保证支持。API 路径本次没有真实付费测试。
- `claude`：Provider 明确返回不可用。本机尚未登录，也未确认这个第三方应用后端用途的订阅适用范围；不能宣称拥有订阅就能当任意服务 API。可继续在官方 Claude Code 中人工分析原文。

2026-10-18 实测：本机 Codex 已登录 ChatGPT；使用两句合成招聘文本的真实 CLI 调用成功，返回一条 required 和一条 preferred，两条逐字引用均通过。并非真实招聘岗位或模型质量基准。

官方依据：[Rill](https://rill.love/)、[Codex 非交互执行](https://learn.chatgpt.com/docs/non-interactive-mode)、[Codex 认证](https://learn.chatgpt.com/docs/auth)、[Claude 程序化运行](https://code.claude.com/docs/en/headless)、[Claude 认证使用限制](https://code.claude.com/docs/en/legal-and-compliance)。使用资格、额度及组织限制仍以实际账号和当前条款为准；此 MVP 是用户本机单人流程。

## 数据、权限和事实边界

- 模型只收到工作台选中的正文，不带已有个人档案、量化资料、Cookie 或密码。
- 页面命令以 JSON 字符串作为不可信材料；模型没有保存、投递或改计划接口。提示词隔离不能保证语义理解正确，所有结果保持待审阅。
- 采集移除表单、脚本和常见隐藏元素；不保证过滤所有 CSS 隐藏文本或正文中的个人信息，必须预览。选中文本也需自行确认范围。
- 服务校验 Host、精确扩展 Origin、随机 Bearer 口令、请求大小和动作白名单。仅用于可信本机单人环境，口令不是多用户权限体系。
- 只接受 HTTP(S) 来源，拒绝带用户名密码的 URL；后端不请求页面 URL，因此没有任意网页抓取或绕过登录能力。查询参数可能包含私密数据，采集前应检查来源地址。
- 同 URL 收藏更新快照并保留手动状态；同 URL 同文本的批次分析去重。不同来源的同一岗位还没有语义去重。
- 岗位链接只用于回看样本来源；不做单个岗位官网真实性核验，也不把官网状态作为类别能力地图的依据。
- 标题是页面标题，不保证为标准职位名称；公司、工资、城市不做无证据补全。
- SQLite 收藏、分区训练历史和不含正文的动作日志位于 `output/companion`。该目录已由现有 `.gitignore` 排除；关闭服务后可自行备份或删除。采集原文含潜在个人信息，不应公开分享数据库。
- Session 原来的 `export` 针对旧 coach 报告；新训练在浏览器渲染，不调用旧导出。审阅继续通过可信本地聊天调用 `Session.review`，不向浏览器暴露直接批准接口。

## 测试和未完成

```powershell
python -m unittest discover -v
python -m unittest discover -s tests -v
node --check browser_companion/popup.js
node --check browser_companion/panel.js
```

新增 9 个测试覆盖：无模型伪造、读写确认、禁止动作、重复收藏、工作分区隔离、预算和版本、待审阅、来源 URL、Provider 失败与假引用、HTTP Host/Origin/口令、日志不含正文。HTTP 测试需要本机回环网络权限。旧 Dify 测试删除了一个引用缺失生成器的无用 import，测试仍直接检查保存的 DSL。

未完成的验收：用户 Chrome 中加载扩展的完整点击流程、真实招聘站点布局兼容、多个真实 JD 的提取质量评测、API 后端实测、Claude 后端、跨来源语义去重、样本审阅与 `role_scope` 能力地图的自动连接。没有自动操作独立招聘标签的浏览 Agent；当前独立标签仅为分析工作台。未宣称完整复刻 Rill。
