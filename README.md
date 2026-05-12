# 求职助手

一个本地个人求职工作台，用来长期保存岗位、沉淀技能点、记录面试并反推学习补齐。当前第一期支持 Boss，后续可以继续接入猎聘、拉勾、智联、前程无忧或手动录入。

核心闭环：

```text
岗位收集 -> 技能点收集 -> 面试记录 -> 技能点补齐 -> 继续筛选岗位
```

## 现在能做什么

- 收藏当前来源的岗位，长期保存岗位信息、职位描述、匹配度和跟进状态。
- 从职位描述里提取技能点，形成自己的技能库。
- 维护项目经验，把项目和技能点关联起来。
- 记录每次面试，把面试问题关联到技能点。
- 自动统计被问最多、答得不好的技能，用来指导后续学习和项目表达。
- 在本地后台管理岗位列表、岗位详情、技能库、项目经验、面试记录和匹配配置。

## 安全边界

本项目不会批量打开岗位详情页，也不会循环点击 Boss 页面。扩展只读取当前页面已经展示出来的岗位内容，再发送给本机服务。

这意味着你仍然需要自己判断哪些岗位值得收藏。程序负责长期保存、整理、评分和复盘。

## 快速开始

### 1. 准备环境

- Windows
- Python 3.10 或更新版本
- Chrome 或 Edge

### 2. 启动本地服务

在项目目录双击或执行：

```powershell
.\start_service.bat
```

脚本会自动检查 Python、pip 和依赖包。启动成功后打开：

```text
http://127.0.0.1:8765
```

默认数据库位置：

```text
output/boss_jobs.sqlite3
```

### 3. 加载浏览器扩展

Chrome 或 Edge：

1. 打开扩展管理页面。
2. 开启“开发者模式”。
3. 选择“加载已解压的扩展”。
4. 选择项目里的 `extension` 目录。
5. 工具栏会出现“求职助手”。

### 4. 收藏岗位

1. 用平时的浏览器正常打开 Boss。
2. 手动打开一个感兴趣的岗位详情。
3. 点击扩展里的“收藏当前岗位”。
4. 回到 `http://127.0.0.1:8765` 查看岗位和匹配分析。

## 本地后台页面

- `总览`：查看岗位数量、投递和面试状态概览。
- `岗位列表`：筛选、排序、分页查看已收藏岗位。
- `岗位详情`：查看职位描述、匹配分析、记录面试。
- `技能库`：查看从岗位和面试中沉淀的技能点。
- `项目经验`：维护项目，并关联到技能点。
- `面试记录`：记录面试轮次、问题、技能点和回答表现。
- `配置`：维护薪资、地点、公司规模、关键词、通勤等匹配规则。

## 数据库说明

本项目使用 SQLite，本地文件默认在 `output/boss_jobs.sqlite3`。可以用 Navicat 打开。

SQLite 不支持 MySQL 那种原生表注释，所以项目内置了 `schema_comments` 表：

```sql
SELECT *
FROM schema_comments
ORDER BY table_name, object_type, column_name;
```

## 配置

配置文件是 `config.yaml`。常用项：

```yaml
filters:
  min_salary_k: 22
  min_company_size: 100
  required_location: 广州

scoring:
  positive_keywords:
    - Java
    - Spring Boot
    - Redis
  c_side_keywords:
    - C端
    - 用户
  exclude_keywords:
    - 外包
    - 驻场
```

薪资匹配按薪资范围上限判断。例如最低薪资配置为 `22K` 时，`12-24K` 会被认为满足条件，因为上限是 `24K`。

## 开发与测试

安装开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

运行测试：

```powershell
python -m pytest -v
node --check extension\content.js
node --check extension\popup.js
node tests\extension\content_parser_test.js
node tests\extension\popup_static_test.js
```

## 打包给朋友使用

可以生成 Windows 便携包或安装包：

```powershell
.\scripts\package_windows.bat
```

脚本会用 PyInstaller 把本地服务打成 exe，并生成 `dist/JobSearchAssistant.zip`。如果电脑上安装了 Inno Setup，还会继续生成 `dist/JobSearchAssistantSetup.exe`。

安装版启动后会自动打开本地后台，数据保存在 `%LOCALAPPDATA%\JobSearchAssistant`。浏览器扩展仍需要用户按提示手动加载，这是 Chrome/Edge 的安全限制。

更详细的构建说明见 [Windows 安装包构建说明](docs/packaging.md)。

## 多招聘网站预留

当前只实现 Boss 采集，但数据层已经按多来源设计：岗位唯一键为 `source:source_job_id`，例如 `boss:https://www.zhipin.com/job_detail/xxx.html`。后续接入猎聘、拉勾、智联、前程无忧或手动录入时，只需要新增对应来源适配器，把页面数据转换成统一的岗位字段，再交给本地服务保存。

旧版直接用 Boss URL 做唯一键的数据会在启动时自动迁移为 `boss:<标准化岗位详情 URL>`，避免列表页和详情页保存成两条记录。

## 项目文档

- [用户指南](docs/user-guide.md)
- [开发指南](docs/development.md)
- [Windows 安装包构建说明](docs/packaging.md)
- [产品闭环与路线图](docs/product-loop.md)
- [用户体验 Review](docs/ux-review.md)
- [扩展手工验证清单](docs/extension-manual-test.md)
 
