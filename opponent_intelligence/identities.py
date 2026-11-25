"""Optional local identities. Unverified/missing assets always use neutral placeholders.

Images require explicit provenance, permission and a matching digest; no network IO.
Player identity is scoped to a club and name, never inferred from a shirt number.
"""
import base64
import hashlib
import json
import re
import unicodedata
from html import escape
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).parent / 'resources' / 'identities'


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().casefold()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


def registry():
    try:
        data = json.loads((ROOT / 'registry.json').read_text())
        if not isinstance(data,dict): return {}
        for kind in ('teams','players'):
            if not isinstance(data.get(kind,{}),dict): return {}
            if any(not isinstance(entry,dict) for entry in data.get(kind,{}).values()): return {}
        return data
    except (OSError, ValueError):
        return {}


def team_record(team):
    key = normalize(team)
    for ident, entry in registry().get('teams', {}).items():
        if key in {normalize(n) for n in [ident, entry.get('name', ''), *entry.get('aliases', [])]}:
            return ident, entry
    return key, {}


def player_record(team, name):
    team_id, _ = team_record(team)
    key = normalize(name)
    for entry in registry().get('players', {}).values():
        if entry.get('team_id') == team_id and key in {normalize(n) for n in [entry.get('name', ''), *entry.get('aliases', [])]}:
            return entry
    return {}


def checked_image(entry):
    """Return sanitized PNG bytes only for verified, licensed local raster files."""
    if not all(entry.get(k) for k in ('file', 'verified', 'source', 'license', 'sha256')) or entry.get('verified') is not True:
        return None
    from PIL import Image
    try:
        path = (ROOT / entry['file']).resolve()
        if not path.is_relative_to(ROOT.resolve()) or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
            return None
        raw = path.read_bytes()
        if len(raw) > 8_000_000 or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            return None
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            if image.width * image.height > 16_000_000:
                return None
            image.thumbnail((256, 256))
            output = BytesIO(); image.convert('RGBA').save(output, format='PNG')
        return output.getvalue()
    except (OSError, ValueError, TypeError, KeyError, Image.DecompressionBombError):
        return None


def image_bytes(team, player=None):
    entry = team_record(team)[1] if player is None else player_record(team, player)
    return checked_image(entry)


def initials(name):
    return ''.join(word[0] for word in str(name).split() if word and word[0].isalnum())[:2].upper() or '?'


def identity_html(team, player=None, size=36):
    name = team if player is None else player
    data = image_bytes(team, player)
    kind = 'crest' if player is None else 'headshot'
    label = escape(str(name), quote=True)
    size = max(20, min(96, int(size)))
    if data:
        encoded = base64.b64encode(data).decode()
        return f'<img class="oi-identity {kind}" width="{size}" height="{size}" src="data:image/png;base64,{encoded}" alt="{label} {kind}">'
    shape = 'oi-crest-placeholder' if player is None else 'oi-avatar-placeholder'
    return (f'<span class="oi-identity {shape}" role="img" aria-label="{label}: {kind} unavailable" '
            f'title="{label}: {kind} unavailable" style="width:{size}px;height:{size}px">{escape(initials(name))}</span>')


def profile_html(team, player, minutes=None):
    detail = '' if minutes is None else f'<small>{escape(str(minutes))} minutes · report sample</small>'
    return f'<div class="oi-profile">{identity_html(team, player, 56)}<div><strong>{escape(str(player))}</strong>{detail}</div></div>'


def identity_png(team, player=None):
    """Export-ready verified image, or explicitly neutral shield/initials artwork."""
    data = image_bytes(team, player)
    if data:
        return data
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGBA', (96, 96), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    if player is None:
        draw.polygon([(12, 6), (84, 6), (84, 62), (48, 91), (12, 62)], fill='#e9eeea')
    else:
        draw.ellipse((4, 4, 92, 92), fill='#e5ede7')
    # Initials are a placeholder, never a fabricated crest or portrait.
    label = initials(team if player is None else player)
    font = ImageFont.load_default(size=25)
    draw.text((48, 45), label, fill='#365d50', font=font, anchor='mm')
    output = BytesIO(); image.save(output, format='PNG')
    return output.getvalue()
