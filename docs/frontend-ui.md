# 北风前端 UI

## 当前实现

这是现有 Vue 前端的改造，不是独立静态演示。沿用现有 FastAPI 配置、预设、会话恢复、结束与 SSE 接口。

- `/#/`：序厅。阿尔萨斯与象征残存人性的小男孩组成全幅抽象彩绘玻璃壁画；文字与导航处在同一视觉空间中，不使用装裱图片作为页面主视觉。
- `/#/settings`：面试准备。目标岗位、学历、语言、面试官身份与职责、预设读取／删除，以及减少动效开关。
- `/#/interview`：独立面试室。真实会话配置、轮次、对话、发送状态、错误同步、结束确认。
- `/#/review`：本次对话回顾和 TXT 导出。统计来自当前会话，没有伪造评分。结束后的页面内记录可导出，但后端不提供已结束会话的重新读取，界面已明确提醒。

Vue Router 使用 hash 路由与懒加载页面。共享状态独立于页面组件，切页不会清空对话或中断正在进行的请求；刷新通过已有生命周期 API 恢复。连接结果不确定时禁用重复发送，要求先同步。

## 视觉与动效

采用深蓝、酒红、暗绿、旧金和近黑铅线；全幅寓言壁画与哥特拱形导航、玻璃色块分区、玫瑰窗几何、金色控件统一。表单与对话区域使用深色覆盖层保证阅读。内页延续同一套材料与结构，不回退为白色卡片页面。

首页文字分阶段入场，页面以淡入／轻微位移切换，消息与确认窗口有短入场动画，按钮与导航有交互反馈。动效遵循系统 `prefers-reduced-motion`，也可在设置中手动减少并持久保存。未引入持续粒子、闪烁光束或自动播放音效。

布局覆盖窄屏，320px、390px 与 768px 使用真实浏览器 iframe 验收响应式 CSS；这不是实体手机设备测试。

## 验证边界

- `cd src/frontend && npm run build`：Vue 类型检查与生产构建。
- `cd src/frontend && npm test`：API 合同与共享状态测试，覆盖防重复发送、错误同步、结束状态和导出内容。
- 浏览器实际操作：首页跳转、表单保存、预设载入、发送、回车发送、切页保留、刷新恢复、结束确认／取消、回顾和导出触发、减少动效。
- 浏览器验收后端使用 `tests/lifecycle_server.py`：真实 HTTP、Graph 和 checkpointer，加确定性测试模型。没有验证外部大模型响应质量，也没有声称真实模型 E2E 已通过。
- 本轮没有修改后端接口，没有新增评分、语音或文件上传能力。

## 壁画资产

当前页面资产：`src/frontend/src/assets/allegory-mural.png`。由内置 imagegen 生成，已保存到仓库工作区；不会依赖用户目录中的生成缓存。人物是寓言性视觉演绎，不宣称是官方剧情原画。

生成方式：内置工具，参考上一版已确认的深色抽象彩绘玻璃壁画。最终提示词：

```text
Use case: stylized-concept. Asset type: full-bleed panoramic website mural, landscape 16:9. Image 1 is the reference for dark palette, stained glass craft and panoramic structure; create a new, MORE ABSTRACT composition of Arthas and the little boy representing his former humanity. Mythic, allegorical medieval sacred mural, not a game splash portrait. Entire canvas is stained glass, with thick irregular black lead boundaries, flat angular lapis blue, midnight blue, oxblood, dark emerald, muted antique gold. On RIGHT HALF a monumental faceted crowned silhouette of Arthas, unmistakable spiked crown and white angular hair, mostly dark blue armour, holding a long vertical Frostmourne. Near the LOWER CENTER LEFT stands a very small golden-haired boy in simple muted gold/ivory clothing, facing the king with one hand softly raised. The king and boy read as two aspects of the same self, an intimate tragic encounter, with a tall sword and fissure dividing their worlds. No stabbing, no gore, no photoreal faces. The figures dissolve into the same interlocking glass facets as the Gothic arches and pointed tracery. Make them iconic and abstract, reduced facial details, strong solemn silhouette, large calm planes. Give the upper-left 40 percent very dark low-detail blue and burgundy glass within broad Gothic arches for website typography overlay; keep meaningful boy figure lower center around x45%,y70%, away from upper-left text area. Use narrow muted gold lines and small amber highlights, overall darkness rich and deep. Mythological narrative mural like an ancient cathedral window, atmospheric and restrained, no sunlight beams, no neon, no particles, no game UI, no lettering, no logos, no margins, no picture frame. The entire webpage will be inside this mural, not a little framed picture.
```
