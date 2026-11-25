"""Shared parsing helpers for Hudl Wyscout team report PDFs.

Adapted from assignment 4. Supports the tested text-based Wyscout layout.
"""
import re
import pdfplumber
NUM_RE = re.compile('^<?\\d+(\\.\\d+)?$')
DATA_RE = re.compile("^(-|/|<?\\d+(\\.\\d+)?'?%?/?|/\\d.*|\\d+(\\.\\d+)?/\\d+(\\.\\d+)?|\\d+'?\\+?\\d*'?)$")

def words(page, x0=0, x1=10000, y0=0, y1=10000):
    ws = page.extract_words(extra_attrs=['size'], x_tolerance=1.5)
    return [w for w in ws if x0 <= w['x0'] < x1 and y0 <= w['top'] < y1]

def rows(ws, tol=3.0):
    """Group words into lines by their top coordinate."""
    out = []
    for w in sorted(ws, key=lambda w: w['top']):
        if out and abs(w['top'] - out[-1][0]['top']) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(r, key=lambda w: w['x0']) for r in out]

def is_badge(w):
    return w['size'] < 5 and w['text'].isdigit()

def is_data(text):
    return bool(DATA_RE.match(text))

def cells(tokens):
    """Join word tokens into table cells.

    'a', '/', 'b' or 'a/', 'b' become one cell 'a/b'. A following 'nn%'
    token becomes that cell's pct.
    """
    out, join_next = ([], False)
    for w in tokens:
        t = w['text']
        if t.endswith('%') and out and (not join_next):
            out[-1]['pct'] = t
            continue
        if join_next or (t.startswith('/') and out):
            out[-1]['text'] += t
            join_next = t.endswith('/')
            continue
        if t == '/' and out:
            out[-1]['text'] += t
            join_next = True
            continue
        out.append({'text': t, 'pct': None})
        join_next = t.endswith('/')
    return out

def num(text):
    """'-' -> 0, "481'" -> 481, '0.14' -> 0.14, '<0.01' stays text."""
    t = text.strip().rstrip("'")
    if t == '':
        return None
    if t == '-':
        return 0
    if t.startswith('<'):
        return t
    v = float(t)
    return int(v) if '.' not in t else v

def pct(text):
    if text is None:
        return None
    v = float(text.rstrip('%'))
    return int(v) if v.is_integer() and '.' not in text else v

def value(cell, kind):
    """Turn one cell into the list of column values it feeds."""
    t = cell['text']
    if kind == 'str':
        return [t]
    if kind == 'num':
        return [num(t)]
    if kind == 'height':
        return [None if t == '-' else num(t)]
    if kind == 'cnt%':
        n = num(t)
        return [n, pct(cell['pct']) if cell['pct'] else None]
    if kind in ('pair', 'pair%'):
        if '/' in t:
            a, b = (num(x) for x in t.split('/'))
        else:
            a, b = (num(t), 0)
            if not a == 0:
                raise ValueError(f'single value {t!r} in a pair column')
        if kind == 'pair':
            return [a, b]
        p = None if a == 0 else pct(cell['pct']) if cell['pct'] else None
        return [a, b, p]
    raise ValueError(kind)

def parse_cells(cs, kinds, where=''):
    if not len(cs) == len(kinds):
        raise ValueError(f'{where}: expected {len(kinds)} cells, got {[c['text'] for c in cs]}')
    out = []
    for c, k in zip(cs, kinds):
        out += value(c, k)
    return out

def split_player(row):
    """[badge, name words..., data...] -> (No, name, data tokens)."""
    if not is_badge(row[0]):
        raise ValueError(row[0]['text'])
    i = 1
    while i < len(row) and (not is_data(row[i]['text'])):
        i += 1
    return (int(row[0]['text']), ' '.join((w['text'] for w in row[1:i])), row[i:])

def player_tables(page, header_first, x0=300, x1=10000, y0=0, y1=10000):
    """Split a page area into tables at header rows; keep the player rows.

    header_first: set of words that start a header row ('Defenders', ...).
    Returns a list of tables, each a list of (No, name, data tokens).
    """
    tables, left = ([], None)
    for r in rows(words(page, x0, x1, y0, y1)):
        if r[0]['text'] in header_first and (not is_badge(r[0])):
            tables.append([])
            left = None
        elif tables and is_badge(r[0]):
            left = r[0]['x0'] if left is None else left
            if abs(r[0]['x0'] - left) < 8:
                tables[-1].append(split_player(r))
    return tables

def open_pdf(path):
    return pdfplumber.open(path)

def color_key(c):
    if c is None:
        return None
    if isinstance(c, (int, float)):
        return round(float(c), 2)
    return tuple((round(float(x), 2) for x in c))
