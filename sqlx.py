import os
import re
import pprint

import js2py



def sqlformat(sql):
    # sql 美化
    js = open('sqlformat.js').read()
    ctx = js2py.EvalJs()
    ctx.execute(js)
    result = ctx.sqlformat(sql)
    return result


def get_indent(s):
    # 获取字符串前有多少个空格
    return len(s) - len(s.lstrip())



def render(content, define_map, block_map, local_map=None):
    # render sqlt content to sql

    key_map = {}
    key_map.update(define_map)
    if local_map:
        key_map.update(local_map) 


    symbols = re.findall(r'\{.+?\}', content)
    symbols = set(symbols)
    rendered_map = {}
    for symbol in symbols:
        key = symbol.strip('{}').strip()
        if '(' not in key:
            assert key in key_map, '`%s` define 引用未找到!' % symbol
            value = key_map[key]
            # 对于简单的变量替换，直接 replace 就行了
            content = content.replace(symbol, value)
        else:
            rs = re.findall(r'(.+?)\((.*?)\)', key)
            assert len(rs) == 1, '`%s` block 引用语法不正确!' % symbol
            block_name, params = rs[0]
            assert block_name in block_map, '`%s` block 引用未找到!' % symbol
            block_content = block_map[block_name]['content']
            param_names = block_map[block_name]['params']
            params = params.split(',')
            params = [param.strip() for param in params if param.strip()]
            assert len(param_names) == len(params), '%s block 参数数量不正确!' % symbol
            local_map = {}
            for name, value in zip(param_names, params):
                local_map[name] = value
            rendered_block = render(block_content, define_map, block_map, local_map)
            # 对于块替换，为了更好的视觉体验，先将渲染后的块内容保存下来，接下来用到
            rendered_map[symbol] = rendered_block

    lines = content.splitlines()
    new_lines = []
    for line in lines:
        for symbol in rendered_map.keys():
            if symbol in line:
                # 遍历每一行，替换行中的块内容，并加上合适的缩进
                # 例如 `select * from {myblock} where 1=1` 渲染后得到:
                # select * from 
                #     (
                #         SELECT
                #             id, name
                #         FROM
                #             mytable
                #     ) AS myblock
                # where 1=1
                n = get_indent(line)
                rendered_block = rendered_map[symbol]
                rendered_block = rendered_block.replace('\n', '\n' + ' ' * n)
                rendered_block = '\n' + ' ' * n + rendered_block + '\n' + ' ' * n
                # 先尝试替换 symbol 两边有空格的情况
                line = line.replace(' %s ' % symbol, rendered_block)
                line = line.replace(symbol, rendered_block)
        new_lines.append(line)
    content = '\n'.join(new_lines)

    return content


def build(content, pretty=False):
    # build sqlx content to sql

    # SQL Extension Content
    # 确保第一行是空行
    sqlx_content = '\n' + content
    # print(sqlx_content)

    define_map = {}
    block_map = {}


    # 处理 define
    lines = sqlx_content.splitlines()
    new_lines = []
    for line in lines:
        if not line.lower().startswith('define '):
            new_lines.append(line)
            continue
        line = line.replace('=', ' ')
        items = line.split()
        assert len(items) == 3, '`%s` define 语法不正确!' % line
        define, key, value = items
        define_map[key] = value
    # pprint.pprint(define_map)

    # SQL Template Content
    sqlt_content = '\n'.join(new_lines)
    # print(sqlt_content)

    # 处理 block
    block_pattern = r'\nblock\s+?(.+?)\((.*?)\)[:\s]*?\n(.*?)\nendblock'
    blocks = re.findall(block_pattern, sqlt_content, re.S)
    sqlt_content = re.sub(block_pattern, '', sqlt_content, flags=re.S)
    for block in blocks:
        block_name, params, content = block
        params = params.split(',')
        params = [param.strip() for param in params if param.strip()]
        block_map[block_name] = {
            'params': params,
            'content': content,
        }
    # pprint.pprint(block_map)


    sql = render(sqlt_content, define_map, block_map)
    sql = '-- ======== Generated By Sqlx ========\n\n%s\n' % sql.strip()

    # print(sql)

    if pretty:
        sql = sqlformat(sql)

    return sql


print(build(open('test.sql', encoding='utf8').read(), True))

