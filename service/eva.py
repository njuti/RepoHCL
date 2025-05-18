import json
import os
import uuid

import requests
from loguru import logger

from metrics import EvaContext, CParser, FunctionMetric, ClazzMetric, ModuleMetric, RepoV2Metric, JSlangParser, \
    ModuleV2Metric
from utils import LangEnum, post, resolve_archive
from .vo import EvaResult, RAResult, RAStatus, RATask


def eva(ctx: EvaContext, lang: LangEnum):
    # 预处理，生成函数调用图、类调用图
    if lang == LangEnum.cpp:
        CParser().eva(ctx)
    elif lang == LangEnum.javascript:
        JSlangParser().eva(ctx)
    else:
        raise NotImplementedError(f'{lang} not supported')
    # 生成软件目录结构，TODO：暂时不用了
    # StructureMetric().eva(ctx)
    # 生成函数文档
    FunctionMetric().eva(ctx)
    # 生成类文档
    ClazzMetric().eva(ctx)
    # 生成模块文档，若API数量过多，则使用V2版本
    if len(ctx.api_iter()) > 1500:
        ModuleV2Metric().eva(ctx)
    else:
        ModuleMetric().eva(ctx)
    # 生成仓库文档
    RepoV2Metric().eva(ctx)


def eva_with_response(req: RATask):
    try:
        path = download_archive(req.repo)
        lang = LangEnum.from_render(req.language)
        ctx = EvaContext(repo=req.name, lang=lang, doc_path=os.path.join('docs', path),
                         resource_path=os.path.join('resource', path),
                         output_path=os.path.join('output', path))
        eva(ctx, lang)
        repo_doc = ctx.load_repo_doc()
        repo_doc = [repo_doc.model_dump()] if repo_doc is not None else []
        data = EvaResult(functions=list(map(lambda x: ctx.load_function_doc(x.signature).model_dump(),
                                            filter(lambda x: x.visible, ctx.func_iter()))),
                         classes=list(map(lambda x: ctx.load_clazz_doc(x.signature).model_dump(),
                                          filter(lambda x: x.visible, ctx.clazz_iter()))),
                         modules=list(map(lambda x: x.model_dump(), ctx.load_module_docs())),
                         repo=repo_doc)

        # 回调传结果，重试几次
        post(req.callback,
             content=RAResult(id=req.id,
                              status=RAStatus.success.value,
                              message='ok',
                              result=data.model_dump_json())
             .model_dump_json(exclude_none=True, exclude_unset=True))
    except Exception as e:
        logger.error(f'fail to generate doc for {req.repo}, err={e}')
        # 回调传错误
        data = json.dumps({'repo': {'description': str(e)}})
        post(req.callback,
             content=RAResult(id=req.id, status=RAStatus.fail.value, message=str(e),
                              result=data).model_dump_json(
                 exclude_none=True, exclude_unset=True))


# 下载仓库
def download_archive(repo: str) -> str:
    save_path = uuid.uuid4().hex
    response = requests.get(repo)
    if response.status_code == 403:
        raise Exception(response.text)
    logger.info(f'fetch repo {response.status_code} {len(response.content)}')
    archive = resolve_archive(response.content)
    archive.decompress(os.path.join('resource', save_path))
    return save_path
