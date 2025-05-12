import json
import os
import shutil
import subprocess
import tempfile

import networkx as nx
import pydot

from .metric import Metric, FuncDef, FieldDef, EvaContext, ClazzDef


# @Author: 段庸
class JSlangParser(Metric):

    @classmethod
    def _generate_func_paras_json(cls, output_path):
        path = os.path.join(output_path, 'func_paras.json')
        script_content = f'''
        loadCpg("{output_path}/cpg.bin")
        val result = cpg.method.map(m => (m.fullName, m.parameter.map(_.name).l)).distinct.l

        import java.io.PrintWriter
        import upickle.default._

        val jsonResult = write(result, indent = 2)
        new PrintWriter("{path}") {{ write(jsonResult); close() }}
        '''
        # 在临时目录中创建 .sc 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sc', delete=False) as tmpfile:
            tmpfile.write(script_content)
            tmpfile_path = tmpfile.name  # 保存路径供后面调用

        os.makedirs(output_path, exist_ok=True)
        # 调用 Joern 执行该脚本
        try:
            subprocess.run(['joern', '--script', tmpfile_path, f'{output_path}/cpg.bin'], check=True)
        finally:
            os.remove(tmpfile_path)  # 执行完删除临时文件

    @classmethod
    def _generate_class_fields_json(cls, output_path):
        path = os.path.join(output_path, 'class_fields.json')
        script_content = f'''
        loadCpg("{output_path}/cpg.bin")

        import java.io.PrintWriter
        import upickle.default._

        case class FieldInfo(fieldName: String, fieldType: String)
        case class ClassInfo(className: String, fields: List[FieldInfo])

        implicit val fieldInfoRW: ReadWriter[FieldInfo] = macroRW
        implicit val classInfoRW: ReadWriter[ClassInfo] = macroRW

        val result = cpg.typeDecl.map {{ t =>
        val className = t.fullName
        val fields = t.member.l.map {{ f =>
            FieldInfo(f.name, f.typeFullName)
        }}.toList
        ClassInfo(className, fields)
        }}.toList

        val json = write(result, indent = 2)

        new PrintWriter("{path}") {{ write(json); close() }}
        '''
        # 在临时目录中创建 .sc 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sc', delete=False) as tmpfile:
            tmpfile.write(script_content)
            tmpfile_path = tmpfile.name  # 保存路径供后面调用
        os.makedirs(output_path, exist_ok=True)
        # 调用 Joern 执行该脚本
        try:
            subprocess.run(['joern', '--script', tmpfile_path, f'{output_path}/cpg.bin'], check=True)
        finally:
            os.remove(tmpfile_path)  # 执行完删除临时文件

    @classmethod
    def _load_funtions(cls, func_nodes, output_path):
        functions = []

        cls._generate_func_paras_json(output_path)
        json_path = os.path.join(output_path, 'func_paras.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        func_para_map = {item[0]: list(item[1]) for item in data}

        for node in func_nodes:
            attrs = node.get_attributes()
            raw_paras = func_para_map[attrs.get("FULL_NAME", "").strip('"')]
            params = []
            for para in raw_paras:
                params.append(FieldDef(para, 'ANY'))
            new_func = FuncDef(
                signature=attrs.get("NAME", "").strip('"'),
                code=attrs.get("CODE", "").strip('"'),
                filename=attrs.get("FILENAME", '""').strip('"'),
                visible=True,
                access='public',
                params=params,
                name=attrs.get("NAME", "").strip('"'),
            )
            functions.append(new_func)
        return functions

    @classmethod
    def _add_edges(cls, func_nodes, graph, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for caller, callee in data:
            if any(node.get_attributes().get("FULL_NAME").strip('"') == caller for node in func_nodes) and any(
                    node.get_attributes().get("FULL_NAME").strip('"') == callee for node in func_nodes):
                # print(1)
                caller_name = next(
                    (
                        node.get_attributes().get("NAME").strip('"')
                        for node in func_nodes
                        if node.get_attributes().get("FULL_NAME").strip('"') == caller
                    ),
                    None
                )
                callee_name = next(
                    (
                        node.get_attributes().get("NAME").strip('"')
                        for node in func_nodes
                        if node.get_attributes().get("FULL_NAME").strip('"') == callee
                    ),
                    None
                )
                graph.add_edge(caller_name, callee_name)

        return graph

    @classmethod
    def _generate_callgraph_json(cls, output_path):
        path = os.path.join(output_path, 'callgraph.json')
        script_content = f'''
        loadCpg("{output_path}/cpg.bin")
        val result = cpg.call.map {{ c =>
        val caller = c.method.fullName
        val callee = c.callee.fullName.l.headOption.getOrElse("")
        (caller, callee)
        }}.l

        import java.io.PrintWriter
        import upickle.default._

        val jsonResult = write(result, indent = 2)
        new PrintWriter("{path}") {{ write(jsonResult); close() }}
        '''
        # 在临时目录中创建 .sc 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sc', delete=False) as tmpfile:
            tmpfile.write(script_content)
            tmpfile_path = tmpfile.name  # 保存路径供后面调用
        os.makedirs(output_path, exist_ok=True)
        # 调用 Joern 执行该脚本
        try:
            subprocess.run(['joern', '--script', tmpfile_path, f'{output_path}/cpg.bin'], check=True)
        finally:
            os.remove(tmpfile_path)  # 执行完删除临时文件

    @classmethod
    def _load_callgraph(cls, func_nodes, functions, output_path):
        graph = nx.DiGraph()
        for func in functions:
            graph.add_node(func.signature, attr=func)

        cls._generate_callgraph_json(output_path)
        json_path = os.path.join(output_path, 'callgraph.json')
        return cls._add_edges(func_nodes, graph, json_path)

    @classmethod
    def _load_clazz(cls,clazz_nodes,func_nodes,resource_path,output_path):
        def generate_code(name, fields, functions):
            name = name + '{/n'
            for field in fields:
                name += field.name + ':' + field.signature + ';/n'
            for function in functions:
                name += 'function ' + function.name + ';/n'

            return name + '}'

        clazzs = []
        cls._generate_class_fields_json(output_path)
        json_path = os.path.join(output_path, 'class_fields.json')

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        class_field_map = {item["className"]: list(item["fields"]) for item in data}

        for node in clazz_nodes:
            attrs = node.get_attributes()
            fields_0 = class_field_map[attrs.get("FULL_NAME", "").strip('"')]
            fields_1 = []
            fields_2 = []
            for dict in fields_0:
                name = dict["fieldName"]
                if any(node.get_attributes().get("NAME").strip('"') == name for node in func_nodes):
                    fields_1.append(FieldDef(name,name))
                else:
                    fields_2.append(FieldDef(name, dict["fieldType"]))

            new_clazz = ClazzDef(
                signature=attrs.get("NAME", "").strip('"'),
                name=attrs.get("NAME", "").strip('"'),
                code=attrs.get("CODE", "").strip('"'),
                fields=fields_2,
                functions=fields_1,
                filename=attrs.get("FILENAME", '""').strip('"'),
            )
            file_path = resource_path + '/' + new_clazz.filename
            new_clazz.code = generate_code(new_clazz.code, new_clazz.fields, new_clazz.functions)
            clazzs.append(new_clazz)
        return clazzs

    @classmethod  # 描述了继承关系，但是还没描述属性关系
    def _load_clazz_callgraph(cls, clazz_nodes, clazzs):
        graph = nx.DiGraph()
        # 预先构建 full_name -> node name 映射（便于查找父类）
        full_name_map = {}
        for i in range(len(clazz_nodes)):
            node = clazz_nodes[i]
            attrs = node.get_attributes()
            full_name = attrs.get("FULL_NAME", "").strip('"')
            name = attrs.get("NAME", "").strip('"')
            if full_name:
                full_name_map[full_name] = name

        # 遍历所有类节点，尝试查找继承关系
        for i in range(len(clazz_nodes)):
            node = clazz_nodes[i]
            attrs = node.get_attributes()
            child_name = attrs.get("NAME", "").strip('"')

            if not child_name:
                continue

            # 节点加入图
            graph.add_node(child_name, attr=clazzs[i])

        for i in range(len(clazz_nodes)):
            node = clazz_nodes[i]
            attrs = node.get_attributes()
            child_name = attrs.get("NAME", "").strip('"')
            inherits = attrs.get("INHERITS_FROM_TYPE_FULL_NAME", "").strip('"')  # 这个属性有坑，分号；之前的是全名，分号之后的是name
            inherits = inherits.split(";", 1)[0]
            # 如果继承某个类，并且该父类在我们的节点列表中，添加边：子类 -> 父类
            if inherits in full_name_map:
                parent_name = full_name_map[inherits]
                graph.add_edge(child_name, parent_name)

        return graph

    def eva(self, ctx: EvaContext):
        func_nodes, clazz_nodes = self._prepare(ctx.output_path, ctx.resource_path)
        functions = self._load_funtions(func_nodes, ctx.output_path)
        clazzs = self._load_clazz(clazz_nodes,func_nodes,ctx.resource_path,ctx.output_path)
        ctx.callgraph = self._load_callgraph(func_nodes,functions,ctx.output_path)
        ctx.clazz_callgraph = self._load_clazz_callgraph(clazz_nodes,clazzs)
        #shutil.rmtree(ctx.output_path)
        #shutil.rmtree('/root/workspace')
        #os.remove(f'{ctx.output_path}/cpg.bin')
        #os.makedirs('/root/workspace', exist_ok=True)

    @staticmethod
    def _prepare(output_path: str, resource_path: str):  # 给返回一个过滤后的node列表
        # 第一步：解析代码
        if not os.path.exists(f'{output_path}/cpg.bin'):
            subprocess.run(['joern-parse', resource_path, '--language', 'javascript', '--output', f'{output_path}/cpg.bin'], check=True)  # 这一步生成cpg.bin
        # 第二步：导出 cpg 图
        # 这里的输出路径必须是一个空目录，joern会在这个目录下创建一个新的目录
        if not os.path.exists(f'{output_path}/export.dot'):
            subprocess.run(['joern-export', f'{output_path}/cpg.bin', '--out', f'{output_path}/export', '--repr', 'all'], check=True)
            shutil.move(f'{output_path}/export/export.dot', f'{output_path}/export.dot')
        # 还必须没有最后一级目录，必须有倒数第二级目录
        dot_file = os.path.join(output_path, 'export.dot')
        graphs = pydot.graph_from_dot_file(dot_file)
        # 获取第一个图
        graph = graphs[0]  # 接下来把图过滤一下，只留下函数和类相关的节点
        #shutil.rmtree(output_path)  # 需要查看joern的解析结果的时候可以把这个注释掉
        # 过滤节点,目前是只留下method和typedecl，后面大概还会用到别的
        function_nodes = []
        class_nodes = []
        for node in graph.get_nodes():
            attrs = node.get_attributes()
            label = attrs.get("label", "").strip('"').upper()
            code = attrs.get("CODE", "").strip('"')
            if label == "METHOD" and attrs.get("NAME", "").strip('"') == attrs.get("NAME", "").strip('"').strip(
                    "<>") and code != '<empty>':  ###判断name，留下的话也会有很多空的code，再看看怎么过滤,and code != empty?
                function_nodes.append(node)
            elif label == "TYPE_DECL" and code.startswith("class "):
                class_nodes.append(node)

        return function_nodes, class_nodes
