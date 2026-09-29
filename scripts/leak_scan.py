#!/usr/bin/env python3
"""按形状扫敏感值，不依赖已知字面量清单（清单本身会泄漏）。

用法：
    python3 leak_scan.py <file-or-dir> [<more>...]        # 默认扫全部规则
    python3 leak_scan.py docs/architecture --only host,token,dsn,key

退出码：0 干净 · 1 命中。命中时只打印规则名、位置、脱敏后的片段，绝不打印完整值。
目录里的 .gitignore 会生效（构建时生成的脱敏表本来就不该入库），跳过了几个文件会打印出来。
"""
import argparse
import fnmatch
import os
import re
import sys

RULES = {
    'key': (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), 'PEM 私钥'),
    'aws': (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), 'AWS AccessKey'),
    'jwt': (re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'), 'JWT'),
    'dsn': (re.compile(r'\b(?:redis|rediss|mysql|postgres(?:ql)?|amqp|mongodb(?:\+srv)?):\/\/[^\s\'"`<>)\]]*:[^\s\'"`<>)\]]+@'),
          '带口令的连接串'),
    'ipv4': (re.compile(r'\b(?!(?:127|0)\.)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '公网/内网 IP 字面量'),
    'token': (re.compile(r'(?i)\b(secret|app_secret|app_key|api_key|access_key|sign_key|hmac|token|password|passwd)'
                         r'\b["\']?\s*[:=]\s*["\'][^"\'\s<>]{12,}["\']'), '密钥赋值字面量'),
    'bearer': (re.compile(r'(?i)\b(bearer|basic)\s+[A-Za-z0-9_\-\.=]{16,}'), 'Authorization 头明文'),
    'host': (re.compile(r'\b[\w.-]*\.(?:internal|intranet|local|corp|int)\.[a-z]{2,4}\b'), '内网域名'),
}
ALLOW = re.compile(r'(<[^>]*(?:脱敏|已隐藏|redacted|REDACTED)[^>]*>|\{\{[^}]*\}\}|example\.(com|test|org))')
SKIP_DIR = {'__pycache__', '.git', 'node_modules'}
EXTS = ('.html', '.md', '.py', '.js', '.json', '.yml', '.yaml', '.txt', '.css')


def gitignore_patterns(top):
    """收集 top 目录下所有 .gitignore 的 basename 规则。
    被忽略的文件（例如构建时生成的脱敏表）不该让「已提交内容干净」这条门禁变红，
    但也不能悄悄跳过——调用方要打印跳过了几个。"""
    pats = []
    for root, dirs, names in os.walk(top):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        if '.gitignore' in names:
            for ln in open(os.path.join(root, '.gitignore'), encoding='utf-8', errors='replace'):
                ln = ln.strip()
                if not ln or ln.startswith('#') or '/' in ln or ln.startswith('!'):
                    continue
                pats.append(ln.rstrip('/'))
    return pats


def collect(targets):
    files, skipped = [], []
    for t in targets:
        if os.path.isdir(t):
            pats = gitignore_patterns(t)
            for root, dirs, names in os.walk(t):
                dirs[:] = [d for d in dirs if d not in SKIP_DIR]
                for n in names:
                    if not n.endswith(EXTS):
                        continue
                    if any(fnmatch.fnmatch(n, p) or fnmatch.fnmatch(n, p + '*') for p in pats):
                        skipped.append(n)
                    else:
                        files.append(os.path.join(root, n))
        else:
            files.append(t)
    return files, sorted(set(skipped))


def frag(s, i, n=28):
    """打码后再打印：扫描器自己不能把口令/密钥贴进日志。"""
    out = re.sub(r'[A-Za-z0-9_\-]{4,}', '****', s[i:i + n].strip())
    return re.sub(r'\d{1,3}(\.\d{1,3}){3}', '*.*.*.*', out)


def scan_file(path, rules):
    hits = []
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        print('skip %s (%s)' % (path, e), file=sys.stderr)
        return hits
    for line_no, line in enumerate(txt.split('\n'), 1):
        if ALLOW.search(line):
            continue
        for name in rules:
            pat, desc = RULES[name]
            m = pat.search(line)
            if m:
                hits.append((path, line_no, name, desc, frag(line, m.start())))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('targets', nargs='+')
    ap.add_argument('--only', help='逗号分隔的规则名子集：' + ','.join(RULES))
    a = ap.parse_args()
    rules = a.only.split(',') if a.only else list(RULES)
    unknown = [r for r in rules if r not in RULES]
    if unknown:
        sys.exit('未知规则: %s（可选 %s）' % (unknown, ','.join(RULES)))
    files, skipped = collect(a.targets)
    hits = []
    for f in files:
        hits += scan_file(f, rules)
    for path, ln, name, desc, snip in hits:
        print('%s:%d  [%s %s]  %s…' % (path, ln, name, desc, snip[:28]))
    print('scanned=%d files  hits=%d  skipped_gitignored=%d %s  rules=%s' % (
        len(files), len(hits), len(skipped), skipped, ','.join(rules)))
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
