# Crisis Data Terminal / VAULT-0

## 本地启动

首次运行需要准备项目专用 Python 环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

需要运行包含 Excel 回归核验的完整 Python 测试时，改用 `requirements-dev.txt` 安装测试依赖。

以后只使用下面这一条推荐命令启动完整开发环境：

```powershell
npm run dev
```

该命令会依次完成以下操作：

1. 检查项目 Python 环境是否包含冻结模型所需依赖；
2. 在 `127.0.0.1:8000` 启动只读推理 API；
3. 等待 `/api/health` 返回就绪状态；
4. 健康检查通过后才在 `http://localhost:5173` 启动 Vite。

如果 Python API 缺少依赖、模型无法加载、端口被占用或健康检查失败，命令会明确报错并退出，不会留下只有页面而没有 API 的开发环境。

`npm run dev:frontend` 只用于排查纯前端问题，不是日常推荐启动方式；单独使用时预测和输入选项接口不可用。

## Production build 与本地 preview

```powershell
npm run build
npm run preview
```

`npm run preview` 同样会启动冻结模型 API，并在 API 健康检查通过后启动 Vite Preview（默认 `http://localhost:4173`）。不要直接运行 `vite preview`，因为纯静态 Preview 不会自行创建 Python 推理服务。

本地启动不代表已经部署到 Vercel。生产或预览部署仍需单独验证 `/api/impact-options` Python Function 及部署依赖。
