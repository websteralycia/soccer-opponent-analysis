# Supplied player portraits

Seven user-provided photos fill the remaining Ajax report avatars. The 22-player Wyscout report roster remains unchanged. Existing ESPN identity references are retained; these are not labelled ESPN-sourced photos.

The built-in image tool was used for transparent-background extraction and headshot framing. Edits are image-tool derivatives, not pixel-identical original photographs; originals are retained locally. The existing avatar component supplies the unchanged slate `#2c3b4c` background and round fit. No production UI or calculation code changed.

| Wyscout player | Original source | Original local file | Display PNG |
|---|---|---|---|
| M. Godts | [Supplied image](https://cdn-img.staticzz.com/img/planteis/new/52/11/11535211_mika_godts_20241126010145.jpg) | `sources/user-supplied/mika-godts.jpg` | `images/players/ajax-mika-godts-supplied.png` |
| J. Šutalo | [Supplied image](https://cdn-img.staticzz.com/img/jogadores/new/43/15/544315_josip_sutalo_20251125173248.png) | `sources/user-supplied/josip-sutalo.png` | `images/players/ajax-josip-sutalo-supplied.png` |
| D. Rugani | [Supplied image](https://cdn3.futbin.com/content/fifa27/img/players/211320.png?fm=png&ixlib=java-2.1.0&verzion=3&w=512&s=c1815881bd48ff3dc185271e0817276b) | `sources/user-supplied/daniele-rugani.webp` | `images/players/ajax-daniele-rugani-supplied.png` |
| J. Henderson | [Supplied image](https://ajax.bbvms.com/mediaclip/5791955/pthumbnail/832/1479.webp?cpPassThrough) | `sources/user-supplied/jordan-henderson.webp` | `images/players/ajax-jordan-henderson-supplied.png` |
| B. Traoré | [Supplied image](https://cdn-img.staticzz.com/img/jogadores/new/63/76/156376_bertrand_traore_20241126004754.jpg) | `sources/user-supplied/bertrand-traore.jpg` | `images/players/ajax-bertrand-traore-supplied.png` |
| D. Konadu | [Supplied image](https://assets.bundesliga.com/player/dfl-obj-j0209m-dfl-clu-j0003n-dfl-sea-0001k9.png?fit=256,256) | `sources/user-supplied/don-angelo-konadu.png` | `images/players/ajax-don-angelo-konadu-supplied.png` |
| Matheus | [Supplied image](https://images.fotmob.com/image_resources/playerimages/261348.png) | `sources/user-supplied/matheus.png` | `images/players/ajax-matheus-supplied.png` |

## Image-edit prompt set

Tool: built-in image generation/editing (background-extraction / identity-preserving framing). No fallback CLI used. Each supplied photo was a separate edit target. The common prompt requested: preserve the exact face, expression, hair, skin texture, pose and kit; remove background to true alpha; square canvas; whole head visible; hair near 10% canvas height, chin near 78%, head width about 48%; existing app supplies slate; no invented text/objects/body parts. Godts explicitly requested removal of white background. Henderson/Traoré/Konadu used that same background/framing specification. Šutalo/Rugani/Matheus additionally requested no smoothing beyond original quality. Konadu received a second tighter head-and-neck crop request (hair 10%, chin 75%, eyes 40%, crop off chest/arms) to match other avatars.

Missing/unrelated-team identities still fall back to initials. The existing 15 ESPN photos and all six team crests are untouched. Coach Report remains text-first and image-free.

Validation: 59 focused tests passed. All 21 outfield selections, comparisons and laptop layouts were verified in the browser. Original report roster, production code, existing portraits/crests and saved database checksums remained unchanged.
