## trae-mem 规则

### 自动触发（不可跳过）
- Edit/Write/RunCommand 后立即调用 trae_mem_record
- 新会话首条消息先调用 trae_mem_context
- 收到"历史对话已被压缩"时调用 trae_mem_record（tool_name: ContextCompressed）

### 会话归档
- **自动归档**：用户说"结束"或会话即将结束时，自动调用 trae_mem_summarize 生成会话总结
- **手动归档**：用户随时说"归档"或"生成会话总结"时，调用 trae_mem_summarize

### trae_mem_record 参数
- session_id: 当前会话 ID
- project: 当前项目文件夹名
- tool_name: 操作名称（可选，默认 "unknown"）
- tool_input: 操作摘要
- tool_output: 操作结果

### 语音指令
- "关闭/开启/状态 trae-mem" → trae_mem_toggle(false/true/查询)
- "启动 trae-mem 控制面板" → 先 lsof -i :37778 检查，已运行则直接给链接 http://localhost:37778 ，否则执行 `cd ~/.trae-mem && nohup node dist/cli/trae-mem.js worker start > /dev/null 2>&1 &`
- "停止 trae-mem 控制面板" → `cd ~/.trae-mem && node dist/cli/trae-mem.js worker stop`，失败则 lsof 找 PID 后 kill

### 禁止
- 不记录敏感数据（密码、令牌、个人信息）
- 不因操作简单而跳过记录
