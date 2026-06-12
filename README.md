# AI IDE 配置备份与迁移中心

各主流 AI IDE（Trae / Cursor / Windsurf / CodeBuddy / Qoder / Copilot 等）的 **规则（Rules）**、**MCP 配置**、**技能（Skills）** 备份、互相迁移的统一仓库。

## 项目定位

- **备份**：将各 AI IDE 的配置统一归档，防止丢失
- **迁移**：跨 IDE 复用配置，减少重复设置
- **参考**：了解各 IDE 的配置格式差异，快速上手新工具

## 目录结构

```
skills/
├── ides/                          # 各 IDE 特有配置
│   └── trae/                      # Trae IDE
│       ├── mcp/                   # MCP 服务器配置
│       │   ├── global-mcp.json    # 用户级 MCP（脱敏模板）
│       │   └── example-agentcad-workspace.json  # 项目级 MCP 示例
│       └── rules/                 # 规则配置
│           └── user_rules.md      # 用户全局规则模板
├── skills/                        # 124 个可迁移的 Agent 技能
│   ├── agent-browser/
│   ├── lark-base/
│   ├── cli-anything-*
│   └── ...
├── rules/                         # 通用规则（与 IDE 无关）
│   ├── AI编程规则.md
│   ├── Context7自动触发.md
│   ├── 代码修改规则.md
│   ├── 任务收尾清理与归档.md
│   └── 非交互模式命令.md
└── README.md
```

## 各 AI IDE 配置格式对比

### Rules（规则）

| IDE                          | 规则文件路径                                                        | 格式                               | 特殊机制                                                                                     |
| ---------------------------- | ------------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------- |
| **Trae**（字节跳动）         | `.trae/rules/*.md`（项目级）<br>Settings > Rules > Global（用户级） | Markdown                           | 支持 4 种生效模式：`alwaysApply`、`globs` 匹配文件、`description` 智能判断、`#Rule` 手动引用 |
| **Cursor**                   | `.cursor/rules/*.mdc`                                               | MDC（YAML Frontmatter + Markdown） | Frontmatter 字段：`description`、`globs`、`alwaysApply`；支持多文件规则                      |
| **Windsurf**（Codeium）      | `.windsurfrules`（项目根目录）                                      | 纯文本（单文件）                   | 所有规则合并为单一文件                                                                       |
| **GitHub Copilot**           | `.github/copilot-instructions.md`                                   | Markdown（单文件）                 | 仅单文件，所有规则集中                                                                       |
| **CodeBuddy**（腾讯）        | `.codebuddy/rules/*.md`                                             | Markdown                           | 与 Trae 格式类似                                                                             |
| **Lingma**（阿里）           | `.lingma/rules/*.md`                                                | Markdown                           | 支持 HTML 注释元数据                                                                         |
| **Claude Code**（Anthropic） | `CLAUDE.md`（项目根目录）                                           | Markdown（单文件）                 | 单文件项目指导                                                                               |
| **Gemini CLI**（Google）     | `GEMINI.md`（项目根目录）                                           | Markdown（单文件）                 | 单文件项目指导                                                                               |
| **VS Code**（通用）          | `.vscode/rules/*.md`                                                | Markdown                           | 标准 Markdown 格式                                                                           |

### MCP（Model Context Protocol）

| IDE          | MCP 配置路径                                                                                  | 格式                        | 传输方式        |
| ------------ | --------------------------------------------------------------------------------------------- | --------------------------- | --------------- |
| **Trae**     | 全局：`~/.trae/mcp.json` 或 `AppData/Roaming/Trae CN/User/mcp.json`<br>项目：`.trae/mcp.json` | JSON（对象 key 为服务器名） | `stdio` / `sse` |
| **Cursor**   | `~/.cursor/mcp.json` 或 `.cursor/mcp.json`                                                    | JSON（对象 key 为服务器名） | `stdio` / `sse` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json`                                                         | JSON（对象 key 为服务器名） | `stdio` / `sse` |
| **VS Code**  | `.vscode/mcp.json`                                                                            | JSON                        | `stdio` / `sse` |

> **MCP 格式基本通用**：各 IDE 均采用 Anthropic 的 MCP 标准（JSON-RPC 2.0），配置结构一致（`command`/`args`/`env` 或 `url`/`headers`），差异主要在文件路径。

### Skills（技能）

| IDE          | 技能存储路径                                                                    | 格式                                    | 特殊说明                                                                                                                    |
| ------------ | ------------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Trae**     | 用户级：`~/.trae/skills/<name>/SKILL.md`<br>也可通过 Trae 内置 Skill 管理器安装 | SKILL.md（YAML Frontmatter + Markdown） | Frontmatter 包含 `name`、`version`、`description`、`metadata.requires`；支持 `references/`、`templates/`、`scripts/` 子目录 |
| **Cursor**   | `.cursor/rules/`（项目级，不区分 skill 概念）                                   | `.mdc` 文件                             | 无独立 skill 概念，规则即技能                                                                                               |
| **其他 IDE** | 多数不原生支持 Skill                                                            | —                                       | 通常通过 Rules 或 MCP 实现类似功能                                                                                          |

## Trae 配置详解

### Trae Rules 生效模式

Trae 的项目规则支持 4 种生效模式：

| 模式     | `alwaysApply` | 需配置属性                                      | 说明                              |
| -------- | ------------- | ----------------------------------------------- | --------------------------------- |
| 始终生效 | `true`        | 无                                              | 所有 AI 对话均加载                |
| 匹配文件 | `false`       | `globs`：文件通配符（如 `*.js`、`src/**/*.ts`） | 匹配文件时自动激活                |
| 智能判断 | `false`       | `description`：使用场景描述                     | AI 根据上下文自动判断是否使用     |
| 手动引用 | `false`       | 无                                              | 仅在对话中通过 `#Rule` 引用时生效 |

### Trae Skills 目录结构

```
~/.trae/skills/
└── <skill-name>/
    ├── SKILL.md          # 必须：技能定义（YAML Frontmatter + 正文）
    ├── references/       # 可选：参考文档
    ├── templates/        # 可选：模板文件
    └── scripts/          # 可选：脚本文件
```

SKILL.md Frontmatter 格式：

```yaml
---
name: <skill-name>
version: <x.y.z>
description: "技能描述"
metadata:
  requires:
    bins: ["依赖的命令行工具"]
  cliHelp: "帮助命令"
---
```

## 通用规则

| 规则                 | 说明                                                               |
| -------------------- | ------------------------------------------------------------------ |
| `AI编程规则`         | 完整编程方法论：交互规范、代码修改流程、代码风格、质量要求、优先级 |
| `Context7自动触发`   | 需要库/API 文档时自动调用 Context7，无需用户显式要求               |
| `代码修改规则`       | 变更影响分析、完整性自检清单                                       |
| `任务收尾清理与归档` | 阶段收尾时清理冗余文件、提交推送、复盘归档、更新 README            |
| `非交互模式命令`     | 所有命令强制非交互模式，禁止手动确认/密码输入/等待回车             |

## 技能分类（共 124 个）

### 通用开发

| 技能                            | 说明                                                      |
| ------------------------------- | --------------------------------------------------------- |
| `agent-browser`                 | 浏览器自动化，控制 Chrome 进行表单填写、截图、数据抓取等  |
| `caveman`                       | 超压缩通信模式，减少约 75% token 消耗                     |
| `diagnose`                      | 系统化调试流程：复现 → 最小化 → 假设 → 插桩 → 修复 → 回归 |
| `edit-article`                  | 文章编辑与改进：结构重组、清晰度提升                      |
| `gh-cli`                        | GitHub CLI 全面参考，覆盖仓库、PR、Issue、Actions 等      |
| `git-commit`                    | Git 提交规范，自动生成 Conventional Commits 格式          |
| `git-guardrails-claude-code`    | Claude Code Git 安全钩子，阻止危险操作                    |
| `grill-me`                      | 深度访谈式设计审查，覆盖决策树所有分支                    |
| `grill-with-docs`               | 结合项目文档的设计审查，同步更新 CONTEXT.md 和 ADR        |
| `handoff`                       | 会话压缩交接，生成供其他 Agent 接手的手册                 |
| `improve-codebase-architecture` | 代码架构改进，识别重构机会、模块耦合                      |
| `migrate-to-shoehorn`           | 测试文件类型断言迁移（as → @total-typescript/shoehorn）   |
| `obsidian-vault`                | Obsidian 知识库管理：搜索、创建、组织笔记                 |
| `opencli-adapter-author`        | OpenCLI 适配器开发：从零编写新站点的 CLI 适配器           |
| `opencli-autofix`               | OpenCLI 适配器自动修复                                    |
| `opencli-browser`               | OpenCLI 浏览器自动化驱动                                  |
| `opencli-usage`                 | OpenCLI 使用指南与适配器发现                              |
| `prototype`                     | 快速原型开发，支持终端应用和 UI 多方案切换                |
| `review`                        | 代码审查：基于 Standards 和 Spec 两维度                   |
| `scaffold-exercises`            | 练习题目录结构生成                                        |
| `security-best-practices`       | 多语言安全最佳实践审查（Python/JS/TS/Go）                 |
| `setup-matt-pocock-skills`      | 项目配置向导，初始化 Issue Tracker、Triage 标签等         |
| `setup-pre-commit`              | Husky 预提交钩子配置（Prettier/类型检查/测试）            |
| `smart-search`                  | 基于 OpenCLI 的智能搜索路由                               |
| `tdd`                           | 测试驱动开发，红-绿-重构循环                              |
| `to-issues`                     | 将计划/PRD 拆分为独立可领取的 Issue                       |
| `to-prd`                        | 将当前对话上下文生成 PRD 并发布到 Issue Tracker           |
| `triage`                        | Issue 分类状态机，按角色驱动分类流程                      |
| `write-a-skill`                 | 创建新的 Agent Skill，含渐进式文档和资源打包              |
| `writing-beats`                 | 叙事节拍式文章写作                                        |
| `writing-fragments`             | 写作素材碎片挖掘与积累                                    |
| `writing-shape`                 | 从素材/笔记/草稿塑造为可发布文章                          |
| `zoom-out`                      | 全局视角审视，跳出细节看整体架构                          |

### 硬件设计

| 技能             | 说明                                                                          |
| ---------------- | ----------------------------------------------------------------------------- |
| `verilog-design` | 工业级 Verilog/SystemVerilog RTL 设计方法学，覆盖规格定义到综合的完整生命周期 |

### CLI-Anything 系列（62 个）

为各类 GUI 应用和 SaaS 平台提供命令行接口，支持 AI Agent 自动化操作。

| 技能                             | 应用                                      |
| -------------------------------- | ----------------------------------------- |
| `cli-anything`                   | 通用 CLI 框架入口                         |
| `cli-hub-meta-skill`             | CLI 技能目录，发现可用的 Agent-Native CLI |
| `cli-anything-adguardhome`       | AdGuard Home 网络广告拦截                 |
| `cli-anything-anygen`            | AnyGen OpenAPI 幻灯片/文档生成            |
| `cli-anything-audacity`          | Audacity 音频编辑                         |
| `cli-anything-blender`           | Blender 3D 场景编辑（258 命令）           |
| `cli-anything-browser`           | 浏览器自动化（DOMShell MCP）              |
| `cli-anything-chromadb`          | ChromaDB 向量数据库管理                   |
| `cli-anything-cloudanalyzer`     | CloudAnalyzer 点云质量评估                |
| `cli-anything-cloudcompare`      | CloudCompare 点云/网格处理（41 命令）     |
| `cli-anything-comfyui`           | ComfyUI AI 图像生成工作流                 |
| `cli-anything-dify-workflow`     | Dify 工作流 DSL 编辑                      |
| `cli-anything-drawio`            | Draw.io 图表创建与导出                    |
| `cli-anything-eth2-quickstart`   | 以太坊 2.0 节点部署                       |
| `cli-anything-exa`               | Exa 网页搜索与内容检索                    |
| `cli-anything-firefly-iii`       | Firefly III 个人财务管理                  |
| `cli-anything-freecad`           | FreeCAD 参数化 3D CAD（258 命令）         |
| `cli-anything-gimp`              | GIMP 图像编辑                             |
| `cli-anything-godot`             | Godot 游戏引擎项目管理                    |
| `cli-anything-inkscape`          | Inkscape 矢量图形编辑                     |
| `cli-anything-intelwatch`        | 竞争情报与 OSINT 搜索                     |
| `cli-anything-iterm2`            | iTerm2 终端自动化                         |
| `cli-anything-iterm2-ctl`        | iTerm2 终端控制                           |
| `cli-anything-kdenlive`          | Kdenlive 视频编辑                         |
| `cli-anything-krita`             | Krita 数字绘画                            |
| `cli-anything-libreoffice`       | LibreOffice 文档编辑                      |
| `cli-anything-lldb`              | LLDB 调试器（Python API）                 |
| `cli-anything-macrocli`          | GUI 宏定义与执行                          |
| `cli-anything-mailchimp`         | Mailchimp 邮件营销 API（303 命令）        |
| `cli-anything-mermaid`           | Mermaid 图表渲染                          |
| `cli-anything-mubu`              | Mubu 实时桥接                             |
| `cli-anything-musescore`         | MuseScore 乐谱编辑                        |
| `cli-anything-n8n`               | n8n 工作流自动化                          |
| `cli-anything-notebooklm`        | NotebookLM 笔记管理                       |
| `cli-anything-novita`            | Novita AI API（DeepSeek/GLM 等）          |
| `cli-anything-nsight-graphics`   | Nsight Graphics GPU 性能分析              |
| `cli-anything-nslogger`          | NSLogger 日志解析                         |
| `cli-anything-obs-studio`        | OBS Studio 场景编辑                       |
| `cli-anything-obsidian`          | Obsidian 知识管理                         |
| `cli-anything-ollama`            | Ollama 本地 LLM 推理                      |
| `cli-anything-openscreen`        | 录屏编辑（缩放/变速/裁剪/标注）           |
| `cli-anything-pm2`               | PM2 Node.js 进程管理                      |
| `cli-anything-qgis`              | QGIS 地理信息系统                         |
| `cli-anything-quietshrink`       | macOS 录屏压缩（Apple Silicon HEVC）      |
| `cli-anything-renderdoc`         | RenderDoc 图形调试器                      |
| `cli-anything-rms`               | Teltonika RMS 设备管理                    |
| `cli-anything-safari`            | Safari 浏览器自动化（84 MCP 工具）        |
| `cli-anything-sbox`              | s&box 游戏引擎（Source 2）                |
| `cli-anything-seaclip`           | SeaClip-Lite 项目管理                     |
| `cli-anything-shotcut`           | Shotcut 视频编辑                          |
| `cli-anything-slay-the-spire-ii` | Slay the Spire 2 游戏控制                 |
| `cli-anything-unimol-tools`      | Uni-Mol 分子性质预测                      |
| `cli-anything-unrealinsights`    | Unreal Engine 性能追踪                    |
| `cli-anything-videocaptioner`    | AI 视频字幕生成                           |
| `cli-anything-wiremock`          | WireMock HTTP Mock 管理                   |
| `cli-anything-zoom`              | Zoom 会议管理                             |
| `cli-anything-zotero`            | Zotero 文献管理                           |

### 飞书 / Lark（27 个）

| 技能                            | 说明                                               |
| ------------------------------- | -------------------------------------------------- |
| `lark-approval`                 | 飞书审批 API：审批实例与任务管理                   |
| `lark-apps`                     | 飞书妙搭（Miaoda）：HTML 部署为公网应用            |
| `lark-attendance`               | 飞书考勤打卡查询                                   |
| `lark-base`                     | 飞书多维表格（Base）：字段/记录/视图/仪表盘/工作流 |
| `lark-calendar`                 | 飞书日历：日程管理、会议室预定、忙闲查询           |
| `lark-contact`                  | 飞书通讯录：用户搜索与 ID 解析                     |
| `lark-doc`                      | 飞书云文档 / Docx / Wiki：创建、读取、编辑         |
| `lark-drive`                    | 飞书云空间：文件/文件夹管理、导入导出              |
| `lark-event`                    | 飞书实时事件订阅（IM/VC/妙记）                     |
| `lark-im`                       | 飞书即时通讯：消息收发、群聊管理                   |
| `lark-mail`                     | 飞书邮箱：草稿、收发、回复、转发                   |
| `lark-markdown`                 | 飞书 Markdown 文件管理                             |
| `lark-minutes`                  | 飞书妙记：音视频转文字、纪要生成                   |
| `lark-okr`                      | 飞书 OKR：目标与关键结果管理                       |
| `lark-openapi-explorer`         | 飞书原生 OpenAPI 探索                              |
| `lark-shared`                   | 飞书 CLI 基础配置：登录、身份切换                  |
| `lark-sheets`                   | 飞书电子表格：工作表/单元格操作                    |
| `lark-skill-maker`              | 飞书自定义 Skill 创建                              |
| `lark-slides`                   | 飞书幻灯片：创建与编辑                             |
| `lark-task`                     | 飞书任务：待办、清单、任务智能体                   |
| `lark-vc`                       | 飞书视频会议：历史会议查询、纪要获取               |
| `lark-vc-agent`                 | 飞书会议机器人：入会/离会/实时事件                 |
| `lark-whiteboard`               | 飞书画板：架构图/流程图/时序图                     |
| `lark-wiki`                     | 飞书知识库：空间管理、节点组织                     |
| `lark-workflow-meeting-summary` | 会议纪要整理工作流                                 |
| `lark-workflow-standup-report`  | 日程待办摘要工作流                                 |

### 企业微信（7 个）

| 技能                  | 说明                         |
| --------------------- | ---------------------------- |
| `wecomcli-contact`    | 通讯录成员查询               |
| `wecomcli-doc`        | 文档/智能表格/智能文档管理   |
| `wecomcli-meeting`    | 会议创建与管理               |
| `wecomcli-msg`        | 消息收发与会话查询           |
| `wecomcli-schedule`   | 日程管理                     |
| `wecomcli-smartsheet` | 智能表格：子表/字段/记录管理 |
| `wecomcli-todo`       | 待办事项管理                 |

### 其他

| 技能                        | 说明                                             |
| --------------------------- | ------------------------------------------------ |
| `anysearch`                 | 实时搜索引擎：网页搜索、垂直域搜索、URL 内容提取 |
| `cli-anything-computer-use` | 浏览器自动化（computer-use MCP）                 |
| `smart-search`              | 基于 OpenCLI 命令的智能搜索路由器                |

## 迁移指南

### Trae → Cursor

1. **Rules**：将 `.trae/rules/*.md` 复制到 `.cursor/rules/`，扩展名改为 `.mdc`，添加 YAML Frontmatter：
   ```yaml
   ---
   description: 规则描述
   globs: ["**/*"]
   alwaysApply: true
   ---
   ```
2. **MCP**：`mcp.json` 格式基本通用，直接复制即可（路径差异见上表）
3. **Skills**：Cursor 无独立 Skill 概念，将 SKILL.md 内容合并到 `.cursor/rules/` 中

### Trae → Windsurf

1. **Rules**：将所有 `.md` 规则内容合并为项目根目录的 `.windsurfrules` 单文件
2. **MCP**：配置文件放到 `~/.codeium/windsurf/mcp_config.json`

### Trae → Claude Code

1. **Rules**：将规则内容合并为项目根目录的 `CLAUDE.md`
2. **MCP**：Claude Code 通过 `mcpServers` 配置，格式通用

## 使用方法

```bash
# 克隆仓库
git clone <repo-url> ~/.ai-ide-config

# Trae 用户：软链接 skills
ln -s ~/.ai-ide-config/skills/* ~/.trae/skills/

# Trae 用户：软链接 MCP 配置（按需编辑）
cp ~/.ai-ide-config/ides/trae/mcp/global-mcp.json ~/.trae/mcp.json

# Trae 用户：软链接规则
cp ~/.ai-ide-config/ides/trae/rules/user_rules.md <对应路径>
```

## 安全提醒

- `ides/trae/mcp/global-mcp.json` 中的 API 密钥已脱敏为占位符（`<YOUR_XXX>`），使用前需替换为真实值
- 不要将包含真实密钥的配置文件提交到仓库
