import json
import os
import re
import shutil
import subprocess
import sys
from typing import List, Dict

import networkx as nx
import pydot
from loguru import logger

from utils import gen_sh, remove_cycle
from .metric import Metric, FuncDef, FieldDef, EvaContext, ClazzDef


# 解析C/C++软件，获取函数调用图和类调用图
class ClangParser(Metric):

    @classmethod
    def _flush_file(cls, path: str, records: Dict) -> None:
        with open(path, 'w') as f:
            f.write(json.dumps(records, indent=4))

    @classmethod
    def _read_file(cls, path: str, resource_path: str) -> Dict:
        to_remove = []
        with open(path, 'r') as f:
            records = json.loads(f.read())
            for k, v in records.items():
                file: str = v.get('filename')
                file = file.replace('/', os.sep)
                # 不是绝对路径说明已经处理过了，跳过
                if not file.startswith(os.sep):
                    continue
                # 仅保留resource下的文件
                # resource_path = 'resource/libxml2/'
                i = file.find(resource_path)
                if i == -1:
                    to_remove.append(k)
                    continue
                v['filename'] = file[i + len(resource_path):].strip(os.sep)
            for k in to_remove:
                del records[k]
        if len(to_remove):
            cls._flush_file(path, records)
        return records

    # 去除类型中的修饰符
    @classmethod
    def _trim_type(cls, t: str) -> str:
        return re.sub(r'[*&]|(\[\d*])|const|volatile|restrict', '', t).strip()

    # 生成类重名列表，用于分析类与函数/类之间的关联
    @classmethod
    def _load_clazz_typedefs(cls, output_path: str, resource_path: str) -> Dict[str, str]:
        # xmlParserInputBufferPtr -> xmlParserInputBuffer * -> xmlParserInputBuffer
        clazz_typedefs_map = {}
        records = cls._read_file(os.path.join(output_path, 'typedefs.json'), resource_path)
        for k, v in records.items():
            source_type = v.get('sourceType')
            if source_type not in ('struct', 'other') or v.get('source').get('literal') == k:
                continue
            clazz_typedefs_map[k] = cls._trim_type(v.get('source').get('literal'))
        # xmlParserInputBufferPtrPtr -> xmlParserInputBufferPtr -> xmlParserInputBuffer
        simplified_map = {}
        for s, t in clazz_typedefs_map.items():
            while t in clazz_typedefs_map:
                t = clazz_typedefs_map[t]
            simplified_map[s] = t
        return simplified_map

    @classmethod
    def _load_functions(cls, output_path: str, resource_path: str) -> Dict[str, FuncDef]:
        function_map = {}
        records = cls._read_file(os.path.join(output_path, 'functions.json'), resource_path)
        for k, v in records.items():
            params = []
            for p in v.get('parameters'):
                params.append(FieldDef(name=p.get('name'), symbol=p.get('literal'), access=p.get('access')))
            with open(os.path.join(resource_path, v.get('filename')), 'r') as f:
                code = ''.join(f.readlines()[int(v.get('beginLine')) - 1: int(v.get('endLine'))])
            visible = bool(v.get('visible')) and str(v.get('declFilename')).endswith(('.h', '.hpp'))
            function_map[k] = FuncDef(symbol=k, params=params, filename=v.get('filename'), code=code,
                                      access=v.get('access'), visible=visible)

        return function_map

    @classmethod
    def _build_class_code(cls, symbol: str, fields: List[FieldDef], functions: List[FuncDef]) -> str:
        code = 'class ' + symbol + ' {\n'
        for access in ['public', 'protected', 'private']:
            filter_fields = list(filter(lambda x: x.access == access, fields))
            filter_functions = list(filter(lambda x: x.access == access, functions))
            if len(filter_fields) == 0 and len(filter_functions) == 0:
                return ''
            s = f'{access}:\n'
            for f in filter_fields:
                s += f'  {f.symbol} {f.name};\n'
            if len(filter_fields) > 0:
                s += '\n'
            for f in filter_functions:
                s += f'  {f.symbol};\n'
            code += s
        code += '};'
        return code

    # 加载类列表
    @classmethod
    def _load_clazz(cls, output_path: str, resource_path: str, callgraph: nx.DiGraph,
                    typedefs: Dict[str, str]) -> Dict[str, ClazzDef]:
        clazz_map: Dict[str, ClazzDef] = {}
        for source_file in ['structs.json', 'records.json']:
            records = cls._read_file(os.path.join(output_path, source_file), resource_path)
            for s, v in records.items():
                fields = list(map(lambda x: FieldDef(name=x.get('name'), symbol=x.get('literal'),
                                                     access=x.get('access')), v.get('fields')))
                # C++类，文件中关联了函数
                if 'functions' in v:
                    clazz_functions = list(map(lambda x: callgraph.nodes[x]['attr'],
                                               filter(lambda x: x in callgraph.nodes, v.get('functions'))))
                else:
                    # Struct,需要手动找到关联函数
                    clazz_functions = cls._find_related_functions(s, callgraph, typedefs)

                clazz_map[s] = ClazzDef(symbol=s, fields=fields, functions=clazz_functions,
                                        filename=v.get('filename'),
                                        code=cls._build_class_code(s, fields, clazz_functions))

        return clazz_map

    # 识别与struct关联的函数
    @classmethod
    def _find_related_functions(cls, clazz: str, callgraph: nx.DiGraph, typedefs: Dict[str, str]) -> List[
        FuncDef]:
        related = []
        # 通过callgraph遍历所有FuncDef
        for _, attrs in callgraph.nodes(data=True):
            v = attrs['attr']
            # 函数参数内包含类，则认为是相关函数
            # TODO，相关函数太多，应当对这些函数做一定的排序筛选
            for p in v.params:
                s = cls._trim_type(p.symbol)
                # 将参数类型去除修饰符后，找到typedefs中对应的类型，与clazz比较
                # clazz在声明时一定不会被typedef或修饰
                if typedefs.get(s, s) == clazz:
                    related.append(v)
        return related

    # 筛选部分函数，生成小规模的调用图
    # ctx.callgraph = self._load_sample_callgraph(ctx.output_path, function_map, ['xmlParseDoc', 'xmlParseFile'])
    @classmethod
    def _load_sample_callgraph(cls, output_path: str, functions: Dict[str, FuncDef], starts: List[str]) -> nx.DiGraph:
        callgraph = cls._load_callgraph(output_path, functions)
        # 函数名转FuncDef，找不到则报错
        q = list(map(lambda x: functions[x], starts))
        v = set()
        ng = nx.DiGraph()
        while len(q):
            s = q.pop(0)
            v.add(s)
            for t in list(filter(lambda x: x not in v, callgraph.successors(s))):
                q.append(t)
                ng.add_edge(s, t)
        logger.info(f'[ClangParser] sample callgraph: {len(callgraph.nodes)} -> {len(ng.nodes)}, starts: {starts}')
        return ng

    # 生成函数间调用图
    @classmethod
    def _load_callgraph(cls, output_path: str, functions: Dict[str, FuncDef]) -> nx.DiGraph:
        # 解析.dot转为DiGraph
        (dot,) = pydot.graph_from_dot_file(os.path.join(output_path, 'cg.dot'))
        callgraph = nx.DiGraph()
        # 记录.dot中节点ID和名称的映射关系
        id_map: Dict[str, str] = {}
        # 添加节点
        for node in dot.get_nodes():
            # 删除前后的“符号
            label = node.get('label').strip('"')
            # 仅同时在functions.json和cg.dot中存在的节点才添加到callgraph中
            if label in functions:
                # callgraph的节点是str函数名称,属性为FuncDef
                callgraph.add_node(label, attr=functions[label])
                id_map[node.get_name()] = label

        # 添加边
        for edge in dot.get_edges():
            # 排除自引用
            if edge.get_source() == edge.get_destination():
                continue
            # 边的起点和终点必须在functions.json中存在
            if edge.get_source() not in id_map or edge.get_destination() not in id_map:
                continue
            callgraph.add_edge(id_map[edge.get_source()], id_map[edge.get_destination()])
        return remove_cycle(callgraph)

    def eva(self, ctx: EvaContext):
        self._prepare(ctx.output_path, ctx.resource_path)
        logger.info(f'[ClangParser] prepared')
        clazz_typedefs_map = self._load_clazz_typedefs(ctx.output_path, ctx.resource_path)
        logger.info(f'[ClangParser] typedef size: {len(clazz_typedefs_map)}')
        function_map = self._load_functions(ctx.output_path, ctx.resource_path)
        ctx.callgraph = self._load_callgraph(ctx.output_path, function_map)
        logger.info(f'[ClangParser] callgraph size: {len(ctx.callgraph.nodes)}, {len(ctx.callgraph.edges)}')
        clazz_map = self._load_clazz(ctx.output_path, ctx.resource_path, ctx.callgraph, clazz_typedefs_map)
        ctx.clazz_callgraph = self._load_clazz_callgraph(clazz_map, clazz_typedefs_map)
        logger.info(
            f'[ClangParser] class callgraph size: {len(ctx.clazz_callgraph.nodes)}, {len(ctx.clazz_callgraph.edges)}')

    @classmethod
    def _load_clazz_callgraph(cls, clazz_map: Dict[str, ClazzDef], typedefs: Dict[str, str]):
        graph = nx.DiGraph()
        for s, clazz in clazz_map.items():
            graph.add_node(s, attr=clazz)
        for s, clazz in clazz_map.items():
            # 描述类间的组合关系
            # class A {
            #   B b;
            # }
            # A -> B
            for f in clazz.fields:
                t = cls._trim_type(f.symbol)
                t = typedefs.get(t, t)
                # 如果不在类的声明图中，说明该类型不是项目中定义的类。例如：int
                if t in graph:
                    graph.add_edge(s, t)
            # TODO，描述类间的继承关系
        return remove_cycle(graph)

    # 调用clang解析软件
    @staticmethod
    def _prepare(output_path: str, resource_path: str):
        # 已经生成过解析文件，直接返回
        if os.path.exists(output_path):
            return
        # TODO windows当前不支持，下列命令行及gen_sh在windows下无法执行
        if sys.platform.startswith("win"):
            raise Exception("Windows is not supported")

        def cmd(command: str, path: str = resource_path):
            subprocess.run(command.replace('/', os.sep), shell=True, cwd=path.replace('/', os.sep))
            logger.info('[ClangParser] command executed: ' + command)

        os.environ['CC'] = 'clang-9'
        os.environ['CXX'] = 'clang++-9'
        # 若有configure文件，执行./configure
        if os.path.exists(os.path.join(resource_path, 'configure')):
            cmd('./configure')
        elif os.path.exists(os.path.join(resource_path, 'Configure')):
            cmd('./Configure')
        if os.path.exists(os.path.join(resource_path, 'Makefile')):
            # 基于makefile生成compile_commands.json
            cmd('bear make -j`nproc`')
        elif os.path.exists(os.path.join(resource_path, 'CMakeLists.txt')):
            # 基于CMakeLists.txt生成compile_commands.json
            cmd('cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=1 .')
        else:
            raise Exception('No Makefile or CMakeLists.txt found')
        # 生成 build ast 命令
        gen_sh(resource_path)
        # 生成.ast
        cmd('chmod +x buildast.sh')
        cmd('./buildast.sh')
        # 在resource_path目录下解析ast
        shutil.copy(os.path.join('lib', 'cge'), resource_path)
        cmd(f'./cge astList.txt')
        # 将解析结果移动到output_path
        os.makedirs(output_path, exist_ok=True)
        shutil.move(os.path.join(resource_path, 'structs.json'), output_path)
        shutil.move(os.path.join(resource_path, 'typedefs.json'), output_path)
        shutil.move(os.path.join(resource_path, 'functions.json'), output_path)
        shutil.move(os.path.join(resource_path, 'records.json'), output_path)
        shutil.move(os.path.join(resource_path, 'cg.dot'), output_path)
