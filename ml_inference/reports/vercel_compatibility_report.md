# Vercel Python Function 兼容性审计

## 结论

代码结构符合 Vercel `api/*.py` Python Function 的文件约定，并使用标准库 `BaseHTTPRequestHandler`，没有引入常驻 FastAPI 进程。Vite 构建成功，Python 模型未进入 `dist`。本阶段未执行正式部署。

## 运行时与依赖

- 冻结训练环境：Python 3.12.13、joblib 1.5.3、scikit-learn 1.9.0、pandas 2.3.3、NumPy 2.5.1。
- 根目录 `requirements.txt` 固定上述版本，并固定 SciPy 1.18.0。
- 本地兼容环境按这些版本加载原 joblib 成功。
- 冻结辅助产物共 19,932,325 字节，其中模型 19,105,075 字节。
- Windows 本地安装的固定 Python 依赖实占约 306,549,683 字节；依赖与辅助产物合计约 326,482,008 字节（311.36 MiB）。这是本地未压缩测量值，云端 Linux wheel 体积可能不同，应以 Vercel 构建产物为最终依据。
- 首次模块与模型加载约 3.01 秒；首次预测约 0.21 秒；热预测约 0.17 秒；本地进程工作集约 184,250,368 字节（175.71 MiB）。这些是单机测量，不是云端 SLA。

## 打包检查

- 未增加 `vercel.json`，当前依赖 Vercel 自动检测 `api/` 与 Vite 构建。新增 `.vercelignore` 只排除原始数据、冻结实验目录、文档、本地依赖和缓存，避免将历史模型重复打入部署包；它明确保留 `ml_inference/frozen_assets/` 中的部署模型副本。
- `.gitignore` 不排除 `ml_inference/frozen_assets/` 或 `.joblib`；部署模型不会被意外忽略。
- 项目本地 `.python-deps/` 已加入 `.gitignore`，不会作为部署文件提交。
- Vite `dist` 约 3,093,815 字节，未发现 `.joblib`、Pipeline 或 Python 文件。
- Vite 构建成功，但仍有既有大型 JavaScript chunk 警告；该警告与 Python 模型无关。

## 风险与建议

标准函数的主要风险是科学计算依赖使构建体积和冷启动增加。当前本地未压缩总体积没有显示立即阻塞，但正式部署前仍需在 Vercel 预览环境核对 Linux 构建包大小、Python 3.12 运行时、冷启动、内存和超时。若标准函数实测受限，应按顺序评估 Large Python Function；仍不满足时再提出独立 FastAPI 服务；模型格式转换只能在严格等价验证后考虑。本阶段不执行这些迁移。
