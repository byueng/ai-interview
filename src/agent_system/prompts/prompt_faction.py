"""读取并填充提示词模板，可选择将结果保存为新文件。"""

from pathlib import Path


def render_prompt(
    template_path: str | Path,
    *args: object,
    output_path: str | Path | None = None,
    **kwargs: object,
) -> str:
    """填充模板并返回文本，不修改原始模板。

    Args:
        template_path: 模板的绝对路径，或相对于本模块所在目录的路径。
        *args: 按顺序替换模板中的 {}，也支持 {0} 等编号占位符。
        output_path: 可选的新文件路径；相对路径以当前工作目录为基准。
            父目录必须已经存在，目标文件不能存在。
        **kwargs: 替换 {position} 等命名占位符。

    模板中的普通花括号需要写成 {{ 和 }}。传入的值只替换一次，
    不会再次作为模板解析。output_path 是控制参数，不能作为占位符参数。

    推荐使用命名绑定：关键字参数名必须与模板中的占位符名称一致，
    与参数传入顺序无关。例如：

        render_prompt(
            "init_interview_prompt.md",
            role_identity="技术面试官",
            role_responsibilities="介绍面试流程，生成开场白",
            language="Python",
            position="后端工程师",
            education="本科",
            resume="有 Python 项目开发经验",
        )

    Raises:
        FileNotFoundError: 模板或输出父目录不存在。
        KeyError: 缺少命名占位符对应的值。
        IndexError: 缺少位置占位符对应的值。
        ValueError: 模板格式不正确，或输出路径指向原始模板。
        FileExistsError: 输出文件已经存在。
    """
    source = Path(template_path)
    if not source.is_absolute():
        source = Path(__file__).resolve().parent / source
    source = source.resolve()

    template = source.read_text(encoding="utf-8")
    # kwargs 按名称绑定：例如 position="后端工程师" 替换 {position}。
    rendered = template.format(*args, **kwargs)

    if output_path is not None:
        destination = Path(output_path).resolve()
        if destination == source:
            raise ValueError("输出路径不能与原始提示词模板相同。")
        # 独占创建：已有文件不覆盖，也避免并发调用静默覆盖彼此的结果。
        with destination.open("x", encoding="utf-8") as output:
            output.write(rendered)

    return rendered
