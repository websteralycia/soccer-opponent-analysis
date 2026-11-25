# Opponent Analysis Dashboard

A Python/Streamlit analyst workspace for extracting structured CSVs from text-based Hudl Wyscout team reports and reviewing match, formation, and player evidence. No automatic coaching recommendations or video annotation tools are included.

## Run locally

Use Python 3.12 (the tested interpreter). From this project folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The dependencies were already available in the development environment; the dashboard addition installed Plotly 6.9.0 only in the project-local virtual environment. Global Python packages and coursework were not changed. Run commands above only when setting up your own environment.

Upload a PDF, click **Process**, inspect all 36 table statuses, and download individual CSVs or a ZIP containing available CSVs and `extraction_status.json`. Changing the uploaded file clears the previous result. Uploads, extraction results, and ZIPs stay in memory; the application does not save uploaded PDFs or write extraction outputs to disk. The upload processing limit is 30 MB.

## Analyst dashboard

After processing a report, use the six dashboard tabs:

- **Team Overview** derives the focal team, dates, matches, W–D–L, and goals from match results. A compact header and four KPI cards lead into selectable fixture cards, a formation comparison matrix, and a readable selected-match event panel. Goals, cards and substitution batches show minutes, player names and teams without hovering. Selecting a fixture affects only events, lineups, and reported formation snapshots. Formation-side buttons switch between focal-team and opponent metrics. Formation metrics remain aggregates across the report, with explicit coverage warnings; missing periods are not filled.
- **Player Analysis** combines only complete outfield pages 02–04. Choose KPI families, a minimum-minutes threshold, and two players for comparison. Click table headers to sort. Per-90 mode adds normalized counts while retaining attempts, successes, and unnormalized success percentages. It never assigns a player's sample totals to individual matches or positions. Passing-page Shot Assists and Key Passes remain separate; finishing-page Key Passes stay in the explorer.
- **Data Explorer** exposes all available extracted tables with source-page, scope, and coverage notes. Search is literal across columns; optional value filtering combines with search. Download the complete source CSV or the filtered result, alongside the original ZIP export. Report glossary definitions remain accessible.

The charcoal/slate theme and chart accents are neutral, with no team-specific colors, player highlights, or tactical conclusions. Available player metrics are controlled by a reusable semantic catalog and offered only when required source columns exist. A different metric family can be added to the catalog without changing the views.

To launch using the tested project environment (including Plotly):

```sh
.venv/bin/python -m streamlit run app.py
```

If you use a different environment, install `requirements.txt` there. Extraction and table exploration still work when Plotly is absent; the app explains how to enable interactive charts.

### Calculation and scope rules

- Full-sample goals come from match scores, never the formation metric rows.
- Success % = successful / attempts × 100, only when attempts > 0 and successes are valid. Zero attempts remain undefined.
- Per 90 = count × 90 / minutes, only for positive, known minutes. Minutes and percentages are not scaled.
- Missing/bounded values do not become zero; exact arithmetic on `<0.01` is unavailable.
- Formation usage is deduplicated by formation before totaling. Unreported metric coverage remains unknown; formation performance is not allocated to matches.
- Event minutes preserve source labels. Added time is ordered after its base minute and before the next numbered minute. Chart horizontal spacing is ordinal within added time, not elapsed duration; no score-state duration or substitution-impact calculation is attempted.
- Player joins use player name and shirt number within a single report, not incomplete leader lists. Small samples, mixed roles, and source rounding remain visible limitations.
- The finishing-page Key Passes field corresponds to Shot Assists on the passing page in the tested reports, while passing-page Key Passes differ. No unified ambiguous key-pass KPI is calculated.
- Recovery/loss/dribble grids and channel markers remain outside the current 36 tables. Their old hardcoded values are not imported into the dashboard.

The newly supplied assignment notes and submitted presentation were reviewed before implementation. Their tactical hypotheses are not application defaults. In particular, the dashboard avoids using formation goals as full-sample goals and does not infer block height from PPDA or recovery locations.

## Reusable extraction API

```python
from opponent_intelligence import extract_report

result = extract_report(pdf_bytes)  # Also accepts a path or binary stream.
print(result.team, result.matches, result.successful)
print(result.status())
for filename, dataframe in result.tables.items():
    csv_bytes = result.csv_bytes(filename)
zip_bytes = result.zip_bytes()
```

`tables` contains only tables that passed extraction and the implemented consistency checks. `errors` maps failed CSV filenames to messages. `warnings` documents data conventions and limits. A page-level parser may supply several related tables; failure of that parser marks its whole group failed rather than exporting potentially incomplete tables. Unrelated page groups can still succeed. Invalid/unsupported PDFs produce 36 explicit failures. Empty extracted sections currently require review and count as failures; this prototype does not assume empty means zero events.

## Project contents

- `app.py`: upload, processing status, downloads, and dashboard entry point.
- `opponent_intelligence/dashboard/`: pure calculations, semantic catalog, Plotly charts, and Streamlit views.
- `.streamlit/config.toml`: neutral dark theme.
- `opponent_intelligence/extraction.py`: in-memory orchestration, metadata detection, error isolation, and export.
- `opponent_intelligence/parsers.py`: adapted layout-specific Wyscout parsers.
- `opponent_intelligence/pdf_helpers.py`: word grouping and numeric/cell parsing.
- `opponent_intelligence/validation.py`: numeric and cross-table consistency checks.
- `opponent_intelligence/resources/schemas.json`: bundled names and headers for 36 tables.
- `opponent_intelligence/resources/glossary.csv`: bundled glossary, checked against each PDF before export.
- `tests/`: regression, malformed-input, partial-failure, validation, UI, and coursework-preservation checks.

No runtime imports or reads reference `00_assignments`. The original assignment 4 parser/helpers and verification scripts were inspected before adaptation. Schema headers and glossary definitions were bundled from the existing Frankfurt CSVs, resolving the assignment 3 dependency without changing its files. Parser assertions were converted into explicit exceptions so checks also run with Python optimization enabled. Excel formatting and independent pixel-based workbook verification were not copied into the application.

## Schema and value conventions

The 36 CSV filenames and column order follow the coursework schema. Ajax output uses its existing headers unchanged. Other teams use the full name detected on the cover in team-specific headers. Results always use the Ajax-style opponent-first layout:

`Date, Competition, Opponent, Home/Away, <team>, Opponent Goals, Result, <team> Team Width m, <team> Team Depth m`

Consequently, Frankfurt results differ structurally from its original CSV: redundant home/away fields are removed and team headers use `Eintracht Frankfurt`. Regression tests normalize those deliberate differences before comparing every output cell.

- Report `-` in count fields becomes `0`, preserving existing Ajax conventions.
- Actual empty numeric values remain missing, exported as blank cells.
- Unknown height/foot and zero-attempt percentages are blank.
- Missing printed percentages remain missing; success-rate validation flags missing percentages when attempts are positive.
- Percentages are **percentage points**: `84.4` means 84.4%, not 0.844.
- `<0.01` remains a bounded text value, not an invented exact number. If such text prevents an exact derived total, that derived group fails explicitly.
- Player totals cover outfield players, not goalkeepers. Group totals use the original central-midfield appearance-based selection rule and full player totals.
- Some omitted buildup action lines retain the source parser's zero-attempt convention; a genuinely absent expected table is reported as a failure.
- CSV downloads use UTF-8 with BOM for Excel compatibility.

## Validation and known limits

Checks include row widths and nonempty tables; percentage ranges and success/attempt consistency with report rounding; outfield roster membership and minutes; result/cover match counts; unique result dates; goal events versus scores; 11 starters per team; and formation metric completeness/usage. Derived team totals are withheld if required source tables fail validation. The manifest identifies partial extraction.

This is a layout-specific prototype, not a universal Wyscout importer. Match count is inferred from the known 14 non-match pages and cross-checked with cover dates. Coordinates, fonts, vector colors and icons must match the tested layout. Scanned PDFs need OCR, which is not included. Changed layouts, extra pages, changed glossary definitions, encrypted PDFs, or ambiguous player names can fail. Very large/complex PDFs can still take significant processing time; there is no background task queue or processing timeout.

The structured tables contain report aggregates and selected leader lists as well as match details. They do not provide event-level statistics for arbitrary match filtering. Zone grids used by the old chart script are outside these 36 tables. Regression equality checks reproducibility against the existing CSVs; it does not independently certify every source-PDF value or establish correctness for other report versions.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -B -m pytest -p no:cacheprovider tests -q -s
```

The regression fixtures are the existing PDFs and CSVs in the sibling `00_assignments` folder, read only. Runtime extraction is self-contained; these integration tests deliberately use local coursework fixtures. `coursework_hashes.json` records historical SHA-256 hashes. The preservation test checks historical coursework content while allowing newly supplied documents and ignoring Finder metadata; a separate before/after check is used during development to verify the current assignment tree remains unchanged. UI tests cover upload/process/download, report switching, match scope, per-90 controls, explorer search, partial reports, and both five- and six-match fixtures. The uploader is simulated; these are Streamlit AppTest tests, not browser/file-picker end-to-end tests. Pure tests cover goals, missing denominators, formation coverage, creation definitions, and stoppage-time ordering.

### Dashboard validation

The full suite passed with 28 tests, followed by 15 passing dashboard tests after the final source-label adjustment and addition of the missing-Plotly fallback test (29 distinct tests total). Ajax extraction matches 6,946 reference cells and Frankfurt matches 8,029 after the documented schema normalization. The dashboard was exercised with five- and six-match fixtures. All 374 current coursework files matched SHA-256 hashes captured at the start of this implementation. No browser visual review was performed; UI verification used Streamlit AppTest and Plotly figure serialization.


### Compact Team Overview

The overview no longer uses the match-results bars, event scatter chart, or oversized formation plot. It shows full-sample W–D–L and goals plus primary **reported** formation usage, with formation coverage explicitly retained. Source tables and lineup/period details are in an expander. Upload/extraction controls collapse after processing, while original CSV and ZIP downloads remain available. Player Analysis and Data Explorer are unchanged.

Events are grouped by match, team and raw minute only for substitutions. A same-minute batch lists all incoming players and all outgoing players, without inventing individual replacement pairings. One-sided substitution records are labeled incomplete. Original stoppage-time labels remain visible; equal-minute event order follows the source, not an inferred sequence.

Reusable UI components live in `opponent_intelligence/dashboard/overview_ui.py`. Avatars default to initials. `events_html(..., headshots=...)` optionally accepts a caller-supplied mapping of `(team, shirt_number)` to verified raster image bytes; invalid images fall back to initials. The application has no photo lookup, scraping, or image-upload workflow.

Laptop layout uses adjacent formation and event panels, with a bounded scroll area for long match event lists. On smaller screens the panels stack, KPI cards use two columns, and fixtures scroll horizontally within their own strip. Fixture scores are explicitly shown from the focal team's perspective, including away games. No tactical conclusions are generated.


Overview redesign validation: all 34 tests passed, including extraction regressions for both PDFs, existing Player Analysis/Data Explorer interactions, fixture selection, stoppage-time ordering, substitution batches, safe HTML/avatars, and neutral team/sample handling. The final dashboard was also inspected in isolated headless Chrome at 1366×900 and 390×844 using a real PDF upload and Process action. Fixture switching updated match details; neither viewport had page-level horizontal overflow. Laptop and mobile screenshots were reviewed. No dependencies were added for browser validation.

Files changed for this redesign: `app.py`, `dashboard/views.py`, new `dashboard/overview_ui.py` (under `opponent_intelligence`), `tests/test_dashboard.py`, new `tests/test_overview_ui.py`, and this README. The extractor and its resources were unchanged.


### Tactical Analysis (compact first version)

A separate tab adds a segmented selector for Defensive organization, Transitions, Buildup and progression, Attacking patterns, and Set pieces. Only the selected category's contents are rendered. The two-column layout combines compact KPI cards and one selected source-table view with a pitch-zone image viewer. Source definitions, glossary and scope caveats remain available in an expander. Team Overview, Player Analysis and Data Explorer retain their existing functions.

Source coverage:

- Defensive organization: complete outfield recovery/duel totals from 02/03 and formation-specific PPDA from 09. PPDA does not establish block height.
- Transitions: full outfield recoveries/losses from 02, selected final-third recovery outcomes from 19, own-third lost-duel outcomes from 12, and loss leaders from 25. Shots following actions are team outcomes, not automatically shots taken by the named player.
- Buildup: complete outfield progressive-pass attempts/completions from 04 and selected buildup passers/receiver links from 14/15. Receiver shares retain the provider's denominator; no complete passing network is reconstructed.
- Attacking patterns: team finishing summary from 20, selected dribblers/crossers from 18/16, and source-separated Shot Assists/Key Passes from 04. Finishing-page Key Passes are not merged.
- Set pieces: team After set pieces finishing category from 20 and separate reported delivery/shot taker tables from 30–33. Categories may overlap; lists are not summed into conversion rates. Bounded `<0.01` values remain source text.

#### Source-bound spatial assets

The reusable viewer has no team-name fallback or runtime dependency on coursework folders. `opponent_intelligence/resources/spatial_registry.json` registers verified image assets against the exact SHA-256 fingerprint of a source PDF. Team, match count and sample dates must also agree. Map and supporting-chart checksums are verified before display. Unknown/re-exported PDFs, missing or altered assets, and categories without registered maps show an unavailable-data message instead of another report's image. The upload fingerprint already used by the app provides source identity; the extraction pipeline was not changed.

The first registered source is the existing five-match Ajax PDF, with six pitch crops from source pages 12, 16 and 17: ball recoveries, possession losses, dribbling, fouls, won defensive actions, and lost own-third duels. These are static source images, not newly extracted spatial events. The long dribbling legend is restated in the viewer so it is not clipped. Existing recovery/loss, dribbling, foul, and lost-duel distribution charts were copied unchanged and are accessible through an optional supporting-chart expander. Their original colors are retained and explicitly labeled source-specific. The previously audited mixed-action duel-loss-rate chart is not reused.

Every spatial image is labeled with source team, dates, page and five-match aggregate scope, independent of fixture selection. Set-piece spatial maps are not bundled. Other reports continue to support CSV-based tactical panels but require verified, uniquely named assets and a registry entry to display source maps. Adding a source requires registration/asset preparation; there is no map-upload editor or automatic new-report map extraction. Store additional source images in separate report-specific paths and include `resources/spatial/*.png` (or extend package data for deeper subfolders).

This version adds no dependencies, numeric spatial inference, video annotation, or automatic tactical/coaching conclusions.

Validation: **46 tests passed**, covering Ajax/Frankfurt extraction regressions, existing dashboard behavior, selected-category-only rendering, partial reports, exact-source matching, no cross-report fallback, missing/corrupted assets, checksum/path safeguards, and complete-versus-selected-list denominators. All 374 coursework files and existing extraction/core files matched their saved hashes. Map crops and reused charts were visually inspected as local images; this tactical addition was tested with Streamlit AppTest rather than a new browser visual pass.


### Tactical statistical hierarchy and interpretation

Each selected tactical evidence view now has a compact **Statistical standouts** block when meaningful comparisons exist. Rankings are calculated from the active source population, not club-specific findings or overall player ratings. Volume, successful-action count, following-shot count, and source-reported team share are compared only within their explicitly labeled table. Buildup receiver links compare link counts, not incomparable percentages from different passers.

Success-rate standouts require **at least 10 attempts** and at least two eligible entities with different known rates. Rates are compared using unrounded successes/attempts, displayed to one decimal place with the winning counts. Ties are retained rather than broken arbitrarily. Uniform values, all-zero data, missing/bounded values with insufficient exact comparisons, and unavailable source columns produce no standout. Known-value eligibility is shown; a selected-player maximum is never presented as a complete-team maximum.

Tactical tables now default to descending action volume, show counts with in-cell teal bars, and carry explicit Standout annotations alongside subtle player-name shading. Bars scale independently within each column and do not represent a shared percentage denominator. Pairable actions show attempts, successes, and a success percentage recalculated from raw counts. Source-rounded values remain unchanged in Data Explorer and CSV downloads. Reported team shares are never recalculated from shortlist sums. Low-attempt percentages can be displayed but never get a success-leader highlight.

Counts display as integers, percentage points as one-decimal percentages, per-90 rates to one decimal, and xG/xA to two decimals. Missing values remain blank/dashes, and bounds such as `<0.01` remain text. KPI cards use these same explicit units rather than exposing raw calculation precision.

Every registered map now has source-specific descriptive metadata: original title, measurement population, units/percentage denominator, legend, orientation and interpretation limits. The dribbling pitch crop is unchanged; its missing title and long legend are restored as native text around the image. Large zone percentages are shares of all dribble attempts, while inner paired percentages are success/failure within that zone. Recovery, loss and foul grids explain their own denominators and per-match numbers. Own-third defensive maps describe event symbols/shirt numbers rather than a spatial percentage rate. League-relative colors retain the provider's original meaning, including the reversed more/less frequency legends; numerical league benchmarks remain unavailable.

Reported statistics, calculated descriptive comparisons, and analyst interpretations remain separate. No analyst interpretation or automatic tactical conclusion is generated. The metric-source expander documents thresholds, formulas and scope limitations.

Validation for this refinement: **65 tests passed**, including the existing extraction/UI regressions plus standout thresholds, ties, insufficient comparisons, source-reported shares, preserved denominators, bounded values, percentage/count formatting, default sorting, table bars, and metadata for all six maps. Original coursework files and extraction modules matched their starting hashes. All six pitch images were visually reviewed; image measurements/crops were left unchanged in this refinement. UI validation used Streamlit AppTest, not a new browser pass.


## Analyst-to-coach workflow

The application now has **Scouting Findings** and **Coach Report** alongside the existing four analytical pages. Team Overview retains fixture cards, events and formation comparisons, with concise scoped statistical observations. Player Analysis retains player/KPI/minutes/per-90 controls but uses compact comparison tables rather than a large chart. Numerical comparisons are not overall player ratings; success-rate comparisons require both players to have at least 10 attempts. Detailed sortable statistics and definitions are expandable.

### Use the workflow

1. Upload/process the report and explore the available data. Use an **Add to scouting findings** action on an overview/player observation, tactical standout, or the current Data Explorer preview. The action opens a prepared draft in Scouting Findings; it does not save or confirm anything. Alternatively create a finding manually.
2. Review the title, category, observation/hypothesis, supporting and contradictory evidence, structured source references, match context, video reference, interpretation, coaching implication and status. Save explicitly. The source-reference expander preserves definitions, calculation details, scope and prepared snapshots.
3. In **Review / edit**, filter by category/status, edit findings, open the linked source table in Data Explorer, mark findings for the coach report, or explicitly confirm deletion. Draft, Needs Video Review and Confirmed are analyst-controlled statuses.
4. On **Coach Report**, select up to three findings, set the order with Move up/down, and author independent coach-facing summaries, tactical observations and coaching considerations. An initial one-finding draft can be previewed; the target briefing is two or three points. Attach an available registered source visualization if useful.
5. Preview the report and download standalone HTML. Click Prepare PDF export to generate a basic PDF, then download it. Any report edit invalidates the previously prepared PDF until regenerated. Unconfirmed finding statuses remain visible in both export formats.

The coach report separates measured sample outcomes, analyst-recorded statistical evidence, interpretations, video references and recommendations. It carries source/definition details and limitations for linked metrics/images. Empty coach fields are labeled un-authored; no tactical conclusions, videos or recommendations are invented. A finding's coach wording is stored separately from its underlying evidence.

### Local persistence and report isolation

Findings, evidence snapshots, statuses, inclusion/order and coach wording are saved in **`data/scouting.sqlite3`**, created on first use. SQLite uses standard-library transactions and report-scoped queries. This folder is excluded from version control. Set `SOCCER_INTELLIGENCE_DB` to choose another database path.

Report identity is `pdf:<SHA-256 of uploaded PDF bytes>`. Re-upload the same PDF after restarting Streamlit to reopen its findings; uploaded PDFs and extracted tables themselves are not persisted by the app. Identical files with different filenames share a workspace; changed/re-exported bytes create a separate workspace. Programmatic CSV-only usage has a deterministic dataset hash fallback that includes team, sample size, filenames and serialized raw tables. No automatic cross-report migration or team-name matching is performed.

A report-scoped JSON backup can be downloaded from Scouting Findings. For a full database backup, stop Streamlit before copying the database, or use a SQLite-aware backup tool. JSON import/restore is not implemented in this version. Tests use temporary databases and never write into the analyst's real database.

This is a **local, single-user** workspace, not a shared-server authorization system. There is no login, cloud database, collaborative editing or encryption layer. Analyst evidence snapshots do not silently update when calculations/extraction versions change; review the linked source before confirming an old finding.

### PDF/HTML export dependencies and limits

`reportlab==4.5.1` was added to requirements and installed in the existing project virtual environment. Launch with:

```sh
.venv/bin/python -m streamlit run app.py
```

If using another environment, install requirements.txt there. HTML export still works without ReportLab, and the PDF action gives an installation message. PDF output uses ReportLab's bundled Vera fonts, source text and optionally a verified source image. It is a simple paginated briefing (new primary findings start on new pages), not a polished slide deck. Unsupported writing systems may need additional fonts. HTML is self-contained, including selected image bytes. The in-app HTML preview is isolated in an iframe so report print styles do not affect the analytical dashboard.

No video is embedded or annotated; references/timestamps remain analyst-supplied text. Visual choices are currently limited to registered, exact-source PDF assets. Custom chart composition, report-template design, collaborative workflows and backup import are deferred.

### Modules changed

- `opponent_intelligence/workflow/store.py`: SQLite schema, report identities, scoped CRUD, inclusion and ordering.
- `workflow/evidence.py`: structured source definitions and frozen evidence snapshots.
- `workflow/ui.py`: reviewable draft actions, findings forms, selection/order, coach wording, preview and downloads.
- `workflow/reports.py`: isolated report model and HTML/PDF generation.
- `dashboard/page_analysis.py`: descriptive overview/player observations and compact comparisons.
- `dashboard/views.py`, `dashboard/tactical_style.py`, `app.py`: page integration and evidence entry points.
- `.gitignore`, `requirements.txt`, tests and documentation: persistence/dependency setup and regression coverage.

The original extraction pipeline and coursework files are unchanged.

Workflow validation: **78 tests passed** in the final full run. Coverage includes the existing extraction/dashboard regressions; descriptive standout and denominator handling; finding creation/editing/deletion and persistence across new store instances; report-specific isolation; selection/order; independent coach wording; source navigation; draft preparation without saving; HTML sanitization and PDF generation/pagination; preserved zero values and unknown denominators; registered visual embedding; and stale-PDF invalidation. Both generated PDF pages were rendered and visually reviewed. App interaction checks use Streamlit AppTest; no new browser end-to-end pass was performed. The 374 original coursework files and original extraction Python modules matched their starting hashes.

### Dashboard presentation and optional identities

The app uses one centralized charcoal/slate theme (`.streamlit/config.toml`, `opponent_intelligence/presentation.py`, `resources/theme.css`): dark charcoal background, slate cards, light text and restrained teal. Detailed methods/sources remain in expanders; no theme switcher is provided. Original Wyscout maps retain their white backgrounds; transparent coursework charts retain a dark backdrop so their original labels stay readable.

Optional club crests and player headshots are loaded only from the local [identity registry](opponent_intelligence/resources/identities/README.md). No verified image files were available, so the initial six clubs and 22 squad players use neutral, accessible placeholders. Add licensed images with verified provenance and SHA-256 digests as documented there. Player lookup is club/name scoped, independent of shirt numbers; unknown teams and players work without images. Report exports embed images locally. Coach highlights are explicitly selected from the uploaded report roster and do not infer player roles.

### Team Overview workspaces

The shared team header and four summary KPIs stay above three focused views. **Matches** opens by default, with selectable fixtures and **Events / Lineups / Formation Periods / Source Rows**. Event substitutions use arrows and source-reported match lineup positions; missing/conflicting roles are unknown. Verified local headshots retain initials fallbacks. **Formations** contains report-level usage, coverage and every formation KPI, plus source rows. **Statistical Observations** presents existing comparisons visually and links directly to the editable finding-draft workflow. Source methods and limitations remain in **Data Quality & Sample Limits**. This navigation does not change calculations or other dashboard pages.

### Visual Player Analysis

Player Analysis has three focused workspaces: **Player Profile**, **Comparisons**, and **Statistical Observations**. Profile charts switch between progression attempts/completions, actual versus expected attacking output and shot outcomes, and defensive duels/recoveries. Identity cards use the reported squad position as a reference label and existing verified-image/initials fallbacks.

Comparisons defaults to two eligible outfield players and supports multiple selections. Horizontal action charts and success rates have separate axes; metric customization and the complete comparison table remain available below the chart. The attacking-contribution mode plots all eligible players with known xG/xA and positive minutes on xG/90 and xA/90 axes, highlighting selected players. This scatter always uses per-90 axes, independently of the totals toggle.

Statistical Observations ranks the selected action volume, successful count, or qualifying success rate. Success-rate observations require at least ten raw attempts. Existing evidence-source definitions, ties and the editable finding-draft workflow are retained; no finding is automatically saved or confirmed. Every catalogued player metric, all eligible-player statistics, and original source fields remain accessible through supporting tables and Data Explorer. Missing values are never replaced by zeros. No radar benchmarks, player spatial maps, external comparison populations or inferred positions are introduced. Detailed methods are in Data Quality & Sample Limits.

Player charts use compact rounded cards, slim bars and hover-only controls. Sparse shot samples (fewer than five raw attempts) use an outcome indicator with the interactive chart available on demand; all-zero attacking output uses a compact summary. These are presentation rules only and do not change statistical eligibility, rates, findings or exports. Scatter axes include display padding and selected-player names appear in hover tooltips to avoid overlapping persistent labels.

Final Player Profile presentation: progression and comparison bars use Plotly's native rounded ends and explicit label standoff. Attacking defaults to Shooting, Goals/xG, and Chance Creation cards (shot assists, actual assists and expected assists remain distinct); the original interactive plots remain under Detailed attacking charts. Defending shows raw-count duel-success rings (with per-90 counts when enabled) and a recovery/interception dot plot that places opponent-half recoveries on the same recovery row as a subset. No statistical formulas or eligibility populations changed. ESPN retrieval/permission limits and pending player mappings are recorded in `resources/identities/ESPN_MAPPING.md`; no ESPN photos are currently activated.

### Tactical evidence workspaces

Tactical Analysis keeps five categories and links each evidence focus to its own supported primary visual. Own-third wins/losses, fouls, recoveries, losses and dribbles use verified report-specific source maps. Progression, all-area duels, formation PPDA, crossing and set-piece deliveries use compact comparisons. There is no unrelated pitch-map fallback. Buildup loss locations are explicitly context, not buildup-specific events; all-area maps and final-third contributor lists retain separate scope labels.

Supporting player charts show up to eight known contributors. **Statistics & Source Data** retains complete original category tables, row search, source navigation, original registered maps/distribution charts and all existing statistical comparisons. **Data Quality & Sample Limits** contains definitions, denominators, incomplete coverage and interpretation limits. The six sharper display crops were rendered from the same registered source PDF bounds; the original assets, checksums and measurements are retained. Unknown reports never inherit registered Ajax images.

Evidence cards open editable Draft findings without saving or confirming them. **Record an analyst observation** supports reviewing team spatial evidence without inventing numerical summaries. Finding classification is optional: **Potential Weakness**, **Opponent Strength**, **Tactical Tendency**, or unclassified. It is independent of tactical category, status and explicit Coach Report inclusion. Legacy JSON payloads read as unclassified without rewriting stored rows; edits, filtering, backups and HTML/PDF reports preserve the optional field and existing evidence. Classification and coaching language are always analyst-selected. Aggregates alone do not establish recurrence or individual causation.

Tactical redesign validation: the full regression suite passed **119 tests** (including Ajax/Frankfurt extraction and preserved coursework checks). After final hover/percentage/supporting-table refinements, **42 focused tests** passed; a final all-focus rendering check also passed after clarifying the formation-coverage label. Browser review covered all five categories, relevant-map switching, crossing, receiver links, PPDA, enlargement, an unsaved optional-classification draft, and 1366×900 / 1280×800 / 390×844 layouts. A classified Coach Report PDF was rendered and visually inspected. Test records used isolated databases; the application findings rows remained unchanged.

Final-third recovery correction: Transitions now defaults to **Final-third recoveries**, using the registered page-14 event map (original title and positional-pressing/shot/goal legend retained) and selected-player outcomes from table 19. No all-area totals are displayed in this view, and the selected-player rows are not summed into a team total. The existing page-16 distribution remains separately available under **All-area recoveries**. Both assets require the exact registered report identity; other uploads receive the unavailable-map fallback.

Recovery terminology: the tactical selector uses **Attacking-third recoveries** (near the opponent’s goal). Outcome controls use **Team shots / xG / goals following recovery** and explain that the recovering player is not necessarily the shooter. These are display labels only: original PDF titles, CSV column names, measurements, and saved source references are unchanged.

Tactical simplification: Buildup no longer repeats the all-area loss-location focus (the source table remains accessible; the map is in Transitions). Formation PPDA is a compact Formation / Usage / Team PPDA / Opponent PPDA table; coverage belongs in Data Quality & Sample Limits. Attacking uses separate source maps for successful final-third dribbles and crosses (page 14), plus all-pitch dribbling (page 17). The original wide dribbling title/legend is displayed as its own verified source crop above the unchanged map crop. Existing asset keys/files and saved findings remain compatible. Final-third dribble views omit unrelated full-team shooting cards; selected-player shot/xG/goal outcomes remain explicitly scoped. Shot Creation shows full-sample shots/xG/goals, with goals from match results; Crossing shows after-cross shots/xG/goals. Set Pieces is unchanged.

Validation for this simplification: **126 regression tests passed**, including Ajax/Frankfurt extraction, all tactical focuses, exact-source asset matching, missing-map handling, preserved shortlist scopes, PPDA table values/missing values, KPI scoping and match-result goal totals, findings and exports. Browser inspection covered PPDA, Buildup, final-third dribbles, Crossing, all-pitch dribbling with its complete legend, and Shot Creation at laptop widths. All 360 coursework content files and the application’s saved findings rows remained unchanged.

### Scouting Findings: compact editor and draft protection

The existing Create new / Review-edit navigation, filters and finding dropdown remain. The editor groups Finding Details and visible side-by-side Observation / Supporting Evidence, followed by expanders for contradictory evidence and linked sources, Video Review, and Analyst Assessment. Source definitions/snapshots remain accessible with linked sources. Save finding is available at the top and bottom.

Working edits are retained in Streamlit session memory; SQLite is written only on Save finding. Edits survive switching saved findings within the same report. Sending another statistical observation while a prepared draft or working edits exist presents **Keep current draft / Replace unsaved draft**. Replacement requires the explicit action; saving the current finding first can open the proposed observation after a successful save. There is one prepared draft and one proposed replacement, not a draft queue. Failed saves retain working edits. Unsaved work is still session-only and should be saved before changing reports or restarting.

No evidence-generation rules, calculations, report identity, database schema, classifications/statuses, PlayBase text format, Coach Report UI/wording, or exports changed. A pre-refinement application ZIP and consistent SQLite snapshot are retained under `backups/scouting-findings-before-refinement-20261118T054458Z/`.

Validation: **143 regression tests passed**, including nine new editor/draft-protection tests. Browser checks used an isolated test database and covered manual save, prepared findings from all three analysis pages, real typed edits through Keep/Replace, saving before opening an incoming observation, switching/editing saved findings, Coach Report selection and separate wording, and 1366×900 / 1280×800 layouts. Saved analyst data, the backup checksums, and all 360 coursework content files were verified unchanged. An initial run encountered a full system disk; only old generated test-browser profiles were removed, then the complete suite passed. Save failures now display an error while retaining session edits.

### Concise Coach Report brief

Coach Report exports now combine an opponent overview, a compact list of analyst-selected findings, and finding sections ordered around saved coaching content, statistical evidence, source visualization, video references, and the analyst's coaching consideration. Source definitions, calculations, scope and limitations remain beneath each finding in smaller supporting text. Repeated evidence prefixes and exact duplicate source records are removed only from the display; stored snapshots are unchanged. No cover page or separate methodology appendix is added.

PDF output uses readable flowing text, full registered high-resolution image parts (including separate title/legend panels), page/finding context, and a report-ID footer. It does not force each finding onto a new page or shrink long text to a fixed page limit. QA samples produced: zero/one finding 1 page; two with maps 2 pages; three with maps 3 pages; three without maps 2 pages; video-reference sample 2 pages; long-content sample 3 pages; the existing saved functionality-test finding 1 page. Larger authored content can exceed these counts. All eight HTML/PDF sample cases were inspected; no text exceeded page bounds, and complete image titles/legends were retained.

The existing selection, ordering and save workflow remain. Editors start collapsed, with the summary above side-by-side tactical-observation/consideration fields. Unsaved coach edits are session-buffered across navigation, reordering and exclusion/reselection. Preview/export uses saved wording only; visible warnings distinguish unsaved work from report readiness. Readiness checks saved summary, tactical observation (including the existing analyst-interpretation fallback), coaching consideration and review status. Draft exports remain available and clearly marked. No video requirement or automatic confirmation is introduced; no coaching text is generated.

Validation: 154 tests passed. One existing coursework-preservation check fails because `00_assignments/assignment_3/Submission/Alycia_Webster_Recruitment_Recommendation_Presentation.mp4` is absent. The historical baseline was not relaxed and coursework was not edited. Browser checks used isolated QA records and covered 0–3 findings, real typed unsaved edits, navigation, exclusion/reselection, reordering, saving, reopening and export controls at laptop widths. The saved Lucas Rosa test record (including wording, selection, order and timestamps) matched its pre-change hash. Its category/status/wording were not treated as a real tactical conclusion. Storage schema, report identity, other analysis pages and extraction code are unchanged. Pre-refinement code/database copies are in `backups/coach-brief-before-20261118T064344Z/`.

### Text-first monochrome Coach Report

Report preview is now a collapsed-by-default expander; HTML/PDF export controls remain outside it. Preview and both exports use a white background, black text, and neutral dividers. Status/classification are plain text. Team crests, source maps and player images/highlights are omitted from the brief. The Coach Report editor retains its selection/order, three coach text fields, readiness and save workflow; visualization and player-highlight controls are removed.

Existing visualization references and player selections remain stored. Saving coach wording updates only the three text fields, including when stale legacy image widgets exist in session state. Evidence, sources, limits, match/video context and saved findings remain intact. Analysis components, spatial assets, app styling, extraction and storage schema are unchanged. Pre-change code/database snapshots are in `backups/coach-text-before-20261118T071251Z/`.

Browser validation at 1366×900 and 1280×800 verified preview open/close, exports while closed, image-free black/white preview, coach-text saving with hidden references preserved, and analysis maps still available. Generated one/two/three-finding examples used 1/1/2 PDF pages; all pages were visually checked and had no embedded images or colored pixels. Counts depend on authored text length. Real saved records and analysis/theme/asset checksums matched the pre-change snapshot.

Final regression validation: **159 tests passed**; the unchanged coursework-preservation check still fails solely because the historical assignment-3 presentation MP4 is absent. Its baseline was not relaxed. New coverage checks 1–3 image-free monochrome exports, collapsed preview/export placement, and coach-text saves preserving hidden asset fields. Existing source-image/player-identity tests now assert presentation removal while retaining stored references.

### Verified local team crests

The six user-provided ESPN crest URLs are mapped in the existing identity registry: Ajax 139, PSV 148, AZ 140, Eintracht Frankfurt 125, PEC Zwolle 2565 and Almere City 5291. Each is saved locally, SHA-256 checked, and linked to ESPN identity-verification metadata; aliases include the existing report names. No page components, dimensions or layouts changed. Existing header, fixture, match-detail and Coach Report editor-header locations now resolve the assets. Unknown teams retain their fallback; player records are untouched. Coach Report preview/HTML/PDF remain image-free. Relevant identity, overview and text-report tests: **30 passed**.

### Ajax report player headshots

The five-match Wyscout report's `01_squad.csv` is the source of truth for the 22-player population. ESPN metadata does not add players, update positions or change the historical sample. Names/IDs were cross-checked using ESPN's March 2025 Ajax match rosters and athlete metadata. Fifteen actual portraits were visually inspected and installed through the existing local registry; seven verified players had no available headshot and keep initials. Full Wyscout/ESPN names, IDs, filenames, verification status and source links are in `opponent_intelligence/resources/identities/ESPN_MAPPING.md`. Original 350×254 files are preserved, with existing runtime resizing and avatar styling. Current/older photos need not match the report date.

No production Python, statistical logic, filtering, comparisons, layouts, team-logo records, source maps, Coach Report code or saved findings changed. Checksums confirmed the protected code/assets/database unchanged. Pre-change registry is in `backups/headshots-before-20261118T080211Z/`. Regression run: **189 passed**, one existing coursework-preservation failure for the missing assignment-3 presentation MP4; the baseline was not relaxed. Tests cover all 22 identities, explicit aliases, club scope, missing-image fallback, local digests, image proportions, existing player interactions and image-free reports. Raw portraits were visually inspected. Browser automation reached Player Analysis and player selection, but the dropdown automation timed out; further browser inspection was blocked by the automatic approval review usage limit. A complete browser visual sign-off of all selections/comparisons remains outstanding.

Headshot browser validation completed on resume: all 21 report outfield-player selections passed (15 local portraits and six initials fallbacks); the goalkeeper remains outside the existing outfield-only Player Analysis population. Two-player comparison, three-player comparison mixing portraits and initials, attacking-contribution scatter, and 1366×900 / 1280×800 layouts were inspected. No portrait clipping, horizontal overflow or application exceptions were observed. The earlier browser-approval limitation is resolved. Protected production code, team crest assets and saved database checksums still match the pre-headshot snapshot.

### Supplied headshot completion

Seven user-provided player images supplement the 15 ESPN photos. All 22 players in the Wyscout report now have local portraits. Built-in image editing produced transparent backgrounds and avatar framing; original downloads are retained under `opponent_intelligence/resources/identities/sources/user-supplied/`, with display PNGs under `images/players/`. Provenance, filenames, editing notes and prompt specification are in `SUPPLIED_HEADSHOTS.md`. These are photo derivatives; they are not labelled untouched ESPN images. The existing avatar component supplies the slate background and unchanged circular sizes. No production Python, layout, analytics, database records, original coursework, existing ESPN portraits, team crests or Coach Report rendering changed.

Validation: **59 focused tests passed**, covering all 22 identities and local-image checks, transparent square derivatives, unrelated-team/unknown-player fallbacks, player interactions and image-free Coach Report output. Browser checks passed all 21 outfield selections, two/three-player comparisons and the scatterplot at laptop widths; the six new outfield portraits were visually inspected in the dark theme. Matheus remains outside the existing outfield-only Player Analysis population. Protected code/assets/database checksums and all existing ESPN portraits were verified unchanged.

### Player statistical observations: positions

Statistical Observations includes a Position group selector beside Highlight players: All positions and the roster groups available for the currently eligible outfield population (Forwards, Midfielders, Defenders; Unreported when necessary). Attackers is displayed as Forwards; other explicit source groups are retained. Grouping and chart labels use squad-table Player + No matches. Missing/conflicting labels remain unknown, with no inference from match lineups. The ranking chart shows names followed by reported position codes. Filtering affects eligible players, highlights, supporting statistics and standout calculations, while minutes/per-90 and success-attempt thresholds remain unchanged. Scouting Findings evidence retains the selected group; counts still describe the whole report sample, not actions isolated to a position. Definitions remain in the supporting source-data expander. No other pages were redesigned.

Browser checks covered all group options, chart position labels, per-90 switching and 1366×900 / 1280×800 layouts without overflow or application exceptions.

Position-filter validation: **21 player regression tests passed**, including group switching, invalidated highlights, minimum-minutes fallback, per-90 rankings, reported position labels, missing/conflicting roster data, unchanged raw values and group-scoped prepared findings.
