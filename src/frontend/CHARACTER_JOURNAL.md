# 人物志数据接入

数据链路：人物目录 → 发布计划与正文解析 → 浏览器 JSON / 图片 → 人物列表 → 人物总览 → 任意数量的子故事。

## 输入

默认读取本 checkout 的 `src/data/character-journal/characters/<characterId>/`。可以用环境变量 `CHARACTER_JOURNAL_ROOT` 指定另一个 characters 目录。数据目录仍被 Git 忽略，新 worktree 需要准备数据；本次已复制现有发布输入供预览。

- `publication-plan.json`：status=accepted，characterId，bibliography，units；每个人物恰好一个 kind=overview，其余都是子故事，按 displayOrder 排序。可选 characterName；没有时从总览标题推导。
- `units/<unitId>/profile.json`：标题与最新副标题。
- `units/<unitId>/story.md`：正文；支持段落、二至六级标题。首行主标题和紧随的副标题不重复显示。正文按文本渲染，不执行 HTML。
- `preview-manifest.json`：每单元的 imagePath、alt、caption。图片以该清单选定版本为准，不自动选最新文件。

旧清单的 Windows 绝对路径会定位到当前人物目录或 frontend/src/assets，再导出成相对 URL。新数据建议直接用人物目录相对路径，例如 units/dream/images/cover-v002.png。原始小说、阅读笔记和 Agent 审计文件不会导出。

## 运行

```powershell
npm run dev -- --host 127.0.0.1 --port 5175
npm run build
```

两者都会先执行 `npm run journal:sync`，将选定发布内容输出至被 Git 忽略的 public/character-journal；构建时自动进入 dist。开发服务器运行期间修改发布输入后，执行 `npm run journal:sync` 并刷新浏览器；部署时重新构建。不要直接编辑生成的 public 数据。

页面使用 hash 路由：`#/stories`、`#/stories/<characterId>`、`#/stories/<characterId>/<unitId>`。不依赖面试后端。加载失败可重试，无数据、无搜索结果、无效人物和章节均有对应状态。

本次使用原清单已有配图；尚未验收的新生成图片没有接入。
