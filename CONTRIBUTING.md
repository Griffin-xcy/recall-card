# 贡献指南

感谢你有意为「拾记 Recall Card」做贡献。这是一个本地运行的个人知识整理工具，欢迎提交问题报告、功能建议和代码。

## 本地开发

要求 Python 3.12+ 与 Node.js 22+，详见 [README.md](./README.md) 的「本地开发」一节。

```bash
python -m venv .venv
# Windows: .venv\Scripts\python -m pip install -r requirements-dev.txt
# macOS / Linux: .venv/bin/python -m pip install -r requirements-dev.txt
npm install
npm run dev
```

## 提交前自检

提交 PR 前，请确保以下命令全部通过：

```bash
python -m pytest -q      # 后端测试
npm run lint             # 前端代码检查
npm run build            # 前端类型检查与生产构建
```

如改动涉及端到端流程，另请运行：

```bash
npm run test:e2e         # 需本机 Edge，其他系统先 npx playwright install chromium
```

## 提交规范

- 提交信息使用祈使句，简短描述「为什么」而非「做了什么」，例如 `fix: 重新生成失败时回滚原卡片`。
- 一次提交只做一件事，保持提交粒度小而连续。
- 不要提交 `.env`、密钥或任何含敏感信息的文件。

## 提交流程

1. Fork 本仓库并创建分支。
2. 实现改动并补充对应测试。
3. 通过「提交前自检」全部命令。
4. 提交 PR，填写 PR 模板，说明改了什么、为什么、如何验证。

## 代码风格

- 后端遵循现有 Python 风格（类型注解、无多余注释）。
- 前端遵循 ESLint 配置，业务组件使用原生 HTML + 自定义 CSS，不引入新的 UI 框架依赖。
- 错误提示面向普通用户，避免技术术语，尽量给出可操作的下一步。
