#!/usr/bin/env python3
"""多宽度自检：控制台错误、横向溢出、文本裁切、深链有效性、缩放、键盘、主题。

前提：产物遵守本 skill 的 DOM 契约（见 references/interaction-spec.md）：
  section.view[id]  ·  .gwrap > .gscroll > .canvas > .cinner > svg + .gnode
  .gnode .gn-t      ·  [data-z=fit|one|in|out] · [data-zout] · #crumbs · #theme · #announce

用法：
    python3 validate_diagram.py --file diagram.html
    python3 validate_diagram.py --file d.html --widths 1440x900,390x844 --root v-home
退出码：0 干净 · 1 有问题（可直接进 CI）
"""
import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

OPT_PROBES = {'crumbs': "() => (document.getElementById('crumbs')||{}).textContent || 'n/a'",
              'theme': "() => document.documentElement.getAttribute('data-theme') || 'n/a'",
              'announce': "() => (document.getElementById('announce')||{}).textContent || 'n/a'"}


def parse_widths(s):
    out = []
    for part in s.split(','):
        w, h = part.lower().split('x')
        out.append((int(w), int(h)))
    return out or [(1440, 900), (390, 844)]


def href_to_id(h, root):
    return root if h == '' else 'v-' + h.replace('/', '-')


def id_to_href(i, root):
    if i == root:
        return '#/'
    return '#/' + i[2:].replace('-', '/')


def static_checks(html, root):
    ids = set(re.findall(r'<section class="view" id="([^"]+)"', html))
    want = {href_to_id(h, root) for h in re.findall(r'href="#/([^"]*)"', html)}
    missing = sorted(w for w in want if w not in ids)
    orphan = sorted(ids - want - {root})
    return ids, missing, orphan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--widths', default='1440x900,1280x800,390x844')
    ap.add_argument('--root', default='v-home', help='首屏 view id（hash 为 #/ 的那个）')
    a = ap.parse_args()
    a.file = os.path.abspath(a.file)
    html = open(a.file, encoding='utf-8').read()
    root = a.root
    ids, missing, orphan = static_checks(html, root)
    print('views=%d  missing_href_targets=%s  unreachable_views=%s'
          % (len(ids), missing or 'none', orphan or 'none'))
    problems = [] if not missing and not orphan else ['static:missing_or_orphan_views']

    # 用节点数最多的视图做缩放/命中探针
    counts = {}
    for v in re.split(r'(?=<section class="view")', html):
        m = re.search(r'id="(v-[^"]+)"', v[:200])
        if m:
            counts[m.group(1)] = len(re.findall(r'class="gnode[ "]', v))
    graph_view = max(counts, key=lambda k: counts[k]) if counts else None
    print('graph probe view: %s (%d nodes)' % (graph_view, counts.get(graph_view, 0)))

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for W, H in parse_widths(a.widths):
            tag = '%dx%d' % (W, H)
            ctx = br.new_context(viewport={'width': W, 'height': H})
            pg = ctx.new_page()
            errs = []
            pg.on('console', lambda m: errs.append('console:%s %s' % (m.type, m.text))
                  if m.type == 'error' else None)
            pg.on('pageerror', lambda e: errs.append('pageerror:%s' % e))
            pg.goto('file://' + a.file)
            pg.wait_for_timeout(250)
            overflow, clipped, badhash = [], [], []
            for i in sorted(ids):
                pg.evaluate("x => { location.hash = x }", id_to_href(i, root))
                pg.wait_for_timeout(12)
                got = pg.evaluate("() => { const v=document.querySelector('.view:not([hidden])'); return v?v.id:'' }")
                if got != i:
                    badhash.append((id_to_href(i, root), got))
                    continue
                ov = pg.evaluate("() => document.documentElement.scrollWidth - %d" % W)
                if ov > 1:
                    bad = pg.evaluate("""() => { const out=[];
                      document.querySelectorAll('.view:not([hidden]) *').forEach(e=>{
                        const r=e.getBoundingClientRect();
                        if(r.right > window.innerWidth + 1 && r.width > 0)
                          out.push(e.tagName+'.'+(e.className||'').toString().slice(0,28)+'|w='+Math.round(r.width)+'|'+(e.textContent||'').trim().slice(0,24));
                      }); return out.slice(0,6) }""")
                    overflow.append((i, ov, bad))
                cl = pg.evaluate("""() => {
                  const v=document.querySelector('.view:not([hidden])'), out=[];
                  v.querySelectorAll('.gn-t,.gn-m').forEach(e=>{
                    if(e.scrollHeight>e.clientHeight+1 || e.scrollWidth>e.clientWidth+1)
                      out.push(e.className+':'+e.textContent.trim().slice(0,22)); });
                  return out }""")
                if cl:
                    clipped.append((i, cl[:4]))
            zoom = kb = after_esc = node = None
            if graph_view:
                pg.evaluate("x => { location.hash = x }", id_to_href(graph_view, root))
                pg.wait_for_timeout(150)
                zoom = {}
                for lab in ['fit', 'one', 'in', 'out']:
                    sel = ".view:not([hidden]) [data-z='%s']" % lab
                    if pg.query_selector(sel):
                        pg.click(sel)
                        pg.wait_for_timeout(30)
                        zoom[lab] = pg.evaluate("""() => { const w=document.querySelector('.view:not([hidden]) .gwrap');
                          const cv=w.querySelector('.canvas'), inn=w.querySelector('.cinner');
                          return {readout:(w.querySelector('[data-zout]')||{}).textContent,
                                  canvasW: Math.round(cv.getBoundingClientRect().width),
                                  innerT: inn.style.transform}}""")
                if pg.query_selector('.view:not([hidden]) .gscroll'):
                    pg.focus('.view:not([hidden]) .gscroll')
                    for k in ['+', '-', '0']:
                        pg.keyboard.press(k)
                        pg.wait_for_timeout(20)
                    kb = pg.evaluate("() => { const e=document.querySelector('.view:not([hidden]) [data-zout]'); return e?e.textContent:'n/a' }")
                pg.keyboard.press('Escape')
                pg.wait_for_timeout(60)
                after_esc = pg.evaluate("() => { const v=document.querySelector('.view:not([hidden])'); return v?v.id:'' }")
                pg.evaluate("x => { location.hash = x }", id_to_href(graph_view, root))
                pg.wait_for_timeout(150)
                if pg.query_selector(".view:not([hidden]) [data-z='one']"):
                    pg.click(".view:not([hidden]) [data-z='one']")
                    pg.wait_for_timeout(60)
                    # 把图画区域滚进视口：否则窄屏下探针测的是「页面没滚到的地方」，
                    # inview_and_clickable 会谎报 0（见 pitfalls 16：0 有两种含义）。
                    pg.evaluate("""() => { const s = document.querySelector('.view:not([hidden]) .gscroll');
                      if (s) { s.scrollIntoView({block:'center'}); s.scrollLeft = 0; s.scrollTop = 0; } }""")
                    pg.wait_for_timeout(40)
                    node = pg.evaluate("""(gv) => {
                      const box = document.querySelector('#'+gv+' .gscroll');
                      const cr = box ? box.getBoundingClientRect() : {left:0,right:window.innerWidth,top:0,bottom:window.innerHeight};
                      const bottom = Math.min(cr.bottom, window.innerHeight), right = Math.min(cr.right, window.innerWidth);
                      const top = Math.max(cr.top, 0), left = Math.max(cr.left, 0);
                      const nodes=[...document.querySelectorAll('#'+gv+' .gnode')];
                      let hit=0, clipT=0, inview=0;
                      nodes.forEach(el=>{ const r=el.getBoundingClientRect();
                        // 必须整节点落在「滚动容器 ∩ 视口」内，否则中心点会被裁掉、命中 BODY（假阳性）
                        if(r.left>=left && r.right<=right && r.top>=top && r.bottom<=bottom){
                          inview++;
                          const c=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
                          if(el.contains(c)||c===el) hit++; }
                        const t=el.querySelector('.gn-t');
                        if(t && t.scrollHeight>t.clientHeight+1) clipT++; });
                      return {nodes:nodes.length, inview:inview, clickable:hit, title_clipped:clipT} }""",
                        graph_view)
            opt = {}
            for k, js in OPT_PROBES.items():
                try:
                    opt[k] = pg.evaluate(js)
                except Exception:
                    opt[k] = 'n/a'
            if pg.query_selector('#theme'):
                pg.click('#theme')
                pg.wait_for_timeout(30)
                opt['theme'] = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
            print('\n== %s ==' % tag)
            print('  nerr', len(errs), json.dumps(errs[:4], ensure_ascii=False))
            print('  overflow', json.dumps(overflow[:4], ensure_ascii=False))
            print('  clipped', json.dumps(clipped[:4], ensure_ascii=False))
            print('  badhash', json.dumps(badhash[:4], ensure_ascii=False))
            print('  zoom', json.dumps(zoom, ensure_ascii=False))
            print('  kb', json.dumps(kb), 'after_esc', json.dumps(after_esc), 'node', json.dumps(node, ensure_ascii=False))
            print('  opt', json.dumps(opt, ensure_ascii=False))
            if errs or overflow or clipped or badhash:
                problems.append('%s:runtime' % tag)
            if graph_view and after_esc and after_esc == graph_view:
                problems.append('%s:esc_noop' % tag)
            if node and (not node['inview'] or node['clickable'] != node['inview']):
                problems.append('%s:hit_test inview=%d clickable=%d' % (tag, node['inview'], node['clickable']))
            ctx.close()
        br.close()

    print('\nPROBLEMS: %s' % (problems or 'none'))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
