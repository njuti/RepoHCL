import os
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import field, dataclass
from enum import StrEnum
from typing import Any

from decouple import config
from loguru import logger
from transformers import AutoTokenizer, AutoModel


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ProjectSettings:
    log_level: LogLevel = field(default_factory=lambda: config('LOG_LEVEL', cast=LogLevel, default=LogLevel.INFO))
    threads: int = field(default_factory=lambda: config('THREADS', cast=int, default=os.cpu_count() * 4))


llm_thread_pool = ThreadPoolExecutor(ProjectSettings().threads)


@dataclass
class ChatCompletionSettings:
    # 环境变量写入密钥
    openai_api_key: str = field(default_factory=lambda: config('OPENAI_API_KEY'))
    # .env文件配置
    openai_base_url: str = field(default_factory=lambda: config('OPENAI_BASE_URL'))
    request_timeout: int = field(default_factory=lambda: config('MODEL_TIMEOUT', cast=int, default=30))
    model: str = field(default_factory=lambda: config('MODEL'))
    temperature: float = field(default_factory=lambda: config('MODEL_TEMPERATURE', cast=float, default=0))
    language: str = field(default_factory=lambda: config('MODEL_LANGUAGE', default='Chinese'))
    history_max: int = field(default_factory=lambda: config('HISTORY_MAX', cast=int, default=-1))


@dataclass
class RagSettings:
    tokenizer: Any = field(default_factory=lambda: config('TOKENIZER', default='Amu/tao-8k',
                                                          cast=lambda x: AutoTokenizer.from_pretrained(x)))
    model: Any = field(default_factory=lambda: config('TOKENIZER_MODEL', default='Amu/tao-8k',
                                                      cast=lambda x: AutoModel.from_pretrained(x)))
    dim: int = field(default_factory=lambda: config('TOKENIZER_DIM', cast=int, default=1024))


logger.add('logs/application.log', level=ProjectSettings().log_level, rotation='1 day', retention='7 days',
           encoding='utf-8')
logger.add('logs/llm.log', level=ProjectSettings().log_level, rotation='1 day', retention='3 days',
           encoding='utf-8', filter=lambda record: record['message'].startswith(('[SimpleLLM]', '[ToolsLLM]')))
