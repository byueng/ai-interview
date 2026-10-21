# golden-boy 插画构图

runId: arthas-20261021-02；characterId: arthas；role: art_director；status: ready_for_illustration；imageMode: chapter_scene。

小标题：黄金男孩（original，已通过校核；来源 text00307:p0001）。小标题只作主题指导，不画进图片。

场景与情绪：真实受封喜悦，金发青年在祭坛前举起银锤；亲友庆贺。

事实证据：text00311:p0012、p0017–p0024、p0039–p0042，并对应已审核正文。

外貌与造型边界：原文：金发、明亮重甲、仪式肩甲、巨大银色锤头、蓝皮锤柄、祭坛、亲友与法奥的白胡须。具体甲片纹样、观众布局、教堂窗花为视觉创作；锤头符文改为不可读几何刻纹以满足无文字要求。

构图：横向16:9，单场景；核心人物及道具放在横向15%–85%、纵向12%–88%安全区。背景可裁切；实际展示裁切尚未验证。

图注：圣光回应了他，新的骑士举起战锤。

完整生成提示词（与generation-prompt.txt逐字一致）：

```text
制作一张横向16:9的完整中世纪彩绘玻璃作品，单一连续空间，无拼贴分镜。人物面孔、手、衣物、道具、建筑和背景全部由清晰深色铅条分割的彩色玻璃构成；扁平而有表情的中世纪造型，透光宝石色、细微玻璃气泡及不均匀纹理，拒绝摄影写实、塑料质感和普通插画外加玻璃边框。让铅条与故事轮廓融合，装饰性拱线仅服务空间。所有面孔、手势和关键道具完整位于画面横向15%至85%、纵向12%至88%的安全区；四边保留可裁切背景，锤顶等道具不得贴边。No text, no lettering, no readable runes, no captions, no watermark, no logo, no UI。不添加现实宗教十字架或无关圣像。

描绘暴风城大教堂中受封仪式结束的同一喜悦瞬间：十九岁的金发阿尔萨斯位于中央祭坛前，无遮面头盔，穿明亮重甲与仪式肩甲，双手满怀兴奋地把一柄巨大银色战锤举向空中。锤头完整，锤柄缠蓝色皮革，刻纹是不可读的几何装饰。头发仍是金色，面容年轻有生气，笑容开放；天窗暖金光照耀其身体，清晰表现真实接纳与希望。短胖、长白胡须的法奥在旁温暖微笑；导师与少量亲友围拢欢呼鼓掌，低于主角的视觉层次，不遮挡主角双手或锤头。教堂石拱和祭坛构成统一空间，观众只是背景群像。配色金黄、乳白、王室蓝，少量酒红与祖母绿点缀；整幅图明亮庄重而有青春喜悦，不是悲剧预告。没有白发、亡灵、霜之哀伤、巫妖王头盔、阴影怪物、未来事件或血迹。
```

输出目标：本单元一张图片；制作员保存原图、版本化成品及实际提示和模型记录。验收：场景和动作对应证据、时期装备正确、全图铅条与透光玻璃、无文字、单场景、人物及道具裁切安全。当前仅构图文档，图片尚未生成或验收。

输入SHA256：

```json
{
  "src/data/character-journal/characters/arthas/units/golden-boy/story.md": "af21d44dcafc9d7a2be10f9eb3770a33073cea8a8d54a4fa26836e105afdb540",
  "src/data/character-journal/characters/arthas/units/golden-boy/profile.json": "3a72aaffc28db58448ecac3f00bf401673a28441ea077027ee7da62079d017cf",
  "src/data/character-journal/characters/arthas/units/golden-boy/text-review.json": "67317d77adcb7cccc4a5c67dba29136531c5ddacdf129e28929ff675532d6ff8",
  "src/data/character-journal/characters/arthas/publication-plan.json": "a2ecec7ed63a404f24e0e79d8449674b31c235069f60a76c0f9e0530e622d2d9",
  "src/data/character-journal/workflow/runs/arthas-20261021-02/delegations/art_director.txt": "98a32d7a3d88deae1f6e168a669ed24c685bbcf8f05f806e4c33ab64d92a9c63",
  "src/data/character-journal/characters/arthas/source/epub-v1/text00311.json": "cdf1bc77aa89100c8393c6b94f368e78760588f77e2bc5253439e4ccd6af25a6"
}
```
