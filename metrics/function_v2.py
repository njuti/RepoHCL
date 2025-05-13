import os.path
from typing import List

import networkx as nx
from loguru import logger

from utils import SimpleLLM, ChatCompletionSettings, prefix_with, TaskDispatcher, ProjectSettings
from .doc import ApiDoc
from .metric import Metric, FieldDef, FuncDef

documentation_guideline = (
    "Keep in mind that your audience is document readers, so use a deterministic tone to generate precise content and don't let them know "
    "you're provided with code snippet and documents. AVOID ANY SPECULATION and inaccurate descriptions! Now, provide the documentation "
    "for the target object in a professional way."
)


# 为函数生成文档V2
# 1. 使用调用关系生成函数文档
# 2. 使用被调用关系修正函数文档
# 实践中发现，修正效果一般，有待改进
class FunctionV2Metric(Metric):

    @classmethod
    def get_v2_draft_filename(cls, ctx, file: str) -> str:
        return os.path.join(f'{ctx.doc_path}', f'{file}.{ApiDoc.doc_type()}.v2_draft.md')

    def eva(self, ctx):
        self._draft(ctx)
        self._revise(ctx)

    @classmethod
    def _draft(cls, ctx):
        callgraph = ctx.callgraph
        # 逆拓扑排序callgraph
        logger.info(f'[FunctionV2Metric] gen doc for functions, functions count: {len(callgraph)}')

        # 生成文档
        def gen(signature: str):
            f: FuncDef = ctx.func(signature)
            if ctx.load_doc(signature, cls.get_v2_draft_filename(ctx, f.filename), ApiDoc):
                logger.info(f'[FunctionV2Metric] load {signature}')
                return
            referenced = list(
                filter(lambda s: s is not None,
                       map(lambda s: ctx.load_function_doc(s), callgraph.successors(signature)))
            )
            prompt = _FunctionPromptBuilder().parameters(f.params).code(f.code).referenced(
                referenced).lang(ctx.lang.markdown).name(signature).build()
            res = SimpleLLM(ChatCompletionSettings()).add_system_msg(prompt).add_user_msg(documentation_guideline).ask()
            res = f'### {signature}\n' + res
            doc = ApiDoc.from_chapter(res)
            doc.code = f'```{ctx.lang.markdown}\n{f.code}\n```'
            ctx.save_doc(cls.get_v2_draft_filename(ctx, f.filename), doc)
            logger.info(f'[FunctionV2Metric] parse {signature}')

        TaskDispatcher(ProjectSettings.llm_thread_pool).map(callgraph, gen).run()

    @classmethod
    def _revise(cls, ctx):
        callgraph = ctx.callgraph
        logger.info(f'[FunctionV2Metric] revise doc for functions, functions count: {len(callgraph)}')

        # 生成文档
        def gen(signature: str):
            if ctx.load_function_doc(signature):
                logger.info(f'[FunctionV2Metric] load revised {signature}')
                return
            f: FuncDef = ctx.func(signature)
            referencer: List[ApiDoc] = list(
                filter(lambda s: s is not None,
                       map(lambda s: ctx.load_function_doc(s), callgraph.predecessors(signature)))
            )[:5]
            draft_doc = ctx.load_doc(signature, cls.get_v2_draft_filename(ctx, f.filename), ApiDoc)
            if len(referencer) == 0:
                ctx.save_function_doc(signature, draft_doc)
                return
            # TODO，简化
            referencer_docs = ''.join(
                map(lambda r: f'**Function**: `{r.name}`\n\n**Document**:\n\n{prefix_with(r.markdown(), "> ")}\n---\n',
                    referencer))
            parameter_docs = prefix_with(
                '#### Parameters\n'
                '- Parameter1: XXX\n'
                '- Parameter2: XXX\n'
                '- ...', '> ' if len(f.params) else '\n').strip()
            prompt = doc_revised_prompt.format(
                referencer=referencer_docs,
                lang=ctx.lang.markdown,
                parameters=parameter_docs,
                function_doc=prefix_with(draft_doc.markdown(), '> '))
            res = SimpleLLM(ChatCompletionSettings()).add_system_msg(prompt).add_user_msg(documentation_guideline).ask(
                lambda x: x[x.find('#### Description'):]  # 去除标题
            )
            res = f'### {signature}\n' + res
            doc: ApiDoc = ApiDoc.from_chapter(res)
            doc.code = f'```{ctx.lang.markdown}\n{f.code}\n```'
            ctx.save_function_doc(signature, doc)
            logger.info(f'[FunctionV2Metric] revise {signature}')

        TaskDispatcher(ProjectSettings.llm_thread_pool).map(nx.reverse(callgraph), gen).run()


# Currently, you are in a project and the related hierarchical structure of this project is as follows:
# {project_structure}
# The path of the document you need to generate in this project is {file_path}.
doc_generation_instruction = '''
You are an AI documentation assistant, and your task is to generate documentation based on the given code of an object.
The purpose of the documentation is to help developers and beginners understand the function and specific usage of the code.
Now you need to generate a document for a Function, whose name is `{code_name}`.

The code of the Function is as follows:
```{lang}
{code}
```

{referenced}

Please generate a detailed explanation document for this Function based on the code of the target Function itself and combine it with its calling situation in the project.
Please write out the function of this Function briefly followed by a detailed analysis (including all details) to serve as the documentation for this part of the code.
The standard format is in the Markdown reference paragraph below, and you do not need to write the reference symbols `>` when you output:

> #### Description
> Briefly describe the Function in one sentence.
> #### Parameters
> - Parameter1
> #### Code Details
> Detailed and CERTAIN code analysis of the Function. {details_supplement}
> #### Example
> ```{lang}
> Mock possible usage examples of the Function with codes. 
> ```

Please note:
- The Level 4 headings in the format like `#### xxx` are fixed, don't change or translate them.
- Don't add new Level 3 or Level 4 headings. Do not write anything outside the format.
'''

doc_revised_prompt = '''
You are an AI documentation assistant tasked with revising and enhancing the documentation for a given Function based on its usage examples. 
Your goal is to ensure that the documentation accurately reflects the Function's functionality without any speculation or inaccuracies.

The following Function documentation is what you need to revise:
{function_doc}

As you can see, the Function is called by the following Functions, their docs and code are as following. Please revise the above documentation by incorporating insights from them:
{referencer}

The previous documentation is written by a robot, and it may not be accurate or detailed enough. You should give it a major revision.
There are some points you need to pay attention to:
1. Ensure that the Description is concise and accurate.
2. Ensure that the Function is called correctly in Example.

The improved README should keep the same format as before. To ensure the same format, you should follow the standard format in the Markdown reference paragraph below. You do not need to write the reference signatures `>` when you output:

> #### Description
> Briefly describe the Function in one sentence.
{parameters}
> #### Code Details
> Detailed and CERTAIN code analysis of the Function. 
> #### Example
> ```{lang}
> Mock possible usage examples of the Function with codes. 
> ```

Please note:
- The improved documentation should keep the same format as before. That is, you should keep the headings in the documentation and only revise the content under each heading. 
- The Level 4 headings in the format like `#### xxx` are fixed, don't change or translate them.
- Don't add new Level 3 or Level 4 headings. Do not write anything outside the format.
- You do not need to write the reference symbols `>` when you output.
'''


class _FunctionPromptBuilder:
    _prompt: str = doc_generation_instruction

    def name(self, name: str):
        self._prompt = self._prompt.replace('{code_name}', name)
        return self

    # def structure(self, structure: str):
    #     self._prompt = self._prompt.replace('{project_structure}', structure)
    #     return self
    #
    # def file_path(self, file_path: str):
    #     self._prompt = self._prompt.replace('{file_path}', file_path)
    #     return self

    def lang(self, lang: str):
        self._prompt = self._prompt.replace('{lang}', lang)
        return self

    def referenced(self, referenced: List[ApiDoc]):
        if len(referenced) == 0:
            self._prompt = self._prompt.replace('{referenced}', '').replace('{details_supplement}', '')
            return self
        prompt = 'As you can see, the code calls the following Functions, their docs and code are as following:\n\n'
        for reference_item in referenced:
            reference_item.code = None
            prompt += f'**Function**: `{reference_item.name}`\n\n' + '**Document**:\n\n' + prefix_with(
                reference_item.markdown(), '> ') + '\n---\n'
        self._prompt = self._prompt.replace('{referenced}', prompt).replace('{details_supplement}',
                                                                            'You should refer to the documentation of the called Functions to analyze the code details.')
        return self

    def build(self) -> str:
        return self._prompt

    def parameters(self, params: List[FieldDef]):
        if len(params):
            self._prompt = self._prompt.replace('{parameters}', prefix_with(
                '#### Parameters\n'
                '- Parameter1: XXX\n'
                '- Parameter2: XXX\n'
                '- ...', '> ').strip())
        else:
            self._prompt = self._prompt.replace('{parameters}', '>\n')
        return self

    def code(self, code: str):
        self._prompt = self._prompt.replace('{code}', code)
        return self
