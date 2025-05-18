from collections import defaultdict
from typing import Dict, List

from loguru import logger

from utils import SimpleLLM, ChatCompletionSettings, TaskDispatcher, Task, ProjectSettings
from .module import ModuleMetric
from .doc import ModuleDoc
from .metric import EvaContext, ClazzDef

file_understand_prompt = '''
You are a senior software engineer.
Your task is to read a code file and summarize the functions of the symbols in the file.
The file you want to read is named {filename}.

The following is a description of all the APIs in this file:
{api_docs}

The following is a description of all the classes in this file:
{clazz_docs}

Now, please summarize the functions of the symbols in the file and write them in the following format.
You shouldn't write the reference symbols `>` when you output.

> #### Description
> A concise paragraph summarizing the file's purpose, how it contributes to solving specific problems.
> #### Functions
> - API1
> - API2

You'd better consider the following workflow:
1. Identify Core Functionality. Start by reading through all APIs and classes descriptions to get a broad understanding of the available functionalities and think about the core tasks or operations that these symbol enable. 
2. Select Key APIs. Based on the core functionalities, identify the key APIs that are most relevant to the module's purpose. These should be the APIs that are most frequently used or have the most significant impact on the module's functionality.

Please Note:
- #### Functions is a list of API signatures included in this file. Please use the complete API signature with the return type and parameters, like {api_example}, not the abbreviation.
- The Level 4 headings in the format like `#### Description` are fixed, don't change or translate them. Don't add new Level 3 or Level 4 headings. Do not write anything outside the format.
'''


# 为模块生成文档V4，
# 以文件为单位，总结文件中的API和类。
class ModuleV4Metric(ModuleMetric):

    def eva(self, ctx: EvaContext):
        try:
            drafts = self._draft_v4(ctx)
            # 由大模型增强模块文档
            self._enhance(ctx, drafts)
        except AssertionError as e:
            logger.error(f'[ModuleV2Metric] fail to gen doc for module, err: {e}')
            raise e

    @classmethod
    def _draft_v4(cls, ctx: EvaContext) -> List[ModuleDoc]:
        api_per_file: Dict[str, List[str]] = defaultdict(list)
        for api in ctx.api_iter():
            api_per_file[ctx.func(api).filename].append(api)
        clazz_per_file: Dict[str, List[ClazzDef]] = defaultdict(list)
        for clazz in ctx.clazz_iter():
            clazz_per_file[ctx.clazz(clazz.signature).filename].append(clazz)
        filenames = set(api_per_file.keys())
        logger.info(f'[ModuleV3Metric] gen drafts for modules, files count: {len(filenames)}')
        existed_modules = set(map(lambda x: x.name, ctx.load_module_docs()))

        # 生成文档
        def gen(filename: str):
            if filename in existed_modules:
                logger.info(f'[ModuleV3Metric] load {filename}')
                return
            api_docs = ''.join(
                map(lambda api: f'- {api}\n > {ctx.load_function_doc(api).description}\n\n',
                    api_per_file[filename]))
            clazz_docs = ''.join(
                map(lambda clazz: f'- {clazz.signature}\n > {ctx.load_clazz_doc(clazz.signature).description}\n\n',
                    clazz_per_file.get(filename, [])))

            prompt = file_understand_prompt.format(
                filename=filename,
                api_docs=api_docs,
                clazz_docs=clazz_docs,
                api_example=api_per_file[filename][0]
            )
            res = SimpleLLM(ChatCompletionSettings()).add_user_msg(prompt).ask()
            res = f'### {filename}\n' + res
            doc = ModuleDoc.from_chapter(res)
            ctx.save_doc(cls.get_draft_filename(ctx), doc)
            logger.info(f'[ModuleV2Metric] gen draft for module {doc.name}')

        TaskDispatcher(ProjectSettings.llm_thread_pool).adds(
            list(map(lambda args: Task(f=gen, args=(args,)), filenames))).run()
        return ctx.load_docs(cls.get_draft_filename(ctx), ModuleDoc)
