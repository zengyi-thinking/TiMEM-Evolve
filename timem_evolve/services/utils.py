"""Common helpers for service layer."""
import os
from langchain_openai import ChatOpenAI

DEFAULT_ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_DEV_ZHIPU_KEY = "8f35caac9ab0a68779ecef4b1673b7fd.bGenP7A79YafJWye"


def create_chat_model(model_name: str, temperature: float = 0.0) -> ChatOpenAI:
    """Create a ChatOpenAI instance using available environment keys."""
    base_override = os.getenv("TIMEM_LLM_BASE_URL")
    zhipu_key = os.getenv("ZHIPUAI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if zhipu_key:
        base_url = base_override or os.getenv("ZHIPUAI_BASE_URL", DEFAULT_ZHIPU_BASE)
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=zhipu_key,
            base_url=base_url,
        )

    if openai_key:
        params = {
            "model": model_name,
            "temperature": temperature,
            "api_key": openai_key,
        }
        base_url = base_override or os.getenv("OPENAI_BASE_URL")
        if base_url:
            params["base_url"] = base_url
        return ChatOpenAI(**params)

    if os.getenv("TIMEM_USE_DEV_ZHIPU_KEY", "1") == "1":
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=DEFAULT_DEV_ZHIPU_KEY,
            base_url=DEFAULT_ZHIPU_BASE,
        )

    raise ValueError("Please set ZHIPUAI_API_KEY or OPENAI_API_KEY to use ChatOpenAI models.")
