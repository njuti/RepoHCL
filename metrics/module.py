from functools import reduce
from typing import List

from loguru import logger

from utils import SimpleLLM, prefix_with, ChatCompletionSettings
from utils.settings import ProjectSettings
from .doc import ModuleDoc
from .metric import Metric, Symbol

modules_summarize_prompt = '''
You are an expert in software architecture analysis. 
Your task is to review function descriptions from a C++ code repository and organize them into multiple functional modules based on their purpose and interrelations. 
You need to output a structured summary for each identified functional module.

The standard format is in the Markdown reference paragraph below, and you shouldn't write the reference symbols `>` when you output:

> ### Module Name
> #### Description
> A concise paragraph summarizing the module's purpose, how it contributes to solving specific problems, and which functions work together within the module.
> #### Functions
> - Function1
> - Function2

You'd better consider the following workflow:
1. Identify Core Functionality. Start by reading through all function descriptions to get a broad understanding of the available functionalities and think about the core tasks or operations that these functions enable.
2. Define Functional Modules. Based on the core functionalities, define initial functional modules that encapsulate related tasks or operations. Use your expertise to determine logical groupings of functions that contribute to similar outcomes or processes.
3. Analyze Function Interdependencies. Examine how functions interact with one another. Consider whether they are called in sequence, share data, or serve complementary purposes. Recognize that a single function can be part of multiple modules if it serves different roles or contexts.
4. Refine Module Definitions. Review and adjust the boundaries of the modules as needed to ensure they accurately reflect the relationships between functions. Ensure that each module's summary clearly articulates its unique value and contribution to the overall system.
5. Generate Documentation. Write a summary for each module using the provided format you finally decide and put them together. Don't include any other content in the output. 

Please Note:
- #### Functions is a list of function names included in this module. Please use the full function name with the return type and parameters, not the abbreviation.
- Try to put every function into at least one module unless the function is really useless.
- The Level 4 headings in the format like `#### xxx` are fixed, don't change or translate them. Don't add new Level 3 or Level 4 headings. Do not write anything outside the format

Now a list of function descriptions are provided as follows, you can start working.
{api_docs}
'''

modules_enhance_prompt = '''
You are an expert in software architecture analysis. 
Your task is to read the module documentation of a C++ project and improve it.
There are two key points for improvement:
1. This module contains some functions, but these functions may not be appropriate, and you need to remove these functions.
2. Design a usage scenario for this module. You need to mock a use case that combines as many functions as possible from the module to solve a specific problem in this scenario. The use case should be realistic and demonstrate the functionality of the module.'

The improved README should keep the same format as before. To ensure the same format, you should follow the standard format in the Markdown reference paragraph below. You do not need to write the reference symbols `>` when you output:

> ### Module Name
> #### Description
> A concise paragraph summarizing the module's purpose, how it contributes to solving specific problems, and which functions work together within the module.
> #### Functions
> - Function1
> - Function2
> #### Use Case
> ```C++
> Mock possible usage examples of the Module with codes.
> ```

You'd better consider the following workflow:
1. Understand the Module. Read through the function descriptions and the module summary to gain a comprehensive understanding of the module's purpose and functionality. Identify the key functions that contribute to the module's core operations and remove any irrelevant functions.
2. Define the Use Case. Based on the functions available in the module, define a specific problem or scenario that the module can address. Consider how multiple functions can work together to achieve a desired outcome or solve a particular issue.
3. Rewrite the Module Summary. Update the module summary to reflect the refined list of functions and the use case you have designed. 

Please Note:
- If all functions are related to the module tightly, you don't need to remove any functions.
- #### Functions is a list of function names included in this module. Please use the full function name with the return type and parameters, not the abbreviation.
- You can revise the content in #### Description if it's not consistent with the answers to the questions.
- The Level 4 headings in the format like `#### xxx` are fixed, don't change or translate them. 
- Don't write new Level 3 or Level 4 headings. Don't write anything outside the format. 
- Do not output descriptions of improvements.


Here is the documentation of the module you need to enhance:

{module_doc}

Here is the documentation of the functions referenced in the module:

{functions_doc}
'''


class ModuleMetric(Metric):
    def eva(self, ctx):
        existed_modules_doc = ctx.load_module_docs()
        if existed_modules_doc:
            logger.info(f'[FunctionMetric] load modules, modules count: {len(existed_modules_doc)}')
            return
        # 提取所有用户可见的函数
        apis: List[Symbol] = list(filter(lambda x: ctx.function_map.get(x).visible
                                                   and ctx.function_map.get(x).declFile.endswith('.h'), ctx.function_map.keys()))
        logger.info(f'[ModuleMetric] gen doc for modules, apis count: {len(apis)}')
        # 使用函数描述组织上下文
        api_docs = reduce(lambda x, y: x + y,
                          map(lambda a: f'- {a.base}\n > {ctx.load_function_doc(a).description}\n\n', apis))
        prompt = modules_summarize_prompt.format(api_docs=api_docs)
        # 生成模块文档
        res = SimpleLLM(ChatCompletionSettings()).add_user_msg(prompt).ask()
        modules = ModuleDoc.from_doc(res)
        # 保存模块文档初稿
        if ProjectSettings().is_debug():
            with open(f'{ctx.doc_path}/modules-0.md', 'w') as f:
                for m in modules:
                    f.write(m.markdown() + '\n')
        logger.info(f'[ModuleMetric] gen doc for modules, modules count: {len(modules)}')
        # 优化模块文档
        for i in range(len(modules)):
            m = modules[i]
            # 使用完整函数文档组织上下文
            functions_doc = []
            for f in m.functions:
                functions_doc.append(ctx.load_function_doc(Symbol(base=f)).markdown())
            functions_doc = prefix_with('\n---\n'.join(functions_doc), '> ')
            # 使用原模块文档组织上下文
            module_doc = prefix_with(m.markdown(), '> ')
            prompt2 = modules_enhance_prompt.format(module_doc=module_doc, functions_doc=functions_doc)
            # 生成模块文档
            res = SimpleLLM(ChatCompletionSettings()).add_user_msg(prompt2).ask()
            doc = ModuleDoc.from_chapter(res)
            # 保存模块文档
            ctx.save_module_doc(doc)
            logger.info(f'[ModuleMetric] gen doc for module {i + 1}/{len(modules)}: {m.name}')
