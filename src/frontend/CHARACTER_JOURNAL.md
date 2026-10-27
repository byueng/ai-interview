# 人物志数据接入

数据链路：人物目录 → 发布计划与正文解析 → 浏览器 JSON / 图片 → 人物列表 → 人物总览 → 任意数量的子故事。

## 输入

默认读取本 checkout 的 `src/data/character-journal/characters/<characterId>/`。可以用环境变量 `CHARACTER_JOURNAL_ROOT` 指定另一个 characters 目录。发布输入随仓库保存，生成的 `public/character-journal` 被 Git 忽略；新 worktree 在开发或构建前自动导出。

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

## 萨尔完整接入（2026-10-27）

源素材来自 `src/data/character-journal/batches/a-20261024/characters/thrall/`。按用户明确选择的“全部 12 篇图文”，接入人物总览与全部十一篇故事，保存在 `characters/thrall/` 的发布清单中：

1. 萨尔：自由、家园与责任（人物总览）
2. 锁链中的名字
3. 为自己选择一个名字
4. 接过毁灭之锤
5. 让部落拥有家园
6. 和平不能只靠承诺
7. 一个接班决定
8. 卸下铠甲之后
9. 英雄之外的自己
10. 以理解重新联结
11. 世界与旧盟友之间
12. 没有结束的审判

每篇复制已有正文和对应彩绘玻璃配图，使用当前 checkout 内的相对路径。原批次的策划、审核和未发布状态记录保留；本次接入选择单独记录在人物目录的 `publication-plan.json`。

入口：`#/stories/thrall`；第一篇：`#/stories/thrall/thrall-part-01`；最后一篇：`#/stories/thrall/thrall-part-11`。十二篇正文与原制作校验记录在统一换行符后相符，十二张图片的 SHA256 与原记录一致。这里记录的是前端接入范围，不代表线上部署。
