import os
from typing import List, override

from loguru import logger

from utils import SimpleLLM, prefix_with, ChatCompletionSettings, SimpleRAG, RagSettings, TaskDispatcher, Task
from utils.settings import llm_thread_pool
from . import RepoMetric
from .doc import RepoDoc, ApiDoc

qa_prompt = '''
You are an expert on software engineering. 
You have found a software that meets your requirements. But you still have some questions about the software.

The software you found is summarized as follows:

{repo_doc}

The software have the following functions maybe related to your questions:

{functions_doc}

Please answer the following questions based on the documentation of the software:

{question}

Please Note:
- When answering the question, you should first draw your conclusion in one sentence.
- The question should be answered in only one paragraph.
'''


# 为仓库生成文档V2，使用RAG验证文档的准确性
class RepoV2Metric(RepoMetric):
    def eva(self, ctx):
        try:
            draft = self._draft(ctx)
            questions = self._questions(ctx, draft)
            answers = self._answer(ctx, draft, questions)
            self._revise(ctx, draft, questions, answers)
        except AssertionError as e:
            logger.error(f'[RepoV2Metric] fail to gen doc for repo, err={e}')

    @classmethod
    @override
    def _answer(cls, ctx, doc: RepoDoc, questions: List[str]) -> List[str]:
        # 读取存在的回答
        if os.path.exists(cls.get_qa_answer_filename(ctx)):
            logger.info(f'[RepoMetric] load repo questions answer')
            with open(cls.get_qa_answer_filename(ctx), 'r') as f:
                answers = f.readlines()
                return list(map(lambda x: x.strip(), answers))
        # 回答每个问题
        rag = SimpleRAG(RagSettings())
        functions: List[ApiDoc] = list(map(lambda x: ctx.load_function_doc(x), ctx.callgraph.nodes))
        rag.add(list(map(lambda x: x.detail, functions)))
        # 回答每个问题，LLM结果直接写入答案数组的对应位置，避免顺序错乱
        answers = [''] * len(questions)

        def answer_qa(i: int, q: str):
            I = rag.query(q)
            functions_doc = [functions[i].markdown() for i in I]
            functions_doc = '\n\n---\n\n'.join(functions_doc)
            q_prompt = qa_prompt.format(repo_doc=prefix_with(doc.markdown(), '> '),
                                        functions_doc=prefix_with(functions_doc, '> '),
                                        question=q)
            answers[i] = SimpleLLM(ChatCompletionSettings()).add_user_msg(q_prompt).ask()
            logger.info(f'[RepoV2Metric] answer question {i + 1}')

        TaskDispatcher(llm_thread_pool).adds(
            list(map(lambda args: Task(f=answer_qa, args=args), enumerate(questions)))).run()
        # 保存仓库文档QA-Answer
        with open(cls.get_qa_answer_filename(ctx), 'w') as f:
            f.write('\n'.join(answers))
        return answers
