import os.path
import time
import uuid
from dataclasses import field
from enum import Enum
from typing import Optional, List, Dict

import requests
from fastapi import FastAPI, BackgroundTasks
from loguru import logger
from pydantic import BaseModel

from main import eva
from metrics import EvaContext, ModuleDoc, RepoDoc
from utils import resolve_archive, prefix_with, SimpleLLM, ChatCompletionSettings, LangEnum

app = FastAPI()


class RATask(BaseModel):
    id: str  # ID
    repo: str  # 仓库OSS地址
    callback: str  # 回调URL
    language: str = LangEnum.cpp.render  # 语言
    name: str = ''


class RAStatus(Enum):
    received = 0
    success = 1
    fail = 2


class RAResult(BaseModel):
    id: str
    status: int
    message: str = ''
    score: Optional[int] = None
    result: Optional[str] = None


class EvaResult(BaseModel):
    functions: List[Dict]
    classes: List[Dict]
    modules: List[Dict]
    repo: List[Dict]


def fetch_repo(repo: str) -> str:
    save_path = uuid.uuid4().hex
    response = requests.get(repo)
    if response.status_code == 403:
        raise Exception(response.text)
    logger.info(f'fetch repo {response.status_code} {len(response.content)}')
    archive = resolve_archive(response.content)
    archive.decompress(os.path.join('resource', save_path))
    return save_path


@app.post('/tools/hcl')
async def hcl(req: RATask, background_tasks: BackgroundTasks) -> RAResult:
    logger.info(f'hcl, req={req}')
    try:
        path = fetch_repo(req.repo)
        # path = 'md5'
        logger.info(f'fetch repo {req.repo} to {path}')
    except Exception as e:
        logger.error(f'fail to get `{req.repo}`, err={e}')
        return RAResult(id=req.id, status=RAStatus.fail.value, message=str(e))
    background_tasks.add_task(run_with_response, path=path, req=req)
    return RAResult(id=req.id, status=RAStatus.received.value, message='task received')


@app.post('/tools/callback')
def test(req: RAResult):
    logger.info(req.model_dump_json())
    return 'ok'


@app.get('/tools/test')
def test2():
    print('hello')
    return 'hello'


def requests_with_retry(url: str, content: str, retry: int = 5):
    err = None
    while retry > 0:
        retry -= 1
        try:
            res = requests.post(url,
                                data=content,
                                headers={'Content-Type': 'application/json'})
            logger.info(f'requests send, status:{res.status_code}, message:{res.text}')
            return
        except Exception as e:
            err = e
            logger.error(f'request fail, err={e}')
            time.sleep(1)
    raise Exception(f'Request Failed, err={err}')


def run_with_response(path: str, req: RATask):
    try:
        lang = LangEnum.from_render(req.language)
        ctx = EvaContext(doc_path=os.path.join('docs', path), resource_path=os.path.join('resource', path),
                         output_path=os.path.join('output', path), lang=lang)
        eva(ctx, lang)
        data = EvaResult(functions=list(map(lambda x: ctx.load_function_doc(x.signature).model_dump(),
                                            filter(lambda x: x.visible, ctx.func_iter()))),
                         classes=list(map(lambda x: ctx.load_clazz_doc(x.signature).model_dump(),
                                          filter(lambda x: x.visible, ctx.clazz_iter()))),
                         modules=list(map(lambda x: x.model_dump(), ctx.load_module_docs())),
                         repo=[ctx.load_repo_doc().model_dump()])

        # 回调传结果，重试几次
        requests_with_retry(req.callback,
                            content=RAResult(id=req.id,
                                             status=RAStatus.success.value,
                                             message='ok',
                                             result=data.model_dump_json())
                            .model_dump_json(exclude_none=True, exclude_unset=True))
    except Exception as e:
        logger.error(f'fail to generate doc for {path}, err={e}')
        requests_with_retry(req.callback,
                            content=RAResult(id=req.id, status=RAStatus.fail.value, message=str(e)).model_dump_json(
                                exclude_none=True, exclude_unset=True))
    # 清扫工作路径
    # shutil.rmtree(f'resource/{path}')
    # shutil.rmtree(f'output/{path}')
    # shutil.rmtree(f'docs/{path}')


# run_with_response('md5', RATask(id='8', callback='127.0.0.1:8000/tools/callback', repo='1'))

class CompReq(BaseModel):
    results: List[str]
    requestId: str
    callback: str
    names: List[str] = field(default_factory=lambda: ['software1', 'software2'])


class CompResult(BaseModel):
    requestId: str
    status: int
    message: str
    result: Optional[str] = None


class CompareMetric:
    _prompt = '''
You are an expert in software development.
Below are multiple software with similar functions. 
They may have different solutions to the same problem, for example, zip and tar are different methods for decompression.
They may be old and latest versions of the same software and therefore differ in capabilities.

Your task is to distinguish the similarities and differences between the functions of the software and tell me which should be used in which scenarios.

{software}

Please compare the two software and write a comparison report with the help of a table
The standard format is in the Markdown reference paragraph below, and you do not need to write the reference symbols `>` when you output:

> | FEATURE POINTS | Software 1 | Software 2 | ... |
> | ---- | ---- | ---- | ... |
> | point1 | How Software 1 perform on point1 | How Software 2 perform on point1 | ... |
> | point2 | **How Software 1 perform on point2** | How Software 2 perform on point2 | ... |
> | point3 | How Software 1 perform on point3 | X  | ... |
> | point4 | X | How Software 2 perform on point4 | ... |
> | ... | ... | ... | ... |
>
> Summary
> - Software 1 is better because ...
> - Software 2 should be used in XXX scenarios because ...
> ...

You'd better consider the following workflow:
1. Understand the Software. Read through the documents of each software to understand their core functionalities.
2. Summarize the Feature Points. Identify the key feature points of each software from the modules documentation.
3. Find the same Feature Points. Compare the performance of the same Feature Points in the two software. 
4. Find the different Feature Points. Identify the Feature Points that only one software has.
5. Write a Summary. Summarize the comparison and give your suggestions.

Please Note:
- For a feature point, if one software performs better, use **bold** to highlight its performance.
- For a feature point, if one of the software doesn't show the feature point, output X.
- Give a summary of the comparison behind the table showing which software is better and why. 
- Don’t mention all the functions the software have, summarize the most important ones.
'''

    @staticmethod
    def _sprompt(ctx: EvaResult):
        s = ''
        if len(ctx.repo):
            r = ctx.repo[0]
            r['features'] = list(map(lambda x: x.strip('- '), r['features'].splitlines()))
            r['standards'] = list(map(lambda x: x.strip('- '), r['standards'].splitlines()))
            r['scenarios'] = list(map(lambda x: x.strip('- '), r['scenarios'].splitlines()))
            s = RepoDoc.model_validate(r).markdown() + '\n'
        for m in ctx.modules:
            m['functions'] = list(map(lambda x: x.strip('- '), m['functions'].splitlines()))
            m = ModuleDoc.model_validate(m)
            m.example = None
            m.functions = []
            s += m.markdown() + '\n'
        return s

    def eva(self, results: List[EvaResult]) -> str:
        s = ''
        for i, r in enumerate(results):
            s += f'## Software {i + 1}\n'
            s += self._sprompt(r)
            s += '---'
        p = self._prompt.format(software=prefix_with(s, '> '))
        llm = SimpleLLM(ChatCompletionSettings())
        res = llm.add_user_msg(p).ask()
        with open('compare.md', 'w') as f:
            f.write(res)
        return res


@app.post('/tools/comp')
async def comp(req: CompReq, background_tasks: BackgroundTasks) -> CompResult:
    background_tasks.add_task(do_comp, req=req)
    return CompResult(requestId=req.requestId, status=RAStatus.received.value, message='task received')


def do_comp(req: CompReq):
    try:
        res = CompareMetric().eva(list(map(lambda x: EvaResult.model_validate_json(x), req.results)))
        requests_with_retry(url=req.callback, content=CompResult(requestId=req.requestId, result=res, message='ok',
                                                                 status=RAStatus.success.value).model_dump_json())
    except Exception as e:
        logger.error(f'fail to compare doc for {req.requestId}, err={e}')
        requests_with_retry(req.callback, content=CompResult(requestId=req.requestId, result=None, message=str(e),
                                                             status=RAStatus.fail.value).model_dump_json())
