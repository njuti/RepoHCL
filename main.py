import os.path
import shutil

import click

from metrics import EvaContext, CParser, FunctionMetric, ClazzMetric, ModuleMetric, RepoV2Metric, JSlangParser, \
    ModuleV2Metric
from utils.common import LangEnum


# def response_with_gitbook(doc_path: str):
#     def summary_sort(s: str):
#         # 模块摘要优先级最高
#         if 'modules.md' in s or 'cares.md' in s:
#             return 1, s.lower()
#         else:
#             # 如果字符串不符合任何条件，给予最低优先级
#             return 4, s.lower()
#
#     summary = '# Summary\n'
#     for root, _, files in os.walk(doc_path):
#         root = root[len(doc_path) + 1:]
#         if len(root) > 0:
#             summary += f'{(len(root.split(os.sep)) - 1) * "  "}* [{root}]\n'
#         for f in sorted(files, key=summary_sort):
#             if len(root) > 0:
#                 summary += f'{len(root.split(os.sep)) * "  "}* [{f[:-3]}]({os.path.join(root, f)}\n'
#             else:
#                 summary += f'* [{f[:-3]}]({f})\n'
#     with open(os.path.join(doc_path, 'SUMMARY.md'), 'w') as f:
#         f.write(summary)
#     with open(os.path.join(doc_path, 'README.md'), 'w') as f:
#         f.write(f'### {os.path.basename(doc_path)}\n')


@click.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--lang', default=LangEnum.cpp.cli,
              type=click.Choice([LangEnum.cpp.cli, LangEnum.javascript.cli], case_sensitive=False),
              help='编程语言')
def main(path, lang):
    path = click.format_filename(path).rstrip(os.sep)
    basename = os.path.basename(path)
    # 移动到工作路径
    shutil.copytree(path, os.path.join('resource', basename), dirs_exist_ok=True)
    # 初始化上下文
    ctx = EvaContext(doc_path=os.path.join('docs', basename), resource_path=os.path.join('resource', basename),
                     output_path=os.path.join('output', basename), lang=LangEnum.from_cli(lang))
    # 开始运行
    eva(ctx, LangEnum.from_cli(lang))
    # 生成gitbook输出
    # response_with_gitbook(os.path.join('docs', basename))
    # 清扫工作路径
    shutil.rmtree(os.path.join('resource', basename))
    shutil.rmtree(os.path.join('output', basename))


def eva(ctx: EvaContext, lang: LangEnum):
    # 生成函数列表、类列表、函数调用图、类调用图
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


if __name__ == '__main__':
    main()
