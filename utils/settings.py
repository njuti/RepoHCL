from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import field, dataclass
from enum import Enum
from typing import Any

from decouple import config
from transformers import AutoTokenizer, AutoModel
from loguru import logger

# 兼容python3.8
class StrEnum(str, Enum):
    def __new__(cls, *values):
        if len(values) > 1:
            member = str.__new__(cls, values[0])
        else:
            member = str.__new__(cls, values[0])
        return member

    def __str__(self):
        return self.value


# 使用 StrEnum 创建具体的枚举类

class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"



@dataclass
class ProjectSettings:
    log_level: LogLevel = field(default_factory=lambda: config('LOG_LEVEL', cast=LogLevel, default=LogLevel.INFO))

    def is_debug(self):
        return self.log_level == LogLevel.DEBUG

llm_thread_pool = ThreadPoolExecutor(1) if ProjectSettings().is_debug() else ThreadPoolExecutor(16)

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
    tokenizer: Any = field(default_factory=lambda: config('TOKENIZER', default='Amu/tao-8k', cast= lambda x: AutoTokenizer.from_pretrained(x)))
    model: Any = field(default_factory=lambda: config('TOKENIZER_MODEL', default='Amu/tao-8k', cast=lambda x: AutoModel.from_pretrained(x)))
    dim: int = field(default_factory=lambda: config('TOKENIZER_DIM', cast=int, default=1024))

logger.add('application.log', level=ProjectSettings().log_level, rotation='1 day', retention='7 days', encoding='utf-8')