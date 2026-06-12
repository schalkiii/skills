# 用户全局规则（Trae User Rules）

> 此文件为 Trae 全局规则模板，适用于所有项目。
> 在 Trae 中通过 Settings > Rules > Create > Global 创建。

## 语言与交互

- 所有回答使用中文
- 批量提问，禁止分批中断

## 代码修改流程

1. 变更影响分析
2. 历史经验参考（检索 Skill 文档）
3. 代码修改执行（遵循项目风格）
4. 文档同步更新
5. 完整性自检
6. 收尾清理与提交

## Trae-Mem 规则

- Edit/Write/RunCommand 后自动调用 trae_mem_record
- 新会话首条消息先调用 trae_mem_context
- 收到"历史对话已被压缩"时调用 trae_mem_record
