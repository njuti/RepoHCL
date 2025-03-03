from typing import List

import networkx as nx
from loguru import logger

from .metric import Metric, FieldDef, FuncDef, Symbol
from .doc import ApiDoc
from utils import SimpleLLM, ChatCompletionSettings, prefix_with

documentation_guideline = (
    "Keep in mind that your audience is document readers, so use a deterministic tone to generate precise content and don't let them know "
    "you're provided with code snippet and documents. AVOID ANY SPECULATION and inaccurate descriptions! Now, provide the documentation "
    "for the target object in a professional way."
)


class FunctionMetric(Metric):
    def eva(self, ctx):
        functions = ctx.function_map
        callgraph = ctx.callgraph
        # 逆拓扑排序callgraph
        sorted_functions = list(reversed(list(nx.topological_sort(callgraph))))
        logger.info(f'[FunctionMetric] gen doc for functions, functions count: {len(sorted_functions)}')
        # 生成文档
        for i in range(len(sorted_functions)):
            symbol = Symbol(base=sorted_functions[i])
            if ctx.load_function_doc(symbol):
                logger.info(f'[FunctionMetric] load {symbol.base}: {i + 1}/{len(sorted_functions)}')
                continue
            f: FuncDef = functions.get(symbol)
            referencer = list(
                filter(lambda s: s is not None,
                       map(lambda s: ctx.load_function_doc(Symbol(base=s)), callgraph.successors(symbol.base)))
            )
            referenced = list(
                filter(lambda s: s is not None,
                       map(lambda s: ctx.load_function_doc(Symbol(base=s)), callgraph.predecessors(symbol.base)))
            )
            prompt = FunctionPromptBuilder().structure(ctx.structure).parameters(f.params).code(f.code).referencer(
                referencer).referenced(referenced).file_path(f.filename).name(symbol.base).build()
            res = SimpleLLM(ChatCompletionSettings()).add_system_msg(prompt).add_user_msg(documentation_guideline).ask()
            res = f'### {symbol.base}\n' + res
            doc = ApiDoc.from_chapter(res)
            ctx.save_function_doc(symbol, doc)
            logger.info(f'[FunctionMetric] parse {symbol.base}: {i + 1}/{len(sorted_functions)}')


doc_generation_instruction = (
    "You are an AI documentation assistant, and your task is to generate documentation based on the given code of an object. "
    "The purpose of the documentation is to help developers and beginners understand the function and specific usage of the code.\n\n"
    "Currently, you are in a project and the related hierarchical structure of this project is as follows\n"
    "{project_structure}\n\n"
    "The path of the document you need to generate in this project is {file_path}.\n"
    'Now you need to generate a document for a Method, whose name is `{code_name}`.\n\n'
    "The code of the Method is as follows:\n\n"
    "```C++\n"
    "{code}\n"
    "```\n\n"
    "{reference_letter}\n"
    "{referencer_content}\n\n"
    "Please generate a detailed explanation document for this Method based on the code of the target Method itself and combine it with its calling situation in the project.\n\n"
    "Please write out the function of this Method briefly followed by a detailed analysis (including all details) to serve as the documentation for this part of the code.\n\n"
    "The standard format is in the Markdown reference paragraph below, and you do not need to write the reference symbols `>` when you output:\n\n"
    "> #### Description\n"
    "> Briefly describe the Method in one sentence.\n"
    "{parameters_note}"
    "> #### Code Details\n"
    "> Detailed and CERTAIN code analysis of the Method. {has_relationship}\n"
    "> #### Example\n"
    "> ```C++\n"
    "> Mock possible usage examples of the Method with codes. {example}\n"
    "> ```\n\n"
    "Please note:\n"
    "- The Level 4 headings in the format like `#### xxx` are fixed, don't change or translate them.\n"
    "- Don't add new Level 3 or Level 4 headings. Do not write anything outside the format\n")


class FunctionPromptBuilder:
    _prompt: str = doc_generation_instruction

    _tag_referenced = False
    _tag_referencer = False

    def structure(self, structure: str):
        self._prompt = self._prompt.replace('{project_structure}', structure)
        return self

    def name(self, name: str):
        self._prompt = self._prompt.replace('{code_name}', name)
        return self

    def file_path(self, file_path: str):
        self._prompt = self._prompt.replace('{file_path}', file_path)
        return self

    def referenced(self, referenced: List[ApiDoc]):
        if len(referenced) == 0:
            self._prompt = self._prompt.replace('{reference_letter}', '')
            return self
        prompt = 'As you can see, the code calls the following methods, their docs and code are as following:\n\n'
        for reference_item in referenced:
            prompt += f'**Method**: `{reference_item.name}`\n\n' + '**Document**:\n\n' + '\n'.join(
                list(map(lambda t: '> ' + t, reference_item.markdown()))) + '\n---\n'
        self._prompt = self._prompt.replace('{reference_letter}', prompt)
        self._tag_referenced = True
        return self

    def referencer(self, referencer: List[ApiDoc]):
        if len(referencer) == 0:
            self._prompt = self._prompt.replace('{referencer_content}', '')
            return self
        prompt = 'Also, the code has been called by the following methods, their code and docs are as following:\n'
        for referencer_item in referencer:
            prompt += f'**Method**: `{referencer_item.name}`\n\n' + '**Document**:\n\n' + '\n'.join(
                list(map(lambda t: '> ' + t, referencer_item.markdown().split('\n')))) + '\n---\n'
        self._prompt = self._prompt.replace('{referencer_content}', prompt)
        self._tag_referencer = True
        return self

    def build(self) -> str:
        if self._tag_referenced or self._tag_referencer:
            self._prompt = self._prompt.replace('{has_relationship}',
                                                'And please include the reference relationship with its callers or callees in the project from a functional perspective')
        else:
            self._prompt = self._prompt.replace('{has_relationship}', '')
            self._prompt = self._prompt.replace('{example}', '')
        if self._tag_referencer:
            self._prompt = self._prompt.replace('{example}', 'You can refer to the use of this Function in the caller.')
        return self._prompt

    def parameters(self, params: List[FieldDef]):
        if len(params):
            self._prompt = self._prompt.replace('{parameters_note}', prefix_with(
                '#### Parameters\n'
                '- Parameter1: XXX\n'
                '- Parameter2: XXX\n'
                '- ...\n', '> '))
        else:
            self._prompt = self._prompt.replace('{parameters_note}', '')
        return self

    def code(self, code: str):
        self._prompt = self._prompt.replace('{code}', code)
        return self
