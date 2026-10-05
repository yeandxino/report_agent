# -*- coding: utf-8 -*-
"""深挖抖音可用的免费解析通道"""
import sys, requests, re, json
sys.stdout.reconfigure(encoding='utf-8')

vid = '7693148092534712232'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

def try_req(name, url, headers=None, allow_redirects=True):
    try:
        r = requests.get(url, headers=headers or {'User-Agent': UA}, timeout=15, allow_redirects=allow_redirects)
        print(f'--- {name}: status={r.status_code} len={len(r.text)} final={r.url[:80]}')
        return r
    except Exception as e:
        print(f'--- {name}: ERR {e}')
        return None

# 1. 之前发现 404 但含 desc/aweme 的页面——深挖
r = try_req('api_v2_iteminfo', f'https://www.iesdouyin.com/api/v2/aweme/iteminfo/?item_ids={vid}')
if r:
    for kw in ['desc', 'aweme', 'nickname', 'item_list', 'RENDER']:
        print('   contains', kw, ':', kw in r.text)
    # 看看是不是验证页或 SSR 页
    m = re.search(r'<title>(.*?)</title>', r.text, re.DOTALL)
    if m: print('   title:', m.group(1)[:80])
    m2 = re.findall(r'window\.(_ROUTER_DATA|_SSR_HYDRATED_DATA|RENDER_DATA)', r.text)
    print('   window data:', m2)

# 2. 试 www.douyin.com 的 web API（带 Referer）
h2 = {'User-Agent': UA, 'Referer': f'https://www.douyin.com/video/{vid}', 'Accept': 'application/json'}
try_req('web_aweme_detail', f'https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={vid}&aid=6383&device_platform=webapp', h2)

# 3. 试 ie.snssdk.com / api 域名
h3 = {'User-Agent': UA, 'Referer': 'https://www.iesdouyin.com/'}
try_req('snssdk_iteminfo', f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={vid}', h3)

# 4. 试 365yg / 其他分享域名
try_req('share_video_page', f'https://www.iesdouyin.com/share/video/{vid}/', h3)

# 5. 桌面版 douyin.com/video 页面
h5 = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}
r5 = try_req('www_douyin_video_desktop', f'https://www.douyin.com/video/{vid}', h5)
if r5:
    m = re.search(r'window\._ROUTER_DATA\s*=\s*(.*?)</script>', r5.text, re.DOTALL)
    print('   desktop router:', bool(m))
    if m:
        try:
            d = json.loads(m.group(1).strip())
            def find(o, path='', depth=0):
                if depth > 6: return
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k in ('desc', 'nickname', 'aweme_id', 'statistics') and not isinstance(v, (dict, list)):
                            print('   HIT:', path + '/' + k, '=', str(v)[:100])
                        elif isinstance(v, (dict, list)):
                            find(v, path + '/' + k, depth + 1)
                elif isinstance(o, list):
                    for i, v in enumerate(o[:3]):
                        find(v, path + f'[{i}]', depth + 1)
            find(d)
        except Exception as e:
            print('   parse err:', e)
