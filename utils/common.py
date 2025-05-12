from dataclasses import dataclass
from enum import Enum
from functools import reduce

import networkx as nx


def prefix_with(s: str, p: str) -> str:
    return reduce(lambda x, y: x + y, map(lambda k: p + k + '\n', s.splitlines()))


@dataclass
class _Lang:
    render: str
    markdown: str
    cli: str


class LangEnum(_Lang, Enum):
    cpp = 'C/C++', 'c++', 'cpp'

    # TODO: 其他语言
    # rust = 'Rust', 'rust', 'rs'
    javascript = 'JavaScript', 'javascript', 'js'
    # java = 'Java', 'java', 'java'
    # python = 'Python', 'python', 'py'

    @classmethod
    def from_cli(cls, cli: str):
        for lang in cls:
            if lang.cli == cli:
                return lang
        raise ValueError(f'Invalid language: {cli}')

    @classmethod
    def from_render(cls, render: str):
        for lang in cls:
            if lang.render == render:
                return lang
        raise ValueError(f'Invalid language: {render}')


# 去除有向图中的环，对于每个环，删除rank值最小的节点的入边
def remove_cycle(callgraph: nx.DiGraph):
    rank = nx.pagerank(callgraph)
    while not nx.is_directed_acyclic_graph(callgraph):
        cycle = list(nx.find_cycle(callgraph))
        edge_to_remove = min(cycle, key=lambda x: rank[x[1]])
        callgraph.remove_edge(*edge_to_remove)
    return callgraph
