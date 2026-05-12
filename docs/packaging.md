# Windows 安装包构建说明

这个项目可以打包成两种交付物：

- `dist/JobSearchAssistant.zip`：免安装便携包，解压后运行 `job-search-assistant/job-search-assistant.exe`。
- `dist/JobSearchAssistantSetup.exe`：Windows 安装包，安装后会创建开始菜单和桌面快捷方式。

## 构建环境

- Windows
- Python 3.10 或更新版本
- 可访问 PyPI，用于安装 PyInstaller
- 可选：Inno Setup，用于生成 `Setup.exe`

如果没有安装 Inno Setup，脚本仍然会生成便携 zip。

## 一键构建

在项目根目录运行：

```powershell
.\scripts\package_windows.bat
```

脚本会执行：

1. 检查 Python。
2. 安装 `requirements-build.txt` 中的构建依赖。
3. 使用 PyInstaller 生成本地服务 exe。
4. 复制 `extension`、`docs`、`README.md` 和默认配置。
5. 生成便携 zip。
6. 如果检测到 `ISCC`，继续生成 Inno Setup 安装包。

## 朋友安装后的体验

安装完成后，朋友只需要：

1. 双击桌面上的“求职助手”。
2. 程序启动本地服务并自动打开 `http://127.0.0.1:8765`。
3. 按 README 或页面提示加载浏览器扩展。
4. 在 Boss 打开岗位详情，点击扩展收藏岗位。

Chrome/Edge 不允许普通安装包静默安装扩展，所以扩展仍需要用户手动加载。后续如果上架 Chrome Web Store 或 Edge Add-ons，可以把这一步进一步简化。

## 数据目录

安装版不会把数据库写到安装目录，而是写到当前用户目录：

```text
%LOCALAPPDATA%\JobSearchAssistant\output\boss_jobs.sqlite3
```

用户配置文件位于：

```text
%LOCALAPPDATA%\JobSearchAssistant\config.yaml
```

这样普通用户不需要管理员权限，也不会因为软件升级覆盖自己的数据。
