#!/usr/bin/env python3
"""分层 DAG 布局：最长路径定列 + 重心法排行 + 同层交叉计数。

用法（自检）：
    python3 dag_layout.py --json graph.json
graph.json: {"nodes":[{"id":"a","y":120}, ...], "edges":[{"s":"a","t":"b"}, ...]}
输出：{"cols":{...},"pos":{...},"size":[w,h],"metrics":{"layers":N,"widest":M,"crossings":K}}

也可直接 import：compute_ranks / order_rows / crossings / layout / edge_path
"""
import argparse
import collections
import json
import sys

NODE_W = 186
NODE_H = 56
COL_STEP = 268
ROW_STEP = 84


def _adjacency(ids, edges):
    idset = set(ids)
    adj = collections.defaultdict(list)
    radj = collections.defaultdict(list)
    for e in edges:
        if isinstance(e, dict):
            s, t = e['s'], e['t']
        else:
            s, t = e[0], e[1]
        if s in idset and t in idset and s != t:
            adj[s].append(t)
            radj[t].append(s)
    return adj, radj


def compute_ranks(ids, edges):
    """rank = 最长路径深度（无前驱 = 0）。有环则抛错，分层图必须是 DAG。"""
    adj, radj = _adjacency(ids, edges)
    memo = {}
    stack = set()

    def r(u):
        if u in memo:
            return memo[u]
        if u in stack:
            raise ValueError('cycle detected at %s — 分层布局要求无环，先把回边折叠成阶段' % u)
        stack.add(u)
        ins = [r(v) + 1 for v in radj[u]]
        stack.discard(u)
        memo[u] = max(ins) if ins else 0
        return memo[u]

    for u in ids:
        r(u)
    return memo


def order_rows(ids, edges, ranks, ys=None, passes=6):
    """重心法（barycenter）迭代排序，返回 ({rank: [id,...]}, index)。"""
    ys = ys or {}
    adj, radj = _adjacency(ids, edges)
    cols = collections.defaultdict(list)
    for u in ids:
        cols[ranks[u]].append(u)
    for r in cols:
        cols[r].sort(key=lambda u: (ys.get(u, 0), str(u)))
    idx = {}
    for r in sorted(cols):
        for i, u in enumerate(cols[r]):
            idx[u] = i

    def bary(u, neigh):
        ns = [idx[v] for v in neigh[u] if v in idx]
        return sum(ns) / len(ns) if ns else idx[u]

    order = sorted(cols)
    for _ in range(passes):
        for r in order[1:]:
            cols[r].sort(key=lambda u: (bary(u, radj), ys.get(u, 0)))
            for i, u in enumerate(cols[r]):
                idx[u] = i
        for r in reversed(order[:-1]):
            cols[r].sort(key=lambda u: (bary(u, adj), ys.get(u, 0)))
            for i, u in enumerate(cols[r]):
                idx[u] = i
    return dict(cols), idx


def crossings(ids, edges, ranks, cols):
    """相邻层之间的边交叉数，作为布局质量指标（越低越好，0 最理想）。"""
    pos = {}
    for r in cols:
        for i, u in enumerate(cols[r]):
            pos[u] = i
    by_pair = collections.defaultdict(list)
    for e in edges:
        s, t = (e['s'], e['t']) if isinstance(e, dict) else (e[0], e[1])
        if s in pos and t in pos and ranks.get(s) != ranks.get(t):
            by_pair[(ranks[s], ranks[t])].append((pos[s], pos[t]))
    n = 0
    for es in by_pair.values():
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                (a, b), (c, d) = es[i], es[j]
                if (a - c) * (b - d) < 0:
                    n += 1
    return n


def layout(ids, edges, ys=None):
    """返回 (pos, cols, ranks, (w, h))，pos[id] = (x, y) 为节点左上角。"""
    ranks = compute_ranks(ids, edges)
    cols, _ = order_rows(ids, edges, ranks, ys)
    maxr = max(cols) if cols else 0
    rows_max = max(len(v) for v in cols.values()) if cols else 1
    pos = {}
    for r in sorted(cols):
        n = len(cols[r])
        top = (rows_max - n) * ROW_STEP / 2.0
        for i, u in enumerate(cols[r]):
            pos[u] = (24 + r * COL_STEP, 24 + top + i * ROW_STEP)
    return pos, cols, ranks, (48 + (maxr + 1) * COL_STEP, 48 + rows_max * ROW_STEP)


def edge_path(x0, y0, x1, y1):
    """水平三次贝塞尔：起点向右出、终点向右入，避免折角切到节点。"""
    dx = x1 - x0
    c = max(48, abs(dx) * 0.42)
    return 'M%.1f %.1f C %.1f %.1f %.1f %.1f %.1f %.1f' % (
        x0, y0, x0 + c, y0, x1 - c, y1, x1, y1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', required=True, help='{"nodes":[{"id","y"}],"edges":[{"s","t"}]}')
    ap.add_argument('--out', help='写出布局 JSON；省略则只打印指标')
    a = ap.parse_args()
    d = json.load(open(a.json, encoding='utf-8'))
    ids = [n['id'] if isinstance(n, dict) else n for n in d['nodes']]
    ys = {n['id']: n.get('y', 0) for n in d['nodes'] if isinstance(n, dict)}
    edges = d['edges']
    pos, cols, ranks, size = layout(ids, edges, ys)
    x = crossings(ids, edges, ranks, cols)
    metrics = {'layers': len(cols), 'widest': max((len(v) for v in cols.values()), default=0),
               'crossings': x, 'nodes': len(ids), 'edges': len(edges)}
    out = {'pos': {k: [round(v[0], 1), round(v[1], 1)] for k, v in pos.items()},
           'cols': {str(k): v for k, v in sorted(cols.items())},
           'ranks': ranks, 'size': list(size), 'metrics': metrics}
    if a.out:
        json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(metrics, ensure_ascii=False))
    if x:
        print('crossings>0：重心法已尽力，考虑折叠回边或拆阶段', file=sys.stderr)


if __name__ == '__main__':
    main()
