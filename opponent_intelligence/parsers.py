"""Layout-specific parsers adapted from assignment_4; no file writes or import side effects."""
import datetime as dt
import re
from pathlib import Path
import pandas as pd
from .pdf_helpers import cells, color_key, is_badge, num, parse_cells, pct, player_tables, rows, split_player, value, words
RESOURCES = Path(__file__).resolve().parent / 'resources'
CM_ROLES = {'DMF', 'RDMF', 'LDMF', 'RCMF', 'LCMF'}
ICON = {0.2: 'Goal', (0.97, 0.79, 0.09): 'Yellow card', (0.78, 0.09, 0.16): 'Red card', (0.16, 0.69, 0.27): 'Subbed on', (0.83, 0.18, 0.21): 'Subbed off'}

def squad(page):
    """p2: squad list. Foot is an icon: the darker of the two soles."""
    foot_hdr = next((w for w in words(page) if w['text'] == 'Foot'))
    soles = [c for c in page.curves if foot_hdr['x0'] - 8 < c['x0'] < foot_hdr['x1'] + 8 and c['top'] > foot_hdr['bottom']]
    pos_x = next((w for w in words(page) if w['text'] == 'Position'))['x0']
    group, out = ('Goalkeepers', [])
    for r in rows(words(page, y0=foot_hdr['bottom'] + 2)):
        if r[0]['text'] in ('DEFENDERS', 'MIDFIELDERS', 'ATTACKERS'):
            group = r[0]['text'].title()
            continue
        if not is_badge(r[0]):
            continue
        name = ' '.join((w['text'] for w in r[1:] if w['x0'] < pos_x - 5))
        data = [w for w in r[1:] if w['x0'] >= pos_x - 5]
        cs = cells(data)
        vals = parse_cells(cs, ['str', 'num', 'height', 'num', 'num', 'num', 'num', 'num', 'pair', 'pair'], f'squad {name}')
        mine = sorted((c for c in soles if abs(c['top'] - r[0]['top']) < 6), key=lambda c: c['x0'])
        if not len(mine) == 2:
            raise ValueError((name, len(mine)))
        dark = [color_key(c['non_stroking_color']) <= 0.5 for c in mine]
        foot = {(True, False): 'Left', (False, True): 'Right', (False, False): None}[tuple(dark)]
        position, age, height, matches, total, avg, goals, assists, yc, rc, sub_in, sub_out = vals
        out.append(dict(No=int(r[0]['text']), Player=name, Group=group, Position=position, Age=age, Foot=foot, Height=height, Matches=matches, Total=total, Avg=avg, Goals=goals, Assists=assists, YC=yc, RC=rc, In=sub_in, Out=sub_out))
    return out
PLAYER_PAGES = {3: ['num', 'pair', 'pair', 'pair%', 'pair%', 'pair%', 'pair%', 'pair%', 'pair', 'pair', 'num', 'pair'], 4: ['num', 'pair%', 'pair%', 'pair%', 'pair%', 'num', 'pair', 'pair%', 'pair', 'num', 'num', 'num', 'num'], 5: ['num', 'pair%', 'pair%', 'pair%', 'pair%', 'pair%', 'pair%', 'pair%', 'pair%', 'num', 'num', 'pair', 'num']}

def player_page(page, kinds, names):
    hdr = next((w for w in words(page) if w['text'] == 'Player'))
    out = []
    for r in rows(words(page, y0=hdr['bottom'] + 2)):
        if not is_badge(r[0]):
            continue
        no, name, data = split_player(r)
        vals = parse_cells(cells(data), kinds, f'p{page.page_number} {name}')
        out.append([no, names.get(no, name)] + vals)
    return out
FORM_RE = re.compile('^\\d(-\\d)+$')
METRICS = {'GOALS': 'Goals', 'XG': 'xG', 'POSSESSION, %': 'Possession %', 'PASS ACCURACY, %': 'Pass Accuracy %', 'MATCH TEMPO': 'Match Tempo', 'LONG PASS SHARE, %': 'Long Pass Share %', 'PPDA RC_PPDA_ABBR': 'PPDA'}

def pitch_players(ws, n=11):
    """Pair shirt numbers with the name printed just below them."""
    nums = [w for w in ws if w['text'].isdigit()]
    name_ws = [w for w in ws if not w['text'].isdigit()]
    names = []
    for w in sorted(name_ws, key=lambda w: (round(w['top']), w['x0'])):
        if names and abs(names[-1]['top'] - w['top']) < 1 and (0 <= w['x0'] - names[-1]['x1'] < 4):
            names[-1] = dict(names[-1], text=names[-1]['text'] + ' ' + w['text'], x1=w['x1'])
        else:
            names.append(dict(w))
    players, used = ([], set())
    for nw in nums:
        cx = (nw['x0'] + nw['x1']) / 2
        cands = [(abs((m['x0'] + m['x1']) / 2 - cx) + (m['top'] - nw['top']), i) for i, m in enumerate(names) if 0 < m['top'] - nw['top'] < 20 and abs((m['x0'] + m['x1']) / 2 - cx) < 25]
        if not cands:
            raise ValueError(f'no name under number {nw['text']}')
        _, i = min(cands)
        if not i not in used:
            raise ValueError(f'name {names[i]['text']} matched twice')
        used.add(i)
        players.append(dict(no=int(nw['text']), name=names[i]['text'], x=cx, y=nw['top']))
    if not len(players) == n:
        raise ValueError([p['no'] for p in players])
    return players

def line_order(players, formation):
    """GK, then each line from the back (formation digits), left to right."""
    ps = sorted(players, key=lambda p: -p['y'])
    out, i = ([], 0)
    for size in [1] + [int(d) for d in formation.split('-')]:
        out += sorted(ps[i:i + size], key=lambda p: p['x'])
        i += size
    return out

def formations(page):
    ws = words(page)
    labels = [w for w in ws if FORM_RE.match(w['text']) and w['size'] > 12]
    res, lineups = ([], [])
    for lab in labels:
        big = lab['size'] > 20
        usage = next((w for w in ws if w['text'].endswith('%') and 0 < w['top'] - lab['top'] < 45 and (abs(w['x0'] - lab['x0']) < 40)))
        if big:
            pitch = words(page, 0, 300, 95, lab['top'] - 5)
            stats = words(page, 0, 300, lab['top'] + 50, lab['top'] + 200)
        else:
            pitch = words(page, 305, 450, lab['top'] - 10, lab['top'] + 170)
            stats = words(page, 455, 600, lab['top'] + 30, lab['top'] + 170)
        for r in rows(stats):
            label = ' '.join((w['text'] for w in r[1:-1]))
            res.append([lab['text'], int(usage['text'].rstrip('%')), METRICS[label], num(r[0]['text']), num(r[-1]['text'])])
        for p in line_order(pitch_players(pitch), lab['text']):
            lineups.append([lab['text'], p['no'], p['name']])
    return (res, lineups)

def match_page(page, team):
    ws = words(page)
    score = [w for w in ws if w['size'] > 20 and w['top'] < 100 and w['text'].isdigit()]
    hg, ag = (int(score[0]['text']), int(score[1]['text']))
    title = [w for w in ws if 100 < w['top'] < 120]
    home = ' '.join((w['text'] for w in title if w['x0'] < 200))
    away = ' '.join((w['text'] for w in title if w['x0'] > 400))
    date_w = next((w for w in title if re.match('\\d\\d\\.\\d\\d\\.\\d{4}$', w['text'])))
    comp = ' '.join((w['text'] for w in title if date_w['x1'] < w['x0'] < 400))
    date = dt.datetime.strptime(date_w['text'], '%d.%m.%Y').strftime('%Y-%m-%d')
    width = int(next((w for w in ws if 135 < w['top'] < 160 and 250 < w['x0'] < 350 and w['text'].isdigit()))['text'])
    depth_chars = sorted((c for c in page.chars if 375 < c['x0'] < 385 and 150 < c['top'] < 420 and c['text'].isdigit()), key=lambda c: c['top'])
    depth = int(''.join((c['text'] for c in depth_chars)))
    match = f'{home} {hg}-{ag} {away}'
    boards_top = min((w['top'] for w in ws if w['top'] > 140 and FORM_RE.match(w['text']) and (abs(w['size'] - 8.2) < 0.3)))
    lineups, events = ([], [])
    for name, (x0, x1), pos_x in ((home, (0, 200), 14), (away, (400, 600), 404)):
        side_ws = [w for w in ws if x0 <= w['x0'] < x1 and 140 < w['top'] < boards_top - 2]
        pos_ws = [w for w in side_ws if abs(w['x0'] - pos_x) < 3 and w['text'].isupper()]
        for i, pw in enumerate(sorted(pos_ws, key=lambda w: w['top'])):
            r = sorted((w for w in side_ws if abs(w['top'] - pw['top']) < 4.5 and w is not pw), key=lambda w: w['x0'])
            badge = r[0]
            if not is_badge(badge):
                raise ValueError((match, pw['text'], badge['text']))
            pname = ' '.join((w['text'] for w in r[1:] if not w['text'].endswith("'")))
            mins = [w for w in r[1:] if w['text'].endswith("'")]
            evs, prev_x1 = ([], 0)
            for m in mins:
                cs = [c for c in page.curves if abs(c['top'] - m['top']) < 5 and max(prev_x1, m['x0'] - 10) < c['x0'] < m['x0']]
                kinds = {color_key(c['non_stroking_color']) for c in cs}
                labels = {ICON.get(k) for k in kinds}
                if not (labels and None not in labels):
                    raise ValueError((match, pname, m['text'], kinds))
                ev = 'Red card' if labels == {'Yellow card', 'Red card'} else labels.pop()
                if not (not labels or ev == 'Red card'):
                    raise ValueError((match, pname, m['text'], labels))
                evs.append((ev, m['text']))
                prev_x1 = m['x1']
            first = lambda e: next((mn for ev, mn in evs if ev == e), None)
            goals = [mn for ev, mn in evs if ev == 'Goal']
            lineups.append([date, match, name, 'Yes' if i < 11 else 'No', pw['text'], int(badge['text']), pname, first('Subbed on'), first('Subbed off'), len(goals), ', '.join(goals) or None, first('Yellow card'), first('Red card')])
            for ev, mn in evs:
                events.append([date, match, name, int(badge['text']), pname, ev, mn])
    periods = []
    for r in rows([w for w in ws if w['top'] >= boards_top - 1 and abs(w['size'] - 8.2) < 0.3]):
        toks = [w['text'] for w in r]
        i = 0
        while i < len(toks):
            if not (FORM_RE.match(toks[i]) and toks[i + 2] == '—'):
                raise ValueError(toks)
            periods.append([date, match, team, toks[i], toks[i + 1], toks[i + 3]])
            i += 4
    venue = 'Home' if home == team else 'Away'
    if not team in (home, away):
        raise ValueError((home, away))
    opp = away if venue == 'Home' else home
    tg, og = (hg, ag) if venue == 'Home' else (ag, hg)
    result = [date, comp, home, away, hg, ag, venue, opp, tg, og, 'W' if tg > og else 'D' if tg == og else 'L', width, depth]
    for nm, g in ((home, hg), (away, ag)):
        n = sum((1 for e in events if e[2] == nm and e[5] == 'Goal'))
        if not n == g:
            raise ValueError(f'{match}: {nm} has {n} goal icons for {g} goals')
    return (result, lineups, events, periods)

def defence(page, names):
    t = player_tables(page, {'Defenders'})
    kinds = [['cnt%', 'num', 'num'], ['cnt%', 'pair', 'pair'], ['pair%', 'pair%']]
    return [[[no, names.get(no, nm)] + parse_cells(cells(d), k, nm) for no, nm, d in tab] for tab, k in zip(t, kinds)]

def full_name(short, squad_names):
    if short in squad_names:
        return short
    stem = short.rstrip('…').rstrip('.')
    hits = [n for n in squad_names if n.startswith(stem)]
    if not len(hits) == 1:
        raise ValueError((short, hits))
    return hits[0]

def build_up(page, names, foot_of):
    ws = words(page, y0=80, y1=800)
    heads = [w for w in ws if w['size'] > 10 and (w['x0'] < 100 or 320 < w['x0'] < 420)]
    blocks = []
    for side, (hx0, hx1), (tx0, tx1) in (('L', (0, 300), (150, 300)), ('R', (300, 600), (450, 600))):
        hs = rows([w for w in heads if hx0 <= w['x0'] < hx1])
        for j, h in enumerate(hs):
            top = h[0]['top']
            nxt = hs[j + 1][0]['top'] if j + 1 < len(hs) else 800
            blocks.append(dict(side=side, top=top, name=' '.join((w['text'] for w in h)), area=words(page, tx0, tx1, top, nxt - 5), foot_ws=words(page, hx0, hx0 + 120, top + 5, top + 20)))
    blocks.sort(key=lambda b: (round(b['top'] / 40), b['side']))
    summary, receivers = ([], [])
    for b in blocks:
        passer = full_name(b['name'], list(names.values()))
        foot_word = next((w['text'] for w in b['foot_ws'] if w['text'] in ('LEFT', 'RIGHT')))
        passes = dribbles = (0, 0, None)
        for r in rows(b['area']):
            if is_badge(r[0]):
                no, nm, d = split_player(r)
                cnt, share = parse_cells(cells(d), ['cnt%'], nm)
                receivers.append([passer, no, names.get(no, nm), cnt, share])
            elif r[0]['text'] in ('Passes', 'Dribbles'):
                v = tuple(parse_cells(cells(r[1:]), ['pair%'], r[0]['text']))
                if r[0]['text'] == 'Passes':
                    passes = v
                else:
                    dribbles = v
        summary.append([passer, foot_word.title(), *passes, *dribbles])
    return (summary, receivers)

def attack(page, names):
    t = player_tables(page, {'Takers', 'Receivers', 'Dribblers', 'Players'})
    kinds = [['pair%', 'pair%', 'num', 'num'], ['height', 'pair%', 'pair', 'num', 'num'], ['cnt%', 'pair', 'num', 'num'], ['num', 'pair', 'num', 'num']]
    return [[[no, names.get(no, nm)] + parse_cells(cells(d), k, nm) for no, nm, d in tab] for tab, k in zip(t, kinds)]

def finishing(page, names):
    shots_hdr = [w for w in words(page, 300) if w['text'] == 'Shots'][0]
    summary = []
    for r in rows(words(page, 300, y0=shots_hdr['bottom'] + 2, y1=shots_hdr['top'] + 270)):
        if is_badge(r[0]) or r[0]['text'] in ('Player', 'Minutes'):
            break
        i = next((k for k, w in enumerate(r) if re.match('^\\d', w['text'])))
        label = ' '.join((w['text'] for w in r[:i]))
        summary.append([label] + parse_cells(cells(r[i:]), ['pair%', 'num', 'num'], label))
    left = words(page, 0, 300, 190, 250)
    labs = [w for w in left if re.match("^\\d+-\\d+\\+?'$", w['text'])]
    intervals = []
    for lab in sorted(labs, key=lambda w: w['x0']):
        cx = (lab['x0'] + lab['x1']) / 2
        v = min((w for w in left if w['text'].isdigit() and lab['top'] - 50 < w['top'] < lab['top'] - 5), key=lambda w: abs((w['x0'] + w['x1']) / 2 - cx))
        intervals.append([lab['text'], int(v['text'])])
    t = player_tables(page, {'Player'})
    shots = [[no, names.get(no, nm)] + parse_cells(cells(d), ['num', 'pair%', 'num', 'num'], nm) for no, nm, d in t[0]]
    keyp = [[no, names.get(no, nm)] + parse_cells(cells(d), ['num', 'num', 'num', 'num'], nm) for no, nm, d in t[1]]
    return (summary, intervals, shots, keyp)

def per90_tables(page, names, kinds_list):
    t = player_tables(page, {'Minutes'})
    if not len(t) == len(kinds_list):
        raise ValueError(len(t))
    return [[[no, names.get(no, nm)] + parse_cells(cells(d), k, nm) for no, nm, d in tab] for tab, k in zip(t, kinds_list)]

def set_pieces(page, names):

    def taker(no, nm, d):
        nm, foot = nm.rsplit(' ', 1) if nm.endswith((' Left', ' Right')) else (nm, None)
        if foot is None:
            if not d[0]['text'] == '-':
                raise ValueError(nm)
            d = d[1:]
        return [no, names.get(no, nm), foot] + parse_cells(cells(d), ['num', 'num', 'num'], nm)
    out = []
    for tab in player_tables(page, {'Takers'}, 0, 300):
        out.append((0, [taker(*row) for row in tab]))
    for tab in player_tables(page, {'Players'}, 300, 600):
        out.append((300, [[no, names.get(no, nm)] + parse_cells(cells(d), ['height', 'num', 'num', 'num'], nm) for no, nm, d in tab]))
    takers = [t for x, t in out if x == 0]
    shots = [t for x, t in out if x == 300]
    return (takers[0], shots[0], takers[1], shots[1])

def glossary(page):
    """The glossary is fixed Wyscout text. Its extracted text loses spaces, so
    check it letter-for-letter against the Frankfurt glossary and reuse that."""
    fra = pd.read_csv(RESOURCES / 'glossary.csv', encoding='utf-8-sig')
    squash = lambda s: re.sub('[^0-9A-Za-z]', '', s).lower()
    w, h = (page.width, page.height)
    text = squash(page.crop((0, 0, w / 2, h)).extract_text() + page.crop((w / 2, 0, w, h)).extract_text())
    missing = [t for t, d in zip(fra.Term, fra.Definition) if squash(d) not in text]
    if not not missing:
        raise ValueError(f'glossary differs from Frankfurt for: {missing}')
    return fra.values.tolist()
SUCCESS = [('General', 'Shots', 'Shots', 'Shots on Target'), ('General', 'Passes', 'Passes', 'Passes Accurate'), ('General', 'Crosses', 'Crosses', 'Crosses Accurate'), ('General', 'Dribbles', 'Dribbles', 'Dribbles Successful'), ('General', 'Duels', 'Duels', 'Duels Won')]
SUCCESS += [('Duels & Set Pieces', m, m, m + ' Won') for m in ('Defensive Duels', 'Offensive Duels', 'Aerial Duels', 'Loose Ball Duels', 'Sliding Tackles')]
SUCCESS += [('Passing', m, m, m + ' Accurate') for m in ('Forward Passes', 'Back Passes', 'Lateral Passes', 'Short + Medium Passes', 'Long Passes', 'Progressive Passes', 'Passes to Final Third', 'Through Passes')]
COUNTS = [('General', m) for m in ('Goals', 'xG', 'Assists', 'xA', 'Losses', 'Losses Own Half', 'Recoveries', 'Recoveries Opponent Half', 'Touches in Penalty Area')]
COUNTS += [('Duels & Set Pieces', m) for m in ('Shots Blocked', 'Interceptions', 'Clearances', 'Fouls', 'Fouls Suffered')]
COUNTS += [('Passing', m) for m in ('Deep Completions', 'Key Passes', 'Shot Assists')]

def central_mids(lineups, team):
    """Players with more than half their lineup appearances in a central midfield role."""
    mine = lineups[lineups.Team == team]
    share = mine.groupby('Player').Position.apply(lambda s: s.isin(CM_ROLES).mean())
    return sorted(share[share > 0.5].index)

def team_totals(gen, duels, passing, cm, n):
    def checked_sum(series):
        if series.isna().any():
            raise ValueError(f'Missing values prevent exact total for {series.name}')
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError(f'Non-numeric or bounded values prevent exact total for {series.name}')
        return series.sum()

    tables = {'General': gen, 'Duels & Set Pieces': duels, 'Passing': passing}
    succ, cnt = ([], [])
    for src, metric, tot_c, ok_c in SUCCESS:
        df = tables[src]
        is_cm = df.Player.isin(cm)
        t, s = (checked_sum(df[tot_c]), checked_sum(df[ok_c]))
        ct, cs = (checked_sum(df.loc[is_cm, tot_c]), checked_sum(df.loc[is_cm, ok_c]))
        succ.append([src, metric, int(t), int(s), round(100 * s / t, 1) if t else None, round(t / n, 1), int(ct), int(cs), round(100 * cs / ct, 1) if ct else None])
    for src, metric in COUNTS:
        df = tables[src]
        t = round(checked_sum(df[metric]), 2)
        c = round(checked_sum(df.loc[df.Player.isin(cm), metric]), 2)
        cnt.append([src, metric, t, round(t / n, 2), c, round(100 * c / t, 1) if t else None])
    return (succ, cnt)

def frame(rows_, cols):
    """Build a DataFrame whose CSV matches the Frankfurt number formatting:
    a column of whole numbers prints as integers, a column with any decimal
    as floats, and a column with any text value as written."""
    data = {}
    for j, c in enumerate(cols):
        raw = [row[j] for row in rows_]
        vals = [v for v in raw if v is not None]
        if not vals or any((isinstance(v, str) for v in vals)):
            data[c] = pd.Series(raw, dtype=object)
        elif any((isinstance(v, float) for v in vals)):
            data[c] = pd.Series(raw, dtype=float)
        else:
            data[c] = pd.Series(raw, dtype='Int64')
    return pd.DataFrame(data, columns=cols)
