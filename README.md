## RepoHCL
借助LLM理解软件，为项目中的每个源代码文件生成文档

### 工作流程
- 为软件生成AST
- 基于AST解析源代码文件中包含的类与函数，并生成Function/Class CallGraph
- 按Function CallGraph的逆拓扑排序，为各个函数生成文档
- 按Class CallGraph的逆拓扑排序，为各个类生成文档
- 基于函数文档生成模块文档
- 基于模块文档生成仓库文档
### 项目结构
```
├── docker                      # docker封装的项目demo
│    ├── base.dockerfile        # 项目环境基础镜像
│    ├── cmd.dockerfile         # main.py的docker运行环境，命令行执行工具
│    └── service.dockerfile     # service.py的docker运行环境，启动服务端
├── test                        # docker封装的项目测试用例
│    ├── cpp                    # C/C++项目测试用例
│    ├── run.sh                 # 将测试用例复制到本地的脚本   
│    └── run.bat                # 将测试用例复制到本地的脚本(Windows)                 
├── 'resource'                  # 待分析C/C++项目源代码目录(运行时生成)
├── 'docs'                      # 生成的文档目录(运行时生成)
├── 'output'                    # C/C++项目分析中间产物目录(运行时生成)
├── metrics                     # 各个度量指标实现
│    ├── clazz.py               # 类级别度量
│    ├── doc.py                 # 度量结果文档对象
│    ├── function.py            # 函数级别度量
│    ├── function_v2.py         # 函数级别度量（V2）
│    ├── metric.py              # 度量基类及上下文
│    ├── module.py              # 模块级别度量
│    ├── module_v2.py           # 模块级别度量（V2）
│    ├── parser.py              # C/C++软件解析
│    ├── js_parser.py           # JavaScript软件解析
│    ├── repo.py                # 仓库级别度量
│    ├── repo_v2.py             # 仓库级别度量（V2）
│    └── structure.py           # 目录结构度量
├── utils
│    ├── common.py              # 公共工具类库
│    ├── file_helper.py         # 压缩文件工具类库
│    ├── llm_helper.py          # LLM工具类库
│    ├── multi_task_dispatch.py # 多线程任务分发器
│    ├── rag_helper.py          # RAG工具类库
│    └── strings.py             # 字符串工具类库
├── .env                        # 配置文件/环境变量
├── main.py                     # 命令行入口
├── service.py                  # web服务入口
├── requirements.txt            # Python依赖管理
└── README.md                  
```
### 使用说明
- 项目基于OpenAI协议调用LLM，需在.env中设置调用的LLM服务的域名`OPENAI_BASE_URL`、模型`MODEL`、温度`MODEL_TEMPERATURE`、输出语言`MODEL_LANGUAGE`，并配置`OPENAI_API_KEY`作为密钥。默认采用阿里百炼的qwen-plus。
- 本地运行环境可参考`docker/base.dockerfile`。
- RepoMetricV2使用到HuggingFace拉取远端模型，若网络不佳，可在.env中设置`HF_ENDPOINT=https://hf-mirror.com`。
- 在.env中设置`LOG_LEVEL`可以控制日志的输出级别，默认`INFO`级别。
- 在.env中设置`THREADS`可以控制多线程的数量，默认`32`。
- Windows下运行，建议使用UTF-8模式，例如：`python3 -X utf-8`

### TODO
- 提高文档质量，增加对生成结果准确性的评估
- 增加对其他语言的支持：RUST、Java、JavaScript
