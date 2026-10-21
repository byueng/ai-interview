# dream 插画构图

runId: arthas-20261021-02；characterId: arthas；role: art_director；status: ready_for_illustration；revision: 2；retryCount: 1；imageMode: chapter_scene。

小标题：梦（original，已通过校核；来源 text00306:p0001）。小标题只作主题指导，不画进图片。

场景与情绪：虚幻大厅的长桌三者对峙；男孩爬回座椅，仍带希望。

事实证据：text00306:p0017–p0035，并对应已审核正文。

外貌与造型边界：原文：长桌、略高主位的雕花椅（不是王座）、老而强壮且脸绘骷髅的兽人、金发病弱男孩、炉火、敞门飞雪。原文未在本场明确男人服装与发式：暗蓝长衣、灰白长发及成年无须脸型属于视觉创作；兽人在男人自身左侧则是原文明确位置；不以王冠或魔剑提前解释身份。

构图：横向16:9，单场景；核心人物及道具放在横向15%–85%、纵向12%–88%安全区。背景可裁切；实际展示裁切尚未验证。

图注：梦境中的长桌：男孩仍未放弃。

完整生成提示词（与generation-prompt.txt逐字一致）：

```text
制作一张横向16:9的完整中世纪彩绘玻璃作品，单一连续空间，无拼贴分镜。人物面孔、手、衣物、道具、建筑和背景全部由清晰深色铅条分割的彩色玻璃构成；扁平而有表情的中世纪造型，透光宝石色、细微玻璃气泡及不均匀纹理，拒绝摄影写实、塑料质感和普通插画外加玻璃边框。让铅条与故事轮廓融合，装饰性拱线仅服务空间。所有面孔、手势和关键道具完整位于画面横向15%至85%、纵向12%至88%的安全区；四边保留可裁切背景，锤顶等道具不得贴边。No text, no lettering, no readable runes, no captions, no watermark, no logo, no UI。不添加现实宗教十字架或无关圣像。

在一座梦中的宽阔木梁大厅内，一张沉重雕花长桌连接且只容纳画中三位角色：远端中央略高的宽大雕花椅上坐着成年阿尔萨斯，成年而非老年脸型，清晰下颌，无明显胡须、无老人皱纹，衣着暗蓝、灰白长发，双臂向两侧微张；注意这把椅子不是王座，无王冠。严格按观看者的画面方位：画面右侧（面向观众的男人自身左侧）坐着老迈但强壮的兽人，粗大下颌，脸上骷髅彩绘，姿态强势。画面左侧是清瘦金发男孩，眼睛呈灰绿而略有白翳，面容苍白虚弱，刚用双手撑扶椅沿爬回座椅，抬头看向男人，目光仍有一点希望，不绝望。用瘦削与低垂肩膀表达病弱，不画脓疮、血痰和裸露伤口。背景一个大壁炉燃烧琥珀橘金色火焰，石地铺毛皮，龙头木雕承托火把；一扇敞开的门卷入冰蓝风雪，与炉火构成同一大厅的冷暖交界。长桌透视将三人连接；冰蓝和深紫围住暖火，为男孩的面容保留微暖光。梦境略有波动的玻璃线条，不能画成真实宫廷会议。没有刺杀动作、魔剑、冰封王座、其他客人或旁观者。

布局硬约束：男孩在画面左侧约30%宽处，成年男人在中央50%宽处，兽人在画面右侧约70%宽处。三个人连同肩背、头部、双臂及手指均向中心内收，完整落在横向15%–85%、纵向12%–88%范围，外侧留空背景而非人物。不要左右镜像。雕花长桌桌面清空，不摆餐食、水果、烤肉、酒杯、盘子或宴席；仅保留桌面木纹及玻璃分块。
```

输出目标：本单元一张图片；制作员保存原图、版本化成品及实际提示和模型记录。验收：场景和动作对应证据、时期装备正确、全图铅条与透光玻璃、无文字、单场景、人物及道具裁切安全。v001已生成但视觉审核退回；本次v002尚未生成或验收。

输入SHA256：

```json
{
  "src/data/character-journal/characters/arthas/units/dream/story.md": "5fe731c9fb2e1112be60e558eac5dd311efe76c4e57db7cdbe90027156d874d1",
  "src/data/character-journal/characters/arthas/units/dream/profile.json": "1ac35da37ed853c21c77853894cd30fe703e163f3d7739778a33d0d53bdf9913",
  "src/data/character-journal/characters/arthas/units/dream/text-review.json": "62cc6b86488fead83da6032a609ecbffa7edd7576968b154b4d562d75d1bbd93",
  "src/data/character-journal/characters/arthas/publication-plan.json": "a2ecec7ed63a404f24e0e79d8449674b31c235069f60a76c0f9e0530e622d2d9",
  "src/data/character-journal/workflow/runs/arthas-20261021-02/delegations/art_director.txt": "98a32d7a3d88deae1f6e168a669ed24c685bbcf8f05f806e4c33ab64d92a9c63",
  "src/data/character-journal/characters/arthas/source/epub-v1/text00306.json": "d8416cb7abad64b525a481c00e6b82784952c5b7f57e1b46fe0711054b7e5249",
  "src/data/character-journal/characters/arthas/units/dream/visual-review.json": "1ea1056ee47c605a91fbabb5cd5837595c2ae33093adef7cf2d4e07ffc42e4af",
  "src/data/character-journal/characters/arthas/units/dream/images/cover-v001.png": "b8e5b3ea8dd14937abe8ed08b2e3ee22fe58bdf617ebd5fa9c1fd69287bdb90e"
}
```

修订2：响应V-DREAM-01/02/03，明确画面右兽人/左男孩，全部人物内收，移除餐食；按协调员要求将中央人物调整为无明显老年胡须的成年脸型。编辑目标：images/cover-v001.png；制作员使用edit-prompt-v002.txt，输出images/cover-v002.png，保留v001与旧generation.json记录。

完整编辑提示（与edit-prompt-v002.txt一致）：

```text
编辑提供的dream现有cover-v001图片，保持横向约16:9尺寸、同一梦境大厅、长桌、火炉、敞门风雪、三位角色，以及全图深色铅条和透光彩绘玻璃媒介。只进行以下连贯修正：

1. 明确交换两侧角色位置：兽人必须在观看者画面右侧，即面向观众的中央男人自身左侧；金发病弱男孩必须在观看者画面左侧。男孩约在画面宽30%，成年男人50%，兽人70%。重新衔接桌椅、光照及身体，不能机械镜像或剪贴。
2. 将三人全部向中心内收，所有头脸、肩背、双臂与手指完整位于横向15%–85%、纵向12%–88%安全区，兽人肩背不得贴边，外侧留背景供裁切。保持男孩撑扶座椅、怀着希望望向中央男人；兽人强势，男人在略高雕花椅上。
3. 清空桌面全部烤肉、水果、盘子、酒杯与其他丰盛餐食，仅保留雕花长桌的木纹与玻璃分块，突出内在对峙。
4. 中央男人是成年阿尔萨斯，保留灰白长发、暗蓝衣服，去掉明显老年胡须和深刻老年皱纹，脸型是成年而非老人；不增加头盔、王冠或魔剑。兽人仍老而强壮，骷髅脸彩绘；男孩仍金发瘦弱但非血腥病变。
5. 保留冰蓝深紫与琥珀炉火的冷暖对照，为男孩保留暖光。人物、手、衣物、桌椅和背景继续全部由深色铅条分割的透光纹理玻璃构成，不变成普通油画、照片或玻璃边框插画。单一连续空间，恰好三人，无新增角色、无刺杀动作。No text, no lettering, no readable runes, no watermark, no logo, no UI。
```
