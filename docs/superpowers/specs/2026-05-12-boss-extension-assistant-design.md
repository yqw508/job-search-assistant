# Boss 浏览器扩展岗位助手设计文档

## 目标

将当前 Boss 岗位助手的主流程从 Playwright 浏览器控制改为“正常浏览器扩展 + 本地 Python 服务”模式。

用户用自己平时的 Chrome 或 Edge 正常打开 Boss 搜索结果页，点击扩展按钮采集岗位。扩展在当前页面读取岗位卡片 DOM，将岗位数据发送给本地服务。本地服务复用现有评分规则和 Excel 导出模块，生成岗位筛选结果。

这个方案的核心目标是降低操作门槛，避免 Playwright、远程调试端口或自动化浏览器触发 Boss 将页面跳转到 `about:blank`。

## 用户体验

第一版目标体验：

1. 用户双击 `start_service.bat`。
2. 本地服务启动并监听 `127.0.0.1`。
3. 用户正常打开 Chrome 或 Edge，进入 Boss 搜索结果页。
4. 用户点击浏览器扩展按钮。
5. 用户点击“采集当前页”或“采集并翻页”。
6. 扩展读取页面中的岗位卡片。
7. 扩展把岗位数据发送给本地服务。
8. 本地服务评分并导出 Excel 到 `output/`。
9. 扩展弹窗显示导出结果路径和采集数量。

## 安全与合规边界

- 不保存 Boss 账号和密码。
- 不绕过验证码、登录校验或平台访问控制。
- 不自动投递岗位。
- 不自动和招聘方沟通。
- 不直接请求 Boss 内部接口。
- 只读取用户正常登录后页面上已经展示的岗位信息。
- 自动翻页必须低频执行，并在页面出现验证、异常或无法找到下一页时停止。

## 推荐方案

采用 Chrome Manifest V3 扩展 + 本地 Python HTTP 服务。

扩展负责页面内采集，因为它运行在用户正常浏览器会话里，不需要 Playwright 控制浏览器。本地服务负责配置、评分和导出，复用现有 Python 代码，避免把复杂规则写进扩展。

## 模块设计

### `src/boss_job_assistant/local_service.py`

本地 HTTP 服务：

- 监听 `127.0.0.1:8765`。
- 提供健康检查接口 `GET /health`。
- 提供岗位导出接口 `POST /jobs/export`。
- 接收扩展发送的岗位 JSON。
- 将 JSON 转成 `JobPosting`。
- 调用 `score_job` 评分。
- 调用 `export_jobs` 导出 Excel。
- 返回导出文件路径、岗位数量、匹配数量。

第一版使用 Python 标准库 `http.server` 实现，避免新增 FastAPI/Flask 依赖。

### `start_service.bat`

Windows 启动脚本：

- 切换到项目根目录。
- 清理会影响 pip 的 `SSLKEYLOGFILE`。
- 检查 Python。
- 检查并安装必要依赖。
- 设置 `PYTHONPATH=src`。
- 启动 `local_service.py`。
- 在终端显示服务地址和扩展使用提示。

### `extension/manifest.json`

Chrome/Edge 扩展配置：

- 使用 Manifest V3。
- 允许在 `https://www.zhipin.com/*` 页面运行内容脚本。
- 允许访问本地服务 `http://127.0.0.1:8765/*`。
- 定义弹窗页面 `popup.html`。
- 注入 `content.js` 读取岗位 DOM。

### `extension/popup.html`

扩展弹窗界面：

- 显示本地服务状态。
- 按钮：“采集当前页”。
- 数字输入：“最多翻页数”，默认 1，第一版限制 1-3。
- 按钮：“采集并导出”。
- 显示采集数量、匹配数量、Excel 路径和错误信息。

### `extension/popup.js`

扩展弹窗逻辑：

- 检查本地服务是否可用。
- 向当前 Boss 标签页发送采集指令。
- 接收 `content.js` 返回的岗位列表。
- 将岗位列表发送给本地服务。
- 展示导出结果。

### `extension/content.js`

页面采集脚本：

- 从当前 Boss 搜索结果页读取岗位卡片。
- 提取岗位名称、薪资、地点、经验、学历、公司、行业、融资、公司规模、岗位链接和页面文本摘要。
- 支持低频点击下一页并继续采集。
- 每次翻页后等待岗位列表更新。
- 遇到验证码、登录页、没有下一页或解析不到岗位时停止。

## 数据格式

扩展发送给本地服务的 JSON：

```json
{
  "source": "boss-extension",
  "jobs": [
    {
      "title": "Java 后端开发工程师",
      "salary": "25-35K",
      "location": "广州",
      "experience": "5-10年",
      "education": "本科",
      "company": "示例公司",
      "industry": "电商",
      "financing": "B轮",
      "company_size": "100-499人",
      "url": "https://www.zhipin.com/job_detail/example.html",
      "description": "岗位卡片和页面可见文本摘要"
    }
  ]
}
```

本地服务返回：

```json
{
  "ok": true,
  "received": 20,
  "matched": 8,
  "output_file": "D:\\future\\output\\boss_jobs_20260512_120000_000000.xlsx"
}
```

## 错误处理

- 本地服务未启动：扩展提示先运行 `start_service.bat`。
- 当前页面不是 Boss 页面：扩展提示进入 Boss 搜索结果页。
- 未解析到岗位：提示检查页面是否加载完成或是否处于验证页。
- 翻页失败：保留已采集数据并停止。
- 本地服务导出失败：返回错误信息并在弹窗展示。

## 测试策略

- Python 单元测试：
  - `local_service` JSON 解析。
  - `JobPosting` 转换。
  - 导出接口成功返回。
  - 空岗位列表错误。
- 扩展脚本测试：
  - 使用保存的 HTML 片段测试 `content.js` 的 DOM 解析函数。
  - 测试下一页按钮不存在时停止。
- 手动端到端测试：
  - 启动本地服务。
  - 加载未打包扩展。
  - 打开 Boss 搜索结果页。
  - 点击“采集当前页”。
  - 检查 Excel 文件生成。

## 第一版范围

第一版实现：

- 本地服务。
- 启动服务脚本。
- Chrome/Edge 未打包扩展。
- 当前页采集。
- 最多 1-3 页低频翻页采集。
- Excel 导出。
- README 中的扩展安装和使用说明。

第一版不实现：

- 自动投递。
- 自动聊天。
- 后台长期定时采集。
- 绕过验证码。
- 直接调用 Boss 内部接口。
- 扩展商店发布。
