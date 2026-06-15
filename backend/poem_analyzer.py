"""
诗词PK - 诗词解析模块
负责赛后诗词的全面赏析，支持调用智谱 GLM-4-Flash 生成高质量解析
"""

import json
import random
from typing import Optional

from config import ZHIPU_API_KEY, ZHIPU_BASE_URL, ZHIPU_MODEL


class PoemAnalyzer:
    """赛后诗词解析"""

    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 兼容客户端（智谱 GLM）"""
        try:
            from openai import AsyncOpenAI
            if ZHIPU_API_KEY and ZHIPU_API_KEY != "你的API_KEY填在这里":
                self._client = AsyncOpenAI(
                    api_key=ZHIPU_API_KEY,
                    base_url=ZHIPU_BASE_URL,
                )
                print(f"[LLM] 智谱 GLM 异步客户端已初始化 (模型: {ZHIPU_MODEL})")
            else:
                print("[LLM] 未配置 API Key，将使用预置解析")
        except ImportError:
            print("[LLM] 未安装 openai 库，将使用预置解析。请执行: pip install openai")

    @staticmethod
    def select_wrong_poems(wrong_poem_ids: list[int], count: int = 2) -> list[int]:
        """
        从答错记录中随机选取指定数量的诗词ID（去重后）

        Args:
            wrong_poem_ids: 所有答错的诗词ID列表（可能包含重复）
            count: 需要选取的数量

        Returns:
            选取的诗词ID列表
        """
        unique_ids = list(set(wrong_poem_ids))
        if len(unique_ids) <= count:
            return unique_ids
        return random.sample(unique_ids, count)

    @staticmethod
    def generate_analysis(poem: dict) -> dict:
        """
        基于题库预置数据生成解析（不依赖 LLM）

        Args:
            poem: 诗词字典

        Returns:
            结构化的解析内容
        """
        analysis = poem.get("analysis", {})

        result = {
            "id": poem.get("id"),
            "title": poem.get("title", "未知"),
            "author": poem.get("author", "未知"),
            "dynasty": poem.get("dynasty", "未知"),
            "content": poem.get("content", ""),
            "tags": poem.get("tags", []),
            "background": analysis.get("background", "暂无创作背景资料。"),
            "translation": analysis.get("translation", ""),
            "appreciation": analysis.get("appreciation", "暂无逐句赏析资料。"),
            "technique": analysis.get("technique", "暂无艺术手法分析。"),
            "famous_lines": analysis.get("famous_lines", ""),
            "theme": analysis.get("theme", ""),
        }

        if not result["translation"]:
            content = poem.get("content", "")
            if content:
                result["translation"] = f"全诗「{content}」语言精练，意蕴深远。"
            else:
                result["translation"] = "暂无译文。"

        if not result["famous_lines"] and poem.get("lines"):
            lines = poem["lines"]
            first_pair = lines[0]
            result["famous_lines"] = (
                f"「{first_pair['upper']}，{first_pair['lower']}」"
                f"是全诗最为传诵的佳句。"
            )

        if not result["theme"] and poem.get("tags"):
            tags_str = "、".join(poem["tags"])
            result["theme"] = f"本诗属于{tags_str}类作品，表达了诗人深挚的情感与独特的艺术追求。"

        return result

    async def generate_analysis_llm(self, poem: dict) -> dict:
        """
        调用智谱 GLM-4-Flash 生成高质量诗词解析

        如果 LLM 不可用（未配置 API Key 或调用失败），回退到预置解析。

        Args:
            poem: 诗词字典

        Returns:
            结构化的解析内容
        """
        title = poem.get("title", "?")
        print(f"[LLM] generate_analysis_llm 被调用: 《{title}》, 客户端={'已就绪' if self._client else '未初始化'}")

        # 基础信息（始终从题库获取）
        base = {
            "id": poem.get("id"),
            "title": poem.get("title", "未知"),
            "author": poem.get("author", "未知"),
            "dynasty": poem.get("dynasty", "未知"),
            "content": poem.get("content", ""),
            "tags": poem.get("tags", []),
        }

        # 如果 LLM 客户端未初始化，回退到预置解析
        if not self._client:
            print(f"[LLM] 客户端不可用，回退到预置解析: 《{title}》")
            fallback = self.generate_analysis(poem)
            fallback["llm_generated"] = False
            return fallback

        try:
            # 构建 prompt
            prompt = self._build_prompt(poem)
            print(f"[LLM] 正在调用智谱 GLM-4-Flash: 《{title}》...")

            # 调用智谱 GLM-4-Flash（OpenAI 兼容异步接口）
            response = await self._client.chat.completions.create(
                model=ZHIPU_MODEL,
                messages=[
                    {"role": "system", "content": "你是一位精通中国古典诗词的文学教授，擅长对古诗词进行全面深入的赏析。请严格按照要求的 JSON 格式输出。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )

            content = response.choices[0].message.content.strip()
            print(f"[LLM] 智谱返回成功: 《{title}》, 响应长度={len(content)}")

            # 解析 LLM 返回的 JSON
            llm_result = self._parse_llm_response(content)
            llm_result.update(base)
            llm_result["llm_generated"] = True
            print(f"[LLM] 解析完成: 《{title}》")
            return llm_result

        except Exception as e:
            print(f"[LLM] 调用失败: 《{title}》, 错误={type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            fallback = self.generate_analysis(poem)
            fallback["llm_generated"] = False
            return fallback

    @staticmethod
    def _build_prompt(poem: dict) -> str:
        """构建 LLM 的 prompt"""
        title = poem.get("title", "")
        author = poem.get("author", "")
        dynasty = poem.get("dynasty", "")
        content = poem.get("content", "")

        return f"""请对以下中国古典诗词进行全面解析，以 JSON 格式返回结果。

诗词信息：
- 标题：{title}
- 作者：{author}
- 朝代：{dynasty}
- 全文：{content}

请严格按以下 JSON 格式输出（不要包含 markdown 代码块标记，直接输出 JSON）：
{{
    "background": "创作背景（100-150字，说明写作时间、地点、缘由）",
    "translation": "白话译文（完整翻译全诗，语言流畅自然）",
    "appreciation": "逐句赏析（200-300字，分析每一句的意境和妙处）",
    "technique": "艺术手法（100-150字，分析修辞、对仗、意象等手法）",
    "famous_lines": "名句点评（指出最著名的句子，分析其精妙之处）",
    "theme": "主题思想（50-100字，概括诗歌的核心主题和思想感情）"
}}"""

    @staticmethod
    def _parse_llm_response(content: str) -> dict:
        """解析 LLM 返回的 JSON 内容"""
        # 尝试去除可能的 markdown 代码块标记
        content = content.strip()
        if content.startswith("```"):
            # 去除开头的 ```json 或 ```
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 部分
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
            else:
                raise ValueError("无法解析 LLM 返回的内容为 JSON")

        # 确保所有必要字段存在
        required_fields = ["background", "translation", "appreciation", "technique", "famous_lines", "theme"]
        for field in required_fields:
            if field not in result or not result[field]:
                result[field] = "暂无数据"

        return result
