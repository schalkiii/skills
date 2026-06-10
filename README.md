# Skills & Rules

AI 编程助手专用技能（Skills）与规则（Rules）集合，提供领域专业知识与工作流指导。

## 目录结构

```
my_skills/
├── skills/          # 110 个 Agent 技能
│   ├── agent-browser/
│   ├── caveman/
│   ├── verilog-design/
│   └── ...
├── rules/           # 用户规则
│   ├── AI编程规则.md
│   ├── Context7自动触发.md
│   ├── 任务收尾清理与归档.md
│   └── 非交互模式命令.md
└── README.md
```

## 规则（Rules）

| 规则 | 说明 |
|------|------|
| `AI编程规则` | 完整编程方法论：交互规范、代码修改流程、代码风格、质量要求、优先级 |
| `Context7自动触发` | 需要库/API 文档时自动调用 Context7，无需用户显式要求 |
| `任务收尾清理与归档` | 阶段收尾时清理冗余文件、提交推送、复盘归档、更新 README |
| `非交互模式命令` | 所有命令强制非交互模式，禁止手动确认/密码输入/等待回车 |

## 技能分类

### 通用开发

| 技能 | 说明 |
|------|------|
| `agent-browser` | 浏览器自动化，控制 Chrome 进行表单填写、截图、数据抓取等 |
| `caveman` | 超压缩通信模式，减少约 75% token 消耗 |
| `diagnose` | 系统化调试流程：复现 → 最小化 → 假设 → 插桩 → 修复 → 回归 |
| `gh-cli` | GitHub CLI 全面参考，覆盖仓库、PR、Issue、Actions 等 |
| `git-commit` | Git 提交规范，自动生成 Conventional Commits 格式 |
| `grill-me` | 深度访谈式设计审查，覆盖决策树所有分支 |
| `grill-with-docs` | 结合项目文档的设计审查，同步更新 CONTEXT.md 和 ADR |
| `handoff` | 会话压缩交接，生成供其他 Agent 接手的手册 |
| `improve-codebase-architecture` | 代码架构改进，识别重构机会、模块耦合 |
| `prototype` | 快速原型开发，支持终端应用和 UI 多方案切换 |
| `security-best-practices` | 多语言安全最佳实践审查（Python/JS/TS/Go） |
| `setup-matt-pocock-skills` | 项目配置向导，初始化 Issue Tracker、Triage 标签等 |
| `tdd` | 测试驱动开发，红-绿-重构循环 |
| `to-issues` | 将计划/PRD 拆分为独立可领取的 Issue |
| `to-prd` | 将当前对话上下文生成 PRD 并发布到 Issue Tracker |
| `triage` | Issue 分类状态机，按角色驱动分类流程 |
| `write-a-skill` | 创建新的 Agent Skill，含渐进式文档和资源打包 |
| `zoom-out` | 全局视角审视，跳出细节看整体架构 |

### 硬件设计

| 技能 | 说明 |
|------|------|
| `verilog-design` | 工业级 Verilog/SystemVerilog RTL 设计方法学，覆盖规格定义到综合的完整生命周期 |

### CLI-Anything 系列

为各类 GUI 应用和 SaaS 平台提供命令行接口，支持 AI Agent 自动化操作。

| 技能 | 应用 |
|------|------|
| `cli-anything` | 通用 CLI 框架入口 |
| `cli-hub-meta-skill` | CLI 技能目录，发现可用的 Agent-Native CLI |
| `cli-anything-adguardhome` | AdGuard Home 网络广告拦截 |
| `cli-anything-anygen` | AnyGen OpenAPI 幻灯片/文档生成 |
| `cli-anything-audacity` | Audacity 音频编辑 |
| `cli-anything-blender` | Blender 3D 场景编辑（258 命令） |
| `cli-anything-browser` | 浏览器自动化（DOMShell MCP） |
| `cli-anything-chromadb` | ChromaDB 向量数据库管理 |
| `cli-anything-cloudanalyzer` | CloudAnalyzer 点云质量评估 |
| `cli-anything-cloudcompare` | CloudCompare 点云/网格处理（41 命令） |
| `cli-anything-comfyui` | ComfyUI AI 图像生成工作流 |
| `cli-anything-dify-workflow` | Dify 工作流 DSL 编辑 |
| `cli-anything-drawio` | Draw.io 图表创建与导出 |
| `cli-anything-eth2-quickstart` | 以太坊 2.0 节点部署 |
| `cli-anything-exa` | Exa 网页搜索与内容检索 |
| `cli-anything-firefly-iii` | Firefly III 个人财务管理 |
| `cli-anything-freecad` | FreeCAD 参数化 3D CAD（258 命令） |
| `cli-anything-gimp` | GIMP 图像编辑 |
| `cli-anything-godot` | Godot 游戏引擎项目管理 |
| `cli-anything-inkscape` | Inkscape 矢量图形编辑 |
| `cli-anything-intelwatch` | 竞争情报与 OSINT 搜索 |
| `cli-anything-iterm2` | iTerm2 终端自动化 |
| `cli-anything-iterm2-ctl` | iTerm2 终端控制 |
| `cli-anything-kdenlive` | Kdenlive 视频编辑 |
| `cli-anything-krita` | Krita 数字绘画 |
| `cli-anything-libreoffice` | LibreOffice 文档编辑 |
| `cli-anything-lldb` | LLDB 调试器（Python API） |
| `cli-anything-macrocli` | GUI 宏定义与执行 |
| `cli-anything-mailchimp` | Mailchimp 邮件营销 API（303 命令） |
| `cli-anything-mermaid` | Mermaid 图表渲染 |
| `cli-anything-mubu` | Mubu 实时桥接 |
| `cli-anything-musescore` | MuseScore 乐谱编辑 |
| `cli-anything-n8n` | n8n 工作流自动化 |
| `cli-anything-notebooklm` | NotebookLM 笔记管理 |
| `cli-anything-novita` | Novita AI API（DeepSeek/GLM 等） |
| `cli-anything-nsight-graphics` | Nsight Graphics GPU 性能分析 |
| `cli-anything-nslogger` | NSLogger 日志解析 |
| `cli-anything-obs-studio` | OBS Studio 场景编辑 |
| `cli-anything-obsidian` | Obsidian 知识管理 |
| `cli-anything-ollama` | Ollama 本地 LLM 推理 |
| `cli-anything-openscreen` | 录屏编辑（缩放/变速/裁剪/标注） |
| `cli-anything-pm2` | PM2 Node.js 进程管理 |
| `cli-anything-qgis` | QGIS 地理信息系统 |
| `cli-anything-quietshrink` | macOS 录屏压缩（Apple Silicon HEVC） |
| `cli-anything-renderdoc` | RenderDoc 图形调试器 |
| `cli-anything-rms` | Teltonika RMS 设备管理 |
| `cli-anything-safari` | Safari 浏览器自动化（84 MCP 工具） |
| `cli-anything-sbox` | s&box 游戏引擎（Source 2） |
| `cli-anything-seaclip` | SeaClip-Lite 项目管理 |
| `cli-anything-shotcut` | Shotcut 视频编辑 |
| `cli-anything-slay-the-spire-ii` | Slay the Spire 2 游戏控制 |
| `cli-anything-unimol-tools` | Uni-Mol 分子性质预测 |
| `cli-anything-unrealinsights` | Unreal Engine 性能追踪 |
| `cli-anything-videocaptioner` | AI 视频字幕生成 |
| `cli-anything-wiremock` | WireMock HTTP Mock 管理 |
| `cli-anything-zoom` | Zoom 会议管理 |
| `cli-anything-zotero` | Zotero 文献管理 |

### 飞书 / Lark

| 技能 | 说明 |
|------|------|
| `lark-approval` | 飞书审批 API：审批实例与任务管理 |
| `lark-apps` | 飞书妙搭（Miaoda）：HTML 部署为公网应用 |
| `lark-attendance` | 飞书考勤打卡查询 |
| `lark-base` | 飞书多维表格（Base）：字段/记录/视图/仪表盘/工作流 |
| `lark-calendar` | 飞书日历：日程管理、会议室预定、忙闲查询 |
| `lark-contact` | 飞书通讯录：用户搜索与 ID 解析 |
| `lark-doc` | 飞书云文档 / Docx / Wiki：创建、读取、编辑 |
| `lark-drive` | 飞书云空间：文件/文件夹管理、导入导出 |
| `lark-event` | 飞书实时事件订阅（IM/VC/妙记） |
| `lark-im` | 飞书即时通讯：消息收发、群聊管理 |
| `lark-mail` | 飞书邮箱：草稿、收发、回复、转发 |
| `lark-markdown` | 飞书 Markdown 文件管理 |
| `lark-minutes` | 飞书妙记：音视频转文字、纪要生成 |
| `lark-okr` | 飞书 OKR：目标与关键结果管理 |
| `lark-openapi-explorer` | 飞书原生 OpenAPI 探索 |
| `lark-shared` | 飞书 CLI 基础配置：登录、身份切换 |
| `lark-sheets` | 飞书电子表格：工作表/单元格操作 |
| `lark-skill-maker` | 飞书自定义 Skill 创建 |
| `lark-slides` | 飞书幻灯片：创建与编辑 |
| `lark-task` | 飞书任务：待办、清单、任务智能体 |
| `lark-vc` | 飞书视频会议：历史会议查询、纪要获取 |
| `lark-vc-agent` | 飞书会议机器人：入会/离会/实时事件 |
| `lark-whiteboard` | 飞书画板：架构图/流程图/时序图 |
| `lark-wiki` | 飞书知识库：空间管理、节点组织 |
| `lark-workflow-meeting-summary` | 会议纪要整理工作流 |
| `lark-workflow-standup-report` | 日程待办摘要工作流 |

### 企业微信

| 技能 | 说明 |
|------|------|
| `wecomcli-contact` | 通讯录成员查询 |
| `wecomcli-doc` | 文档/智能表格/智能文档管理 |
| `wecomcli-meeting` | 会议创建与管理 |
| `wecomcli-msg` | 消息收发与会话查询 |
| `wecomcli-schedule` | 日程管理 |
| `wecomcli-smartsheet` | 智能表格：子表/字段/记录管理 |
| `wecomcli-todo` | 待办事项管理 |

## 使用方法

将本仓库克隆到 AI 编程助手的技能目录中，即可在编码时自动加载对应技能指导。
