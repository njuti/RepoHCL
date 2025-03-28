import time
import uuid
from enum import Enum
from typing import Optional, List, Dict

import requests
from fastapi import FastAPI, BackgroundTasks
from loguru import logger
from pydantic import BaseModel

from main import eva
from metrics import EvaContext, ApiDoc
from metrics.doc import RepoDoc
from utils import resolve_archive, prefix_with, SimpleLLM, ChatCompletionSettings

app = FastAPI()


class RATask(BaseModel):
    id: str  # ID
    repo: str  # 仓库OSS地址
    callback: str  # 回调URL


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
    archive.decompress(f'resource/{save_path}')
    return save_path


@app.post('/tools/hcl')
async def hcl(req: RATask, background_tasks: BackgroundTasks) -> RAResult:
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


def run_with_response(path: str, req: RATask):
    try:
        ctx = EvaContext(doc_path=f'docs/{path}', resource_path=f'resource/{path}', output_path=f'output/{path}')
        eva(ctx)
        data = EvaResult(functions=list(map(lambda x: ctx.load_function_doc(x).model_dump(), ctx.function_map.keys())),
                         classes=list(map(lambda x: ctx.load_clazz_doc(x).model_dump(), ctx.clazz_map.keys())),
                         modules=list(map(lambda x: x.model_dump(), ctx.load_module_docs())),
                         repo=[ctx.load_repo_doc().model_dump()])

        # 回调传结果，重试几次
        retry = 5
        while retry > 0:
            retry -= 1
            try:
                res = requests.post(req.callback,
                                    data=RAResult(id=req.id,
                                                  status=RAStatus.success.value,
                                                  message='ok',
                                                  result=data.model_dump_json()).model_dump_json(exclude_none=True,
                                                                                                 exclude_unset=True),
                                    headers={'Content-Type': 'application/json'})
                logger.info(f'callback send, status:{res.status_code}, message:{res.text}')
                break
            except Exception as e:
                logger.error(f'request fail, err={e}')
                time.sleep(1)
    except Exception as e:
        logger.error(f'fail to generate doc for {path}, err={e}')
        requests.post(req.callback,
                      data=RAResult(id=req.id, status=RAStatus.fail.value, message=str(e)).model_dump_json(
                          exclude_none=True, exclude_unset=True),
                      headers={'Content-Type': 'application/json'})
    # 清扫工作路径
    # shutil.rmtree(f'resource/{path}')
    # shutil.rmtree(f'output/{path}')
    # shutil.rmtree(f'docs/{path}')


# run_with_response('md5', RATask(id='8', callback='127.0.0.1:8000/tools/callback', repo='1'))

class CompReq(BaseModel):
    s1: str
    s2: str


class CompResult(BaseModel):
    result: str


class CompareMetric:
    _prompt = '''
You are an expert in software development.
Below are two software with similar functions. 

> ## Software 1
{s1}
> ---
> ## Software 2
{s2}

You can see the function documents of each software. 
Your task is to distinguish the similarities and differences between the functions of the two software and explain them with the help of a table.
The standard format is in the Markdown reference paragraph below, and you do not need to write the reference symbols `>` when you output:

> | FEATURE POINTS | Software 1 | Software 2 |
> | ---- | ---- | ---- |
> | point1 | How Software 1 perform on point1 | How Software 2 perform on point1 |
> | point2 | **How Software 1 perform on point2** | How Software 2 perform on point2 |
> | point3 | How Software 1 perform on point3 | X  |
> | point4 | X | How Software 2 perform on point4 |
> | ... | ... | ... |
>
> Summary
> - Software 1 is better because ...
> - Software 2 should be used in XXX scenarios because ...

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
            s = RepoDoc.model_validate(r).markdown() + '\n'
        for f in ctx.functions:
            f_doc = ApiDoc.model_validate(f)
            f_doc.parameters = None
            f_doc.example = None
            f_doc.detail = None
            s += f_doc.markdown() + '\n'
        return prefix_with(s, '> ')

    def eva(self, ctx1: EvaResult, ctx2: EvaResult) -> str:
        s1 = self._sprompt(ctx1)
        s2 = self._sprompt(ctx2)
        p = self._prompt.format(s1=s1, s2=s2)
        llm = SimpleLLM(ChatCompletionSettings())
        res = llm.add_user_msg(p).ask()
        return res


@app.get('/tools/comp')
def comp(req: CompReq) -> CompResult:
    s1 = EvaResult.model_validate_json(req.s1)
    s2 = EvaResult.model_validate_json(req.s2)
    res = CompareMetric().eva(s1, s2)
    return CompResult(result=res)
