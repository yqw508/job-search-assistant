# Windows 单文件 exe 构建说明

这个项目可以打包成两种交付物：

- `dist/JobSearchAssistant.exe`：单文件应用，朋友拿到后直接双击运行。
- `dist/JobSearchAssistantSetup.exe`：可选安装包，安装后会创建开始菜单和桌面快捷方式。

第一阶段优先使用 `JobSearchAssistant.exe`，因为它不需要朋友安装 Python、解压目录或执行命令。

## 构建环境

- Windows
- Python 3.10 或更新版本
- 可访问 PyPI，用于安装 PyInstaller
- 可选：Inno Setup，用于生成 `Setup.exe`

如果没有安装 Inno Setup，脚本仍然会生成单文件 exe。

## 一键构建

在项目根目录运行：

```powershell
.\scripts\package_windows.bat
```

脚本会把完整输出写入：

```text
build\logs\package_windows.log
```

如果双击运行，窗口会在结束时停住，方便查看错误。自动化构建时可以关闭停留：

```powershell
$env:PACKAGE_NO_PAUSE=1
.\scripts\package_windows.bat
```

脚本会执行：

1. 检查 Python。
2. 安装 `requirements-build.txt` 中的构建依赖。
3. 使用 PyInstaller 生成 `dist/JobSearchAssistant.exe`。
4. 把默认配置、浏览器扩展、文档一起打进 exe。
5. 如果检测到 `ISCC`，继续生成 Inno Setup 安装包。

## 朋友使用体验

朋友只需要：

1. 双击 `JobSearchAssistant.exe`。
2. 程序启动本地服务并自动打开 `http://127.0.0.1:8765`。
3. 首次启动时，程序会把扩展文件释放到：

```text
%LOCALAPPDATA%\JobSearchAssistant\extension
```

4. 按 README 或页面提示，在 Chrome/Edge 加载这个扩展目录。
5. 在 Boss 打开岗位详情，点击扩展收藏岗位。

Chrome/Edge 不允许普通 exe 静默安装扩展，所以扩展仍需要用户手动加载。后续如果上架 Chrome Web Store 或 Edge Add-ons，可以把这一步进一步简化。

## 数据目录

单文件 exe 不会把数据库写到 exe 所在目录，而是写到当前用户目录：

```text
%LOCALAPPDATA%\JobSearchAssistant\output\boss_jobs.sqlite3
```

用户配置文件位于：

```text
%LOCALAPPDATA%\JobSearchAssistant\config.yaml
```

这样普通用户不需要管理员权限，也不会因为软件升级覆盖自己的数据。
