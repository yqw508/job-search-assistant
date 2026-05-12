# Boss 岗位助手

这是一个本地半自动浏览器助手，用于个人求职时整理 Boss 直聘上可见的岗位信息。程序会打开可见浏览器，由你手动登录，然后按配置搜索岗位、读取列表和详情、按岗位画像评分，最后导出 Excel。

## 边界

- 不保存账号密码。
- 不绕过验证码或平台验证。
- 不自动投递。
- 不高频并发采集。
- 只整理用户登录后正常可见的信息。

## 一键启动

推荐直接运行启动脚本：

```powershell
.\start.bat
```

脚本会自动完成这些检查：

- 检查 Python 是否可用。
- 检查 pip 是否可用。
- 检查 `playwright`、`PyYAML`、`openpyxl`、`pytest` 是否安装。
- 缺少依赖时执行 `python -m pip install -r requirements.txt`。
- 将 Playwright 浏览器缓存放到项目内的 `.playwright-browsers`。
- 优先用本机已安装的 Google Chrome 或 Microsoft Edge 启动 CDP 附加模式，减少“自动测试软件控制”提示。
- 如果没有找到本机 Chrome/Edge，再执行 `python -m playwright install chromium`。
- 如果默认下载源连接被重置，会自动换备用下载源重试一次。
- 使用项目内 `.browser-profile` 保存浏览器会话，避免每次都从全新的临时浏览器开始。
- 设置 `PYTHONPATH=src` 并启动岗位助手。

如果网络或代理限制导致 Playwright Chromium 下载失败，可以先安装 Google Chrome 或 Microsoft Edge，然后再次运行 `.\start.bat`，脚本会自动复用本机浏览器。

## 如果 Boss 跳到 about:blank

如果浏览器打开 Boss 后几秒自动跳回 `about:blank`，说明 Boss 拦截了自动化或远程调试浏览器。此时推荐使用本地 HTML 导入模式：

1. 用你平时正常使用的 Chrome 或 Edge 打开 Boss。
2. 手动搜索岗位，例如 Java Spring Boot、广州。
3. 等岗位列表出现后，按 `Ctrl+S` 保存网页。
4. 把保存出来的 `.html` 或 `.htm` 文件放到项目目录的 `input_html` 文件夹。
5. 运行：

```powershell
.\import_html.bat
```

程序会解析 `input_html` 里的 HTML 文件，按 `config.yaml` 评分，并导出 Excel 到 `output/`。

## 手动安装

```powershell
python -m pip install -r requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH="$PWD\.playwright-browsers"
python -m playwright install chromium
```

如果运行时提示 Chromium 缺失，再执行一次：

```powershell
python -m playwright install chromium
```

## 运行

在项目根目录运行：

```powershell
$env:PYTHONPATH="src"
$env:PLAYWRIGHT_BROWSERS_PATH="$PWD\.playwright-browsers"
$env:BOSS_BROWSER_CHANNEL="msedge"
python -m boss_job_assistant.boss_job_assistant config.yaml
```

如果已经执行过可编辑安装：

```powershell
pip install -e .
```

之后可以直接运行：

```powershell
python -m boss_job_assistant.boss_job_assistant config.yaml
```

## 配置

主要配置在 `config.yaml`：

- `search.keyword`：搜索关键词，默认是 `Java Spring Boot`。
- `search.city`：城市名称，默认是 `广州`，用于展示和兜底。
- `search.city_code`：Boss 城市码，广州默认是 `101280100`。
- `search.max_pages`：最多采集页数，首次建议设为 `1`。
- `search.detail_pages`：是否进入详情页读取岗位描述。
- `filters.min_salary_k`：最低薪资下限，单位 K。
- `filters.min_company_size`：最低公司人数。
- `filters.required_location`：要求工作地。
- `scoring.positive_keywords`：技术加分关键词。
- `scoring.c_side_keywords`：C 端业务加分关键词。
- `scoring.exclude_keywords`：排除关键词，例如外包、驻场、派遣。
- `runtime.output_dir`：Excel 输出目录，默认是 `output`。

结果会导出到 `output/boss_jobs_*.xlsx`。

## 首次使用建议

首次运行前，建议先把 `search.max_pages` 改成 `1`：

1. 程序打开浏览器后，会在终端打印一个 Boss 搜索地址。
2. 在浏览器地址栏手动粘贴并打开这个地址。
3. 手动登录 Boss，并确认页面上已经出现岗位列表。
4. 回到终端按 Enter，程序开始读取当前页面并导出 Excel。
5. 确认结果正常后，再逐步增加采集页数。

如果出现验证码或平台验证，请在浏览器中手动处理。程序不会绕过验证。

## 手动验证

```powershell
python -m pytest -v --basetemp D:\future\.tmp\pytest
```

真实浏览器端到端验证需要你手动登录 Boss：

```powershell
$env:PYTHONPATH="src"
$env:PLAYWRIGHT_BROWSERS_PATH="$PWD\.playwright-browsers"
$env:BOSS_BROWSER_CHANNEL="msedge"
python -m boss_job_assistant.boss_job_assistant config.yaml
```
