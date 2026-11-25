# Optional identity images

Six ESPN team crests supplied by URL by the user are stored locally under `images/`. Club identities were verified against ESPN team metadata and each downloaded image inspected. Registry entries retain the original URL, ESPN team ID, verification source and SHA-256 digest. Use is recorded as user-requested local display; no independent redistribution license is asserted. All 22 Ajax report players now have local portraits: 15 ESPN headshots plus seven user-supplied background/framing edits. See ESPN_MAPPING.md for the complete identity/image mapping. Runtime identity rendering performs no network requests.

`registry.json` seeds the six clubs and 22 squad players in the initial report. These entries are optional identity metadata, never a source for analytics, team selection, player positions, or lineups. Unknown clubs/players receive the same neutral fallbacks.

## Supply an image

1. Obtain a file with permission for the intended use. Place PNG, JPEG, or WebP files under `identities/images/`.
2. Add/update the appropriate team or club-scoped player entry. Preserve stable identifiers; add explicit aliases for verified spelling variants. Shirt numbers are not identity keys.
3. Set `file` relative to this directory (for example `images/club.png`), `source` to the provenance, `license` to the permission/license description, and `sha256` to the file digest. Record the actual permission/use basis without asserting an unverified license, and verify the player identity and portrait before setting `verified: true`.
4. Restart/rerun the app. Missing files, invalid images, missing provenance, unverified entries and digest mismatches fall back safely. The registry does not itself grant image rights.

All accepted rasters are sanitized and resized before display. Paths cannot escape this directory. Coach Report preview and HTML/PDF exports remain text-only and do not render identity images. No URLs, SVG scripts, scraping or new image dependencies are used.

## Still needed

Crests installed: Ajax (139), PSV (148), AZ (140), Eintracht Frankfurt (125), PEC Zwolle (2565), Almere City (5291). Unknown or invalid assets retain the existing neutral shield fallback. Existing crest dimensions and placements are unchanged.

The seven unavailable ESPN images are supplemented by user-provided photos for Matheus, J. Šutalo, D. Rugani, J. Henderson, M. Godts, B. Traoré and D. Konadu. Original sources and edited PNGs are retained; see [SUPPLIED_HEADSHOTS.md](SUPPLIED_HEADSHOTS.md). Unknown future players still use initials.

Names retain source-report spelling. Full names, identities and rights must be verified when supplying images. No starting formation/pitch positions are inferred. Existing lineup-role tables remain available in Team Overview; this pass does not create a lineup visualization.

ESPN identity/headshot verification status is documented in [ESPN_MAPPING.md](ESPN_MAPPING.md). Identity matching does not activate an image or establish usage permission.
