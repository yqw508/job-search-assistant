# Vue 后台说明

后台管理界面使用 Vue 3、Vite 和 Element Plus，源码在 `frontend/`，构建产物在 `frontend/dist/`。

## 本地开发

先启动 Python 本地服务，再启动前端开发服务器：

```powershell
python -m boss_job_assistant.local_service
cd frontend
npm.cmd install
npm.cmd run dev
```

Vite 会把 `/api` 请求代理到 `http://127.0.0.1:8765`。

## 构建和打包

```powershell
cd frontend
npm.cmd run build
```

Windows 打包脚本 `scripts/package_windows.bat` 会自动安装前端依赖、执行前端构建，并把 `frontend/dist` 打进 `dist/JobSearchAssistant.exe`。

如果 npm 官方源较慢，可以先手动安装：

```powershell
cd frontend
npm.cmd install --registry=https://registry.npmmirror.com
```
