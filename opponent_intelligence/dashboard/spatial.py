"""Source-bound image registry. Exact PDF identity, never team-name fallback."""
import hashlib
import json
from pathlib import Path
from .data import overview

RESOURCES=Path(__file__).resolve().parents[1]/'resources'
CATEGORIES={
    'Defensive organization':{'defensive_duels','lost_duels','fouls'},
    'Transitions':{'recoveries','final_third_recoveries','losses','lost_duels'},
    'Buildup and progression':set(),
    'Attacking patterns':{'dribbles','final_third_dribbles','crosses'},
    'Set pieces':set(),
}


def registry():
    try:
        return json.loads((RESOURCES/'spatial_registry.json').read_text())['reports']
    except (OSError,ValueError,KeyError):
        return {}


def checked_asset(filename, checksum):
    path=(RESOURCES/filename).resolve()
    if not path.is_relative_to(RESOURCES.resolve()) or not path.is_file():
        return None
    return path if hashlib.sha256(path.read_bytes()).hexdigest()==checksum else None


def spatial_maps(result, fingerprint, category):
    report=registry().get(fingerprint)
    if report is None or report['team']!=result.team or report['matches']!=result.matches:
        return []
    summary=overview(result)
    if summary is None or str(summary['start'].date())!=report['start'] or str(summary['end'].date())!=report['end']:
        return []
    available=[]
    for item in report['maps']:
        if item['key'] not in CATEGORIES.get(category,set()):
            continue
        path=checked_asset(item['file'],item['sha256'])
        if path is None:
            continue
        entry=dict(item,path=path,report=report)
        entry['display_path']=checked_asset(item['display_file'],item['display_sha256']) if item.get('display_file') else None
        entry['header_path']=checked_asset(item['header_file'],item['header_sha256']) if item.get('header_file') else None
        entry['support_path']=checked_asset(item['support_file'],item['support_sha256']) if item.get('support_file') else None
        available.append(entry)
    return available
