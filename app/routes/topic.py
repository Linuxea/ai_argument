"""Topic refinement route: AI-powered topic clarification."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI, AuthenticationError, NotFoundError

from app.config import settings
from app.models import RefineTopicRequest

router = APIRouter(tags=["topic"])

_REFINE_PROMPT_TEMPLATE = """请将以下辩论话题优化为更清晰、更有辩论价值的表述。

原始话题: {topic}

要求:
1. 保持原始话题的核心立场和意图
2. 使表述更加明确、具体
3. 确保话题具有可辩性（存在不同观点）
4. 直接输出优化后的话题，不要添加任何解释或前缀

优化后的话题:"""


@router.post("/api/topic/refine")
async def refine_topic(request: RefineTopicRequest):
    """Use AI to refine and clarify a debate topic."""
    if not settings.api_key:
        raise HTTPException(status_code=400, detail="请先在设置中配置 API Key")

    if not request.topic or not request.topic.strip():
        raise HTTPException(status_code=400, detail="话题不能为空")

    prompt = _REFINE_PROMPT_TEMPLATE.format(topic=request.topic)

    try:
        client = AsyncOpenAI(base_url=settings.api_base_url, api_key=settings.api_key)
        response = await client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )
        choice = response.choices[0] if response.choices else None
        content = (choice.message.content if choice and choice.message else None) or ""
        refined_topic = content.strip()
        if not refined_topic:
            # Model returned empty content (content filter, tool-only response,
            # or reasoning model that didn't emit text). Don't crash with a
            # misleading 502 — tell the user plainly.
            raise HTTPException(
                status_code=502,
                detail="模型未返回话题文本，请稍后重试或换个表述",
            )
        return {"refined_topic": refined_topic}
    except HTTPException:
        raise
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="API Key 无效")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="模型不存在或 API URL 不正确")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"话题优化失败: {e}")
