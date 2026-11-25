# ESPN Ajax report headshot mapping

Roster source: `00_assignments/assignment_4/ajax_report/csv/01_squad.csv` (22 report players). Historical ESPN Ajax match rosters from March 2, 9, 16 and 30, 2025 establish club/sample context; ESPN athlete metadata provides profile names, IDs and image links. The season parameter on the current roster endpoint did not yield the historical squad and was not used as the report population.

Initial ESPN check: 15 available portraits; seven unavailable ESPN images (HTTP 404, no headshot in metadata). Those seven now use the user-supplied portraits documented in [SUPPLIED_HEADSHOTS.md](SUPPLIED_HEADSHOTS.md), bringing the report to 22 local headshots. No ambiguous identity matches remain. Confidence is high for identity, based on historical team membership, names/aliases and reported roles; image verification means the metadata-linked file was visually inspected as a real portrait, not independent biometric authentication. Source photos may be older than the report.

Images are downloaded originals at 350×254; runtime resizing/proportions and existing avatar presentation are unchanged. No synthetic, guessed-player or replacement portraits are used. User requested local display; no independent redistribution license is asserted.

| Wyscout name | ESPN name / profile | ID | Local filename | Verification |
|---|---|---|---|---|
| Matheus | [Matheus](https://www.espn.com/soccer/player/_/id/158174/matheus) | 158174 | ajax-matheus-supplied.png | Verified identity; user-supplied portrait (ESPN image unavailable) |
| J. Hato | [Jorrel Hato](https://www.espn.com/soccer/player/_/id/353951/jorrel-hato) | 353951 | ajax-jorrel-hato.png | Verified identity + portrait |
| Y. Baas | [Youri Baas](https://www.espn.com/soccer/player/_/id/305590/youri-baas) | 305590 | ajax-youri-baas.png | Verified identity + portrait |
| A. Gaaei | [Anton Gaaei](https://www.espn.com/soccer/player/_/id/333312/anton-gaaei) | 333312 | ajax-anton-gaaei.png | Verified identity + portrait |
| J. Šutalo | [Josip Sutalo](https://www.espn.com/soccer/player/_/id/305552/josip-sutalo) | 305552 | ajax-josip-sutalo-supplied.png | Verified identity; user-supplied portrait (ESPN image unavailable) |
| D. Rugani | [Daniele Rugani](https://www.espn.com/soccer/player/_/id/181673/daniele-rugani) | 181673 | ajax-daniele-rugani-supplied.png | Verified identity; user-supplied portrait (ESPN image unavailable) |
| Lucas Rosa | [Lucas Rosa](https://www.espn.com/soccer/player/_/id/351281/lucas-rosa) | 351281 | ajax-lucas-rosa.png | Verified identity + portrait |
| A. Kaplan | [Ahmetcan Kaplan](https://www.espn.com/soccer/player/_/id/306806/ahmetcan-kaplan) | 306806 | ajax-ahmetcan-kaplan.png | Verified identity + portrait |
| D. Janse | [Dies Janse](https://www.espn.com/soccer/player/_/id/368818/dies-janse) | 368818 | ajax-dies-janse.png | Verified identity + portrait |
| O. Wijndal | [Owen Wijndal](https://www.espn.com/soccer/player/_/id/241392/owen-wijndal) | 241392 | ajax-owen-wijndal.png | Verified identity + portrait |
| K. Taylor | [Kenneth Taylor](https://www.espn.com/soccer/player/_/id/282228/kenneth-taylor) | 282228 | ajax-kenneth-taylor.png | Verified identity + portrait |
| D. Klaassen | [Davy Klaassen](https://www.espn.com/soccer/player/_/id/168993/davy-klaassen) | 168993 | ajax-davy-klaassen.png | Verified identity + portrait |
| J. Henderson | [Jordan Henderson](https://www.espn.com/soccer/player/_/id/127262/jordan-henderson) | 127262 | ajax-jordan-henderson-supplied.png | Verified identity; user-supplied portrait (ESPN image unavailable) |
| J. Mokio | [Jorthy Mokio](https://www.espn.com/soccer/player/_/id/381074/jorthy-mokio) | 381074 | ajax-jorthy-mokio.png | Verified identity + portrait |
| O. Edvardsen | [Oliver Edvardsen](https://www.espn.com/soccer/player/_/id/295861/oliver-edvardsen) | 295861 | ajax-oliver-edvardsen.png | Verified identity + portrait |
| K. Fitz-Jim | [Kian Fitz-Jim](https://www.espn.com/soccer/player/_/id/305589/kian-fitz-jim) | 305589 | ajax-kian-fitz-jim.png | Verified identity + portrait |
| B. van den Boomen | [Branco van den Boomen](https://www.espn.com/soccer/player/_/id/196234/branco-van-den-boomen) | 196234 | ajax-branco-van-den-boomen.png | Verified identity + portrait |
| M. Godts | [Mika Godts](https://www.espn.com/soccer/player/_/id/353363/mika-godts) | 353363 | ajax-mika-godts-supplied.png | Verified identity; user-supplied portrait (ESPN image unavailable) |
| S. Berghuis | [Steven Berghuis](https://www.espn.com/soccer/player/_/id/149577/steven-berghuis) | 149577 | ajax-steven-berghuis.png | Verified identity + portrait |
| B. Brobbey | [Brian Brobbey](https://www.espn.com/soccer/player/_/id/282229/brian-brobbey) | 282229 | ajax-brian-brobbey.png | Verified identity + portrait |
| B. Traoré | [Bertrand Traoré](https://www.espn.com/soccer/player/_/id/169661/bertrand-traore) | 169661 | ajax-bertrand-traore-supplied.png | Verified identity; user-supplied portrait (ESPN image unavailable) |
| D. Konadu | [Don-Angelo Konadu](https://www.espn.com/soccer/player/_/id/386841/don-angelo-konadu) | 386841 | ajax-don-angelo-konadu-supplied.png | Verified identity; user-supplied portrait (ESPN image unavailable) |

Full per-player provenance, aliases, source metadata URLs and exact historical match evidence are in `registry.json`. Missing, invalid or unrelated-team images retain the neutral initials fallback. Team crests are unchanged. Coach Report preview/HTML/PDF stay image-free.
