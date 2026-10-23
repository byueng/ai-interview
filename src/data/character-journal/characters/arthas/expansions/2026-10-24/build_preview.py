"""Assemble the two reviewed journal supplements into a local reading preview."""
from pathlib import Path
import html
import json
import re

ROOT = Path(__file__).resolve().parent
UNITS = ('stratholme', 'icecrown-duel')


def markdown(text):
    blocks = []
    for block in re.split(r'\n\s*\n', text.strip()):
        value = html.escape(block.strip())
        heading = re.match(r'^(#{1,6})\s+(.+)$', value)
        if heading:
            level = min(len(heading[1]) + 1, 6)
            blocks.append(f'<h{level}>{heading[2]}</h{level}>')
        else:
            value = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)
            blocks.append('<p>' + value.replace('\n', '<br>') + '</p>')
    return '\n'.join(blocks)


sections = []
nav = []
for uid in UNITS:
    folder = ROOT / 'units' / uid
    profile = json.loads((folder / 'profile.json').read_text(encoding='utf-8-sig'))
    title = html.escape(profile['title'])
    nav.append(f'<a href="#{uid}">{title}</a>')
    image = folder / 'images' / 'cover-v002.png'
    if not image.is_file():
        raise FileNotFoundError(image)
    content = markdown((folder / 'story.md').read_text(encoding='utf-8-sig'))
    caption_path = folder / 'caption.txt'
    caption = html.escape(caption_path.read_text(encoding='utf-8').strip()) if caption_path.exists() else title
    sections.append(f'<article id="{uid}"><figure><img src="units/{uid}/images/cover-v002.png" alt="{caption}"><figcaption>{caption}</figcaption></figure><div class="prose">{content}</div></article>')

page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>阿尔萨斯 · 两个转折</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#101a23;color:#e4e0d7;font-family:"Microsoft YaHei",sans-serif;line-height:1.95}header{max-width:1100px;margin:auto;padding:64px 24px 32px}header small{color:#b69c6c;letter-spacing:.18em}h1{font-family:serif;font-size:clamp(30px,5vw,54px);font-weight:500;margin:12px 0}header p,figcaption{color:#abaeb0}nav{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}a{color:#dec794;text-decoration:none;border-bottom:1px solid #695b43}nav a{padding:8px 18px;border:1px solid #695b43;border-radius:3px}article{max-width:1100px;margin:0 auto 70px;background:#15212c;border:1px solid #34404a;scroll-margin-top:20px}figure{margin:0}img{display:block;width:100%;height:auto}figcaption{font-size:13px;padding:14px 24px;border-bottom:1px solid #34404a}.prose{max-width:820px;margin:auto;padding:24px 36px 44px}.prose h2{font-family:serif;font-size:30px;font-weight:500;color:#ead9b5}.prose h3{font-size:21px;margin-top:36px;color:#d7bc8d}.prose p{font-size:16px;margin:20px 0}footer{max-width:1000px;margin:0 auto;padding:0 24px 40px;color:#939ca4;font-size:13px}@media(max-width:600px){header{padding-top:32px}.prose{padding:18px 22px 30px}article{border-left:0;border-right:0}.prose h2{font-size:26px}}
</style><header><small>阿尔萨斯人物志 · 专题增补</small><h1>两个转折</h1><p>斯坦索姆的绝望，与通往冰封王座的最后一战。</p><nav>'''
page += ''.join(nav) + '</nav></header>' + ''.join(sections)
page += '<footer>基于用户提供的《迈向冰封王座：阿尔萨斯》原文创作。副标题为编辑拟题；插画为彩绘玻璃艺术诠释。此为独立内容预览。</footer></html>'
(ROOT / 'preview.html').write_text(page, encoding='utf-8')
print(ROOT / 'preview.html')
