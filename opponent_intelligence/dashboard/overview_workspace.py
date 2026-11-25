"""Focused Team Overview workspaces; other dashboard pages are unchanged."""
import pandas as pd
import streamlit as st
from .data import table, numeric, match_events, overview
from .overview_ui import text, number, fixture_strip, event_groups, events_html, formation_panel
from ..identities import identity_html


def matches_view(result):
    results = table(result, '05')
    if results.empty:
        st.info('Match results are unavailable. Select Formations or Statistical Observations to inspect other available data.')
        return
    selected = fixture_strip(results, result.team)
    row = results[results.Date.eq(selected)].iloc[0]
    with st.container(border=True, key='overview_match_card'):
        st.html(f'<div class="oi-match">{identity_html(result.team,size=32)} {text(result.team)} '
                f'<span>{text(number(row[result.team]))}–{text(number(row["Opponent Goals"]))}</span> '
                f'{text(row.Opponent)} {identity_html(row.Opponent,size=32)}</div>'
                f'<div class="oi-hint">{text(row.Date)} · {text(row["Home/Away"])} · {text(row.Competition)}</div>')
        detail = st.segmented_control('Match details', ['Events', 'Lineups', 'Formation Periods', 'Source Rows'],
                                      default='Events', key='overview_detail') or 'Events'
        if detail == 'Events':
            events = match_events(result, selected)
            if events.empty:
                st.info('No event table is available for this match.')
            else:
                with st.container(height=390, border=False, key='overview_event_panel'):
                    st.html(events_html(event_groups(events)))
        elif detail in {'Lineups', 'Formation Periods'}:
            data = table(result, '06' if detail == 'Lineups' else '08')
            selected_data = data[data.Date.eq(selected)] if 'Date' in data else pd.DataFrame()
            if selected_data.empty:
                st.info(f'{detail} unavailable for this match.')
            else:
                st.markdown('**Both teams · reported lineup roles**' if detail == 'Lineups' else '**Reported formation periods**')
                if detail == 'Lineups':
                    roster_columns = ['Date', 'Match', 'Team', 'Starter', 'Position', 'No', 'Player']
                    selected_data = selected_data[[c for c in roster_columns if c in selected_data]]
                st.dataframe(selected_data, hide_index=True, width='stretch')
        else:
            st.markdown('**Selected-match events · 07_match_events.csv**')
            events = table(result, '07')
            if 'Date' in events:
                st.dataframe(events[events.Date.eq(selected)], hide_index=True, width='stretch')
            else:
                st.info('Match event source rows unavailable.')
            st.markdown('**Full-sample match results · 05_match_results.csv**')
            st.dataframe(results.sort_values('Date'), hide_index=True, width='stretch')


def formations_view(result):
    st.markdown('#### Reported formation periods · full report sample')
    mode = st.segmented_control('Formation display', ['Comparison', 'Source Rows'], default='Comparison',
                                key='overview_formation_display') or 'Comparison'
    forms = table(result, '09')
    if mode == 'Source Rows':
        st.markdown('**09_formations.csv · report-level aggregates**')
        if forms.empty:
            st.info('Formation-specific metrics are unavailable.')
        else:
            st.dataframe(forms, hide_index=True, width='stretch')
    else:
        from .data import formation_usage
        formation_panel(result, forms, formation_usage(result))


def observation_cards(result):
    """Present the existing observations, without changing their evidence drafts."""
    from .page_analysis import overview_observations
    seeds = overview_observations(result)
    cards = []
    results = table(result, '05')
    summary = overview(result)
    for seed in seeds:
        if seed['title'] == 'Conceded-goal concentration':
            goals = numeric(results['Opponent Goals'])
            count = int(goals.gt(0).sum())
            rows = [(str(row.Opponent), float(goal)) for (_, row), goal in zip(results.iterrows(), goals)]
            cards.append(dict(seed=seed, value=f'{summary["goals_against"]:g} goals in {count}/{len(results)} matches',
                              scope='Full sample · goals conceded by match', rows=rows, signed=False))
        elif seed['title'] == 'Formation xG comparison':
            forms = table(result, '09')
            xg = forms[forms.Metric.eq('xG')].copy()
            xg['balance'] = numeric(xg[result.team]) - numeric(xg.Opponent)
            xg = xg.dropna(subset=['balance'])
            leaders = xg[xg.balance.eq(xg.balance.max())]
            cards.append(dict(seed=seed, value=f'{xg.balance.max():+.2f} xG balance',
                              scope=', '.join(leaders.Formation.astype(str)) + ' · highest among reported formations',
                              rows=list(zip(xg.Formation.astype(str), xg.balance)), signed=True))
    return cards


def observations_view(result):
    from ..workflow.ui import draft_action
    cards = observation_cards(result)
    if not cards:
        st.info('No comparable statistical observations are available for this report.')
        return
    for index, (column, card) in enumerate(zip(st.columns(len(cards), gap='medium'), cards)):
        with column, st.container(border=True):
            st.html(f'<div class="oi-label">{text(card["seed"]["title"])}</div>'
                    f'<div class="oi-observation-value">{text(card["value"])}</div>'
                    f'<div class="oi-observation-scope">{text(card["scope"])}</div>')
            maximum = max(abs(value) for _, value in card['rows']) or 1
            bars = []
            for label, value in card['rows']:
                width = 100 * abs(value) / maximum
                label_value = f'{value:+.2f}' if card['signed'] else f'{value:g}'
                # Signed balances have separate halves around a common zero baseline.
                if card['signed']:
                    left = 50 if value >= 0 else 50 - width / 2
                    track = f'<div class="oi-balance-track"><span style="left:{left}%;width:{width/2}%"></span></div>'
                else:
                    track = f'<div class="oi-track"><span style="width:{width}%"></span></div>'
                bars.append(f'<div class="oi-observation-row"><span>{text(label)}</span>{track}<b>{text(label_value)}</b></div>')
            st.html(''.join(bars))
            if card['signed']:
                st.markdown('**Formation periods · team xG − opponent xG**')
            # Keep the first legacy button key for prepared-draft compatibility.
            draft_action(result, dict(card['seed'], supporting_evidence=card['seed']['observation'], status='Draft'),
                         'overview' if index == 0 else 'overview_'+str(index), label='Add to Scouting Findings')
