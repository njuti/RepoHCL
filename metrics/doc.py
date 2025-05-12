from __future__ import annotations

import re
from abc import abstractmethod, ABC
from typing import List, Optional, override, TypeVar

from pydantic import BaseModel, field_serializer

# T 表示Doc的子类，在Python中仅用于类型提示
T = TypeVar('T', bound='Doc')
# 文档对象基类，描述了怎么从md文件中解析出文档对象，如何将文档对象转化为md文件
class Doc(ABC, BaseModel):
    name: str  # 符号名称
    description: str  # 符号描述

    # 读取字符串，返回其中的所有文档对象
    @classmethod
    def from_doc(cls, s: str) -> List[T]:
        function_pattern = re.compile(r'(###.*?)(?=\n### |\Z)', re.DOTALL)
        res: List[Doc] = []
        for match in function_pattern.finditer(s):
            res.append(cls.from_chapter(match.group(1)))
        return res

    # 读取字符串，返回其中的一个文档对象
    @classmethod
    def from_chapter(cls, s: str) -> T:
        module_pattern = re.search(r'### (.*?)\n(.*?)(?=\n### |\Z)', s, re.DOTALL)
        name = module_pattern.group(1).strip()
        block = module_pattern.group(2)
        return cls.from_chapter_hook(cls(name=name, description=cls.from_block(block, 'Description')), block)

    # 读取字符串，为文档对象附加属性
    @classmethod
    @abstractmethod
    def from_chapter_hook(cls, doc, block: str):
        pass

    # 读取字符串block，返回 header（#### 四级标题）下的内容
    @classmethod
    def from_block(cls, block: str, header: str) -> Optional[str]:
        match = re.search(f'#### {header}' + r'(.*?)(?=####|\Z)', block, re.DOTALL)
        content = match.group(1).strip() if match else None
        return content

    # 将文档对象转化为markdown格式的字符串
    def markdown(self) -> str:
        md = f'### {self.name}\n#### Description\n{self.description}\n\n'
        return md + self._markdown_hook()

    # 使用文档对象的属性，为markdown附加内容
    @abstractmethod
    def _markdown_hook(self) -> str:
        pass

    # 文档对象类型
    @classmethod
    @abstractmethod
    def doc_type(cls) -> str:
        pass


# 函数文档
class ApiDoc(Doc):
    detail: Optional[str] = None  # 函数的详细描述
    example: Optional[str] = None  # 函数的使用示例
    parameters: Optional[str] = None  # 函数的参数列表
    code: Optional[str] = None  # 函数的源代码

    @classmethod
    @override
    def from_chapter_hook(cls, doc: ApiDoc, block: str) -> ApiDoc:
        doc.detail = cls.from_block(block, 'Code Details')
        doc.example = cls.from_block(block, 'Example')
        doc.parameters = cls.from_block(block, 'Parameters')
        doc.code = cls.from_block(block, 'Source Code')
        return doc

    @override
    def _markdown_hook(self) -> str:
        md = ''
        if self.parameters is not None:
            md += f'#### Parameters\n{self.parameters}\n\n'
        if self.detail is not None:
            md += '#### Code Details\n{details}\n\n'.format(details=self.detail)
        if self.example is not None:
            md += f'#### Example\n{self.example}\n\n'
        if self.code is not None:
            md += f'#### Source Code\n{self.code}\n\n'
        return md.strip()

    @classmethod
    @override
    def doc_type(cls) -> str:
        return 'function'


# 类文档
class ClazzDoc(Doc):
    detail: Optional[str] = None  # 类的详细描述
    attributes: Optional[str] = None  # 类的属性列表

    @classmethod
    @override
    def from_chapter_hook(cls, doc: ClazzDoc, block: str) -> ClazzDoc:
        doc.detail = cls.from_block(block, 'Code Details')
        doc.attributes = cls.from_block(block, 'Attributes')
        return doc

    @override
    def _markdown_hook(self) -> str:
        md = ''
        if self.attributes is not None:
            md += f'#### Attributes\n{self.attributes}\n\n'
        md += '#### Code Details\n{details}\n\n'.format(details=self.detail)
        return md.strip()

    @classmethod
    @override
    def doc_type(cls) -> str:
        return 'class'


# 模块文档
class ModuleDoc(Doc):
    example: Optional[str] = None  # 模块的使用示例
    functions: List[str] = None  # 模块的函数列表

    # 将字符串列表格式的函数列表在JSON序列化时，转为markdown格式的字符串
    @field_serializer('functions')
    def functions_serializer(self, v: List[str], _info) -> str:
        return '\n'.join(map(lambda x: f'- {x}', v))

    @classmethod
    @override
    def from_chapter_hook(cls, doc: ModuleDoc, block: str) -> ModuleDoc:
        function_doc = cls.from_block(block, 'Functions')
        doc.functions = list(filter(lambda x: len(x), map(lambda x: x.strip('- `\''), function_doc.splitlines())))
        doc.example = cls.from_block(block, 'Use Case')
        return doc

    @override
    def _markdown_hook(self) -> str:
        md = ''
        if self.functions:
            md += '#### Functions\n{}\n\n'.format('\n'.join(map(lambda x: f'- {x}', self.functions)))
        if self.example:
            md += f'#### Use Case\n{self.example}\n\n'
        return md.strip()

    @classmethod
    @override
    def doc_type(cls) -> str:
        return 'module'


# 仓库文档
class RepoDoc(Doc):
    features: List[str] = None  # 仓库的功能列表
    standards: List[str] = None  # 仓库的协议列表
    scenarios: List[str] = None  # 仓库的场景列表

    # 将字符串列表格式的功能列表在JSON序列化时，转为markdown格式的字符串
    @field_serializer('features', 'standards', 'scenarios')
    def features_serializer(self, v: List[str], _info) -> str:
        return '\n'.join(map(lambda x: f'- {x}', v))

    @classmethod
    @override
    def from_chapter_hook(cls, doc: RepoDoc, block: str) -> RepoDoc:
        features_doc = cls.from_block(block, 'Features')
        doc.features = list(filter(lambda x: len(x), map(lambda x: x.strip('- '), features_doc.splitlines())))
        standards_doc = cls.from_block(block, 'Standards')
        doc.standards = list(filter(lambda x: len(x), map(lambda x: x.strip('- '), standards_doc.splitlines())))
        scenarios_doc = cls.from_block(block, 'Scenarios')
        if scenarios_doc:
            doc.scenarios = list(filter(lambda x: len(x), map(lambda x: x.strip('- '), scenarios_doc.splitlines())))
        return doc

    @override
    def _markdown_hook(self) -> str:
        md = '#### Features\n{}\n\n'.format('\n'.join(map(lambda x: f'- {x}', self.features)))
        md += '#### Standards\n{}\n\n'.format('\n'.join(map(lambda x: f'- {x}', self.standards)))
        if self.scenarios:
            md += '#### Scenarios\n{}\n\n'.format('\n'.join(map(lambda x: f'- {x}', self.scenarios)))
        return md.strip()

    @classmethod
    @override
    def doc_type(cls) -> str:
        return 'repo'
