# 开发指南

## 架构

项目由两部分组成：

- Chrome/Edge 扩展：读取当前 Boss 页面里的岗位详情。
- Python 本地服务：保存岗位、评分、展示后台页面、维护 SQLite。

本地服务监听：

```text
http://127.0.0.1:8765
```

## 主要目录

```text
extension/                         浏览器扩展
src/boss_job_assistant/            Python 本地服务
tests/                             Python 测试
tests/extension/                   扩展解析和静态测试
docs/                              中文文档
```

## 核心模块

- `local_service.py`：HTTP 服务、页面渲染、接口路由。
- `storage.py`：SQLite 建表、迁移、读写函数。
- `scorer.py`：岗位匹配规则。
- `skills.py`：职位描述技能点提取。
- `models.py`：岗位和评分数据结构。
- `extension/content.js`：Boss 页面解析。
- `extension/popup.js`：扩展弹窗和本地服务交互。

## 数据库

初始化入口是 `storage.init_db()`。新增表时需要同步：

- 建表 SQL。
- `SCHEMA_COMMENTS` 中文注释。
- 存储层测试。

SQLite 没有原生字段注释，项目使用 `schema_comments` 表承载注释。

## 本地开发

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v
node --check extension\content.js
node --check extension\popup.js
node tests\extension\content_parser_test.js
node tests\extension\popup_static_test.js
```

## 来源适配器约定

系统内部不再把 Boss URL 当成通用主键，统一使用 `source:source_job_id`。当前 Boss 扩展输出 `source="boss"`、`source_url=<当前岗位链接>`，保存层会把 Boss 详情页链接标准化为 `source_job_id`。

后续新增招聘网站时，建议按这个边界接入：

- 页面采集层只负责把站点 DOM 转成统一 `JobPosting` 字段。
- 每个来源必须提供稳定的 `source`，例如 `liepin`、`lagou`、`zhilian`、`51job`、`manual`。
- 有详情链接时写入 `source_url`；没有链接的手动岗位会用标题、公司、薪资、地点生成 `manual:<hash>`。
- 评分、技能提取、面试记录和项目经验不关心来源，只依赖统一岗位字段。

## 发布检查

提交到 GitHub 前建议确认：

- README 是中文且无乱码。
- `start_service.bat` 可以从干净环境安装依赖。
- `requirements.txt` 不包含测试或废弃依赖。
- `output/`、`.tmp/`、`.browser-profile*` 等本地文件未提交。
- 所有测试通过。
