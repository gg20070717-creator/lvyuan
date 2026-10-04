# 旅鸢 · lvyuan

**旅鸢——中国入境游旅行定制师多智能体协同实训平台**

面向中国入境游旅行定制师的个性化学习与多智能体协同实训平台，包含知识学习、学情画像、能力自评、学习路线、情景沙盒、AI 对话和实用工具。

知识库包含 7 个领域、3796 个技能点及 30944 道题。前端采用蓝白配色和组件内国风装饰，页面背景保持简洁；学习路线页面保留原有布局与金色连线。

## 本地开发

需要 Python 3.11+、Node.js 20+ 和 Git。克隆后按以下步骤启动开发环境：

```powershell
git clone https://github.com/gg20070717-creator/lvyuan.git
cd lvyuan
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item local.env.example local.env
npm --prefix sinanlike/frontend ci
```

在 `local.env` 中填写自己的 `DEEPSEEK_API_KEY`。AI 对话需要密钥；知识库与题库随仓库提供。实时语音需要另行配置 `DASHSCOPE_API_KEY`。

终端一，在仓库根目录启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn brain_of_cloud.api.app:create_app --factory --host 127.0.0.1 --port 18000 --reload
```

终端二，在仓库根目录启动前端：

```powershell
npm --prefix sinanlike/frontend run dev
```

访问 <http://127.0.0.1:5173/>。后端健康检查为 <http://127.0.0.1:18000/>，接口文档为 <http://127.0.0.1:18000/docs>。前端开发代理和生产配置均使用 18000 端口。

## 项目结构

| 目录 | 内容 |
| --- | --- |
| `sinanlike/frontend/` | 当前 Vue 3 + TypeScript 前端、设计资源、Electron 入口 |
| `brain_of_cloud/` | FastAPI 后端、智能体、知识库引擎、记忆与训练服务 |
| `data/` | 共享知识库、题库及数据说明 |
| `tests/` | 原项目单元测试 |
| `competition_eval/` | 评测工具 |
| `scripts/` | 数据整理、验证与评测脚本 |
| `docs/` | 协作指南与进度记录 |

## 验证

```powershell
npm --prefix sinanlike/frontend run build
.\.venv\Scripts\python.exe -m pytest -q
```

前端构建执行 TypeScript 检查并生成 `sinanlike/frontend/dist/`。调用真实模型的验证脚本位于 `scripts/`，运行前查看脚本要求，它们可能调用付费模型。

## 同步与协作

组员先接受仓库协作邀请。每次开工同步 `main`，为自己的工作创建分支，提交后通过 Pull Request 合并。命令和邀请入口见 [协作指南](docs/协作指南.md)，已完成工作见 [进度记录](docs/进度记录.md)。

每位组员自行配置 `local.env`；个人学习记录、数据库与日志保留在本机。安装包、便携运行时、缓存和个人密钥不参与版本管理。目录名 `sinanlike` 延续本地部署路径，项目对外名称统一为“旅鸢”。
