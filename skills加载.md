### 方案一：本地加载：扫描 skills 文件夹，md 元数据 + py 代码 → LangChain Tool
- 实现逻辑：
    遍历skills/*子文件夹
    读取每个 skill 的skill.md解析 tool name /description/parameters
    动态导入文件夹内main.py，拿到run()执行函数
    基于 md 元信息 + run 函数，构建 LangChain StructuredTool
    得到 tool 列表，可以直接喂给 React Agent；也可以再把这批 tool 暴露成 MCP 服务
- skills/skill_registry.py
``` python
import os
import importlib.util
from pathlib import Path
import yaml
from langchain_core.tools import StructuredTool

SKILLS_ROOT = Path(__file__).parent

def load_one_skill(skill_folder:Path) -> StructuredTool:
    # 1. 读取 skill.md，yaml front‑matter元数据
    md_path = skill_folder / "skill.md"
    md_content = md_path.read_text(encoding="utf‑8")
    # 简单解析markdown头部yaml元块（实际可用python‑markdown / frontmatter库）
    import frontmatter
    fm = frontmatter.loads(md_content)

    skill_name = fm["name"]
    skill_desc = fm["description"]
    params_spec = fm["parameters"]

    # 2. 动态导入 main.py 的 run 函数
    main_py = skill_folder / "main.py"
    spec = importlib.util.spec_from_file_location(f"skill.{skill_folder.name}", str(main_py))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    skill_func = mod.run

    # 3. 封装成LangChain结构化Tool
    tool = StructuredTool.from_function(
        func=skill_func,
        name=skill_name,
        description=skill_desc
    )
    return tool

def load_all_skills() -> list[StructuredTool]:
    """扫描skills目录，加载全部文件夹skill，返回LangChain工具列表"""
    tools = []
    for entry in os.scandir(SKILLS_ROOT):
        if entry.is_dir():
            skill_dir = Path(entry.path)
            if (skill_dir/"skill.md").exists() and (skill_dir/"main.py").exists():
                t = load_one_skill(skill_dir)
                tools.append(t)
    return tools

if __name__ == "__main__":
    all_tools = load_all_skills()
    for t in all_tools:
        print(f"loaded skill: {t.name} | {t.description}")
```