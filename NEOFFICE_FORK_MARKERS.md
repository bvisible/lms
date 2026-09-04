# Neoffice fork markers — `bvisible/lms`

Every change we made to code we did not write carries a `//// Neoffice` comment saying
**why** (see `CLAUDE.md`, rule "mark every change to code that is not ours"). At the next
upstream merge, `grep -rn "////"` gives the complete map of OUR intent versus theirs.

This file is the other half of that map: the divergences that **cannot carry a comment**
(JSON, binaries, build artifacts) and the hunks a comment cannot reach (an attribute list
inside an opening tag). The checker (`bvisible/neoffice-ci` → `scripts/fork_markers.py`)
reads this file and treats a not-commentable path named here as marked.

```bash
python3 fork_markers.py check --base 8e3b5d8eb4d3f26dbf14c0bf4d6522702d20ffbc --head HEAD
```

## lms

### The true base (do not trust the branch name)

| Fact | Value |
|---|---|
| Our branch | `origin/version-15` |
| Upstream | `frappe/lms`, default branch `develop` |
| **BASE** | **`8e3b5d8eb4d3f26dbf14c0bf4d6522702d20ffbc`** — 2026-07-29, "Merge pull request #2621 from Bowrna/fix_link_open_in_newtab" |
| How it was found | `git merge-base origin/version-15 upstream/develop` **and** `… upstream/main` both answer this same commit; it is an ancestor of both (`git merge-base --is-ancestor` → yes for `develop` and for `main`) |
| Is upstream's tip contained in ours? | **No.** `git merge-base --is-ancestor upstream/develop origin/version-15` → no. (The webshop fork did contain it; this one does not — the branch name is not the base.) |
| `git describe --tags 8e3b5d8e` | `assets-develop-100-g8e3b5d8e`; tags containing it: `v2.61.0`, `v2.62.0`, `v2.62.1` |
| Merged into our branch by | `09ddea15` — "Merge upstream/develop into version-15 (513 commits, 2026-06-05 → 2026-07-29)" |

### Attribution proof

*Measured on `541022e3`, the tip of `version-15` just before this marking pass. The absolute
counts grow with every commit — re-measure them; what must stay true is the **ratio**: every
commit since BASE is ours.*

* `git rev-list 8e3b5d8e..origin/version-15` → **111 commits**.
* `git rev-list origin/version-15 ^8e3b5d8e ^upstream/develop` → **111 commits**, the same set:
  since BASE our branch contains **no upstream commit at all**. Everything after the base is ours.
* Authors of those 111: 93 Jérémy Christillin, 17 `github-actions[bot]` (the commit-the-build
  asset bot), 1 `neoffice-fork-bot` (the marker bot).
* `git log --format=%B 8e3b5d8e..origin/version-15 | grep -c "cherry picked from commit"` → **0**.
  There is **no upstream backport** on this branch; nothing to drop at the merge for that reason.
* Sampled with `git blame` (no `-w`) on unmarked hunks — every sampled line resolves to one of
  those 111 commits (`36c69d63`, `d6d8abd2`, `d3b10e3f`, `d8908dad`, `74ad6ff0`, `7aeaa695`…).
* Files changed BASE..HEAD: **482** (this manifest included), of which **37 are source**; the
  other 445 are skipped by the checker — 438 built SPA files, 5 CI workflows, 1 PO file, and
  this file.
* State of the map after the pass: `check --base 8e3b5d8e --head <tip>` went from **57 unmarked
  hunks to 5** — and those 5 are the build artifacts and the one unreachable hunk listed above,
  each documented here. Marker lines went from **23 in 6 files to 241 in 31 files** (counted
  outside `lms/public/frontend/`, `.github/` and this manifest).

### Not-commentable divergences (JSON, binaries) — the checker reads these paths from here

| Path | What diverges | At the merge |
|---|---|---|
| `lms/lms/doctype/lms_course_offer/lms_course_offer.json` | **Added file, no upstream equivalent** (`d3b10e3f`). Child DocType `LMS Course Offer`, `istable: 1`, three fields: `label` (Data, `reqd`, `in_list_view`, `columns: 4`), `months` (Int, `in_list_view`, `columns: 3`, description "0 means permanent access."), `price` (Currency, `reqd`, `in_list_view`, `columns: 3`). Modelled on `Booking Rate`: one access duration and its price, so one Item sells three months / a year / permanent access instead of one article per duration. | Keep whole. ⚠️ it sits inside upstream's `LMS` module folder, so a future upstream module restructure would move it — check `lms/lms/doctype/` after any merge that touches the module layout. |
| `package.json` | One key: `scripts.build` no longer runs the frontend build unconditionally. Ours short-circuits when `lms/public/frontend/assets` already exists (unless `FORCE_REBUILD=1`) and moves upstream's command to a new `build:force`. Reason: this branch **commits the built SPA** (`cbb59d03`), and client instances (2 vCPU / 4 GB) OOM on `yarn build`; `bench` calls `yarn build` on every app at install. | Keep ours; re-apply the guard on top of whatever upstream's `build` becomes, and keep `build:force` as the escape hatch. |

### Build artifacts — mark the SOURCE, never the artifact

These are committed **outputs**. Any marker written into them is erased by the next build, so
they are deliberately left unmarked; the checker still lists them, which is expected.

| Path | Produced by | Source that carries the marker |
|---|---|---|
| `lms/public/frontend/**` (438 files, +10 353 lines) | `yarn build` in `frontend/`, committed by `.github/workflows/build-and-commit-assets.yml` | `frontend/src/**` (marked) and `.gitignore` (marked: the three ignores upstream has are commented out on purpose) |
| `lms/www/lms.html`, `lms/www/_lms.html` | the same vite build — `frontend/vite.config.js` sets `buildConfig.indexHtmlPath: '../lms/www/_lms.html'` | `frontend/vite.config.js` (marked) and `.gitignore` (marked) |
| `frontend/components.d.ts` | `unplugin-vue-components` regenerates it on every dev run and build ("Generated by unplugin-vue-components" header) | the three components it declares: `NeoCockpitBridge.vue`, `NeoCockpitLMSSidebar.vue`, `SecureVideo.vue` — all three carry an added-file marker |
| `lms/locale/fr.po` (+1 812 / −1 413) | `bench update-po-files` + the translation pass | the source strings in the marked files. PO/MO are skipped by the checker by design (RULE #1bis: PO only, never CSV) |

### Hunks a comment cannot reach

| Location | Why unreachable | Where the marker is |
|---|---|---|
| `frontend/src/pages/Lesson.vue` — the three attributes `:lessonName`, `:videos`, `@video-ended` on `<LessonContent>` | a comment between the attributes of an opening tag is not valid markup | the `<!-- //// Neoffice … -->` block immediately above `<LessonContent` (the checker still reports this hunk: it only looks 3 lines up, and the opening tag is longer than that) |
| `lms/plugins.py` — `src="https://www.youtube-nocookie.com/embed/{video_id}"` | the changed line lives inside an f-string literal | the `#////` block above `return f"""` |
| `lms/lms/utils.py` — `def get_course_outline(course: str = None, …)` | the change is in the signature | the `#////` block above the `@frappe.whitelist` decorator |

### Deliberate non-markings

* `lms/lms/doctype/lms_course_offer/__init__.py` — **empty file** (0 bytes), as Frappe requires for
  a DocType package. Nothing to say, nothing to conflict on; left unmarked on purpose.
* `.github/workflows/**` — skipped by the checker (CI is ours by construction). Four workflows are
  entirely ours (`build-frontend.yml`, `fork-markers.yml`, `tests.yml`, `upstream-preview.yml`) and
  `build-and-commit-assets.yml` is modified; upstream also touched that last one since BASE.

### Custom fields — created in code, not by editing upstream JSON

No upstream DocType JSON is modified on this branch. Everything we add to an upstream doctype is a
**Custom Field created at install and at migrate** (`lms/hooks.py` → `after_install` / `after_migrate`),
which is what keeps the merge surface at zero:

| DocType | Fields | Created by |
|---|---|---|
| `LMS Enrollment` | `neoffice_access_section`, `subscription`, `access_from`, `access_valid_till`, `last_grant_invoice` | `lms.lms.neoffice_video.setup_custom_fields` |
| `Item` | `lms_section`, `lms_course`, `lms_access_months` | `lms.lms.neoffice_commerce.setup_custom_fields` |
| `LMS Course` | `neo_shop_section`, `neo_item`, `neo_offers` | idem |
| `LMS Settings` | `neo_website_section`, `neo_show_on_website`, `neo_video_section`, `neo_vod_channel`, `neo_vod_account`, `neo_vod_token`, `neo_sell_via_shop` | idem |
| `Quotation Item`, `Sales Order Item`, `Sales Invoice Item` | `lms_offer`, `lms_months` | `lms.lms.neoffice_commerce.setup_cart_fields` |

### Merge forecast — the 15 source files touched on BOTH sides since BASE

`upstream/develop` changed 534 files since BASE, we changed 481; the intersection is 16, of which
15 are source (the 16th is `.github/workflows/build-and-commit-assets.yml`).

| File | ours | upstream | Expected |
|---|---|---|---|
| `lms/lms/utils.py` | 25+/8− | 417+/50− | ⚠️ **hardest**. Two of our hunks (`frappe.__version__`) sit on lines upstream still writes as `get_frappe_version()`. Upstream's `from frappe.utils import get_frappe_version` **does not resolve on frappe v15** (our fork only has it in `frappe.pulse.utils`) — taking upstream's import would make the whole module fail to import. Keep ours until the fleet runs v16. |
| `frontend/src/pages/Lesson.vue` | 26+/2− | 257+/133− | ⚠️ upstream rewrote large parts. Re-apply the four secure-video touch points by hand (`<LessonContent>` attributes, the import, `trackVideoWatchDuration`, `onSecureVideoEnded`, the third term of the "has a video" test). |
| `lms/lms/permissions.py` | 10+/1− | 106+/8− | ⚠️ upstream reworked access resolution. Our subscription guard inside `resolve_lesson_access` must be re-applied, including the deliberate absence of a `return` in the lapsed branch (`314d9559`). |
| `frontend/src/components/LessonContent.vue` | 29+/1− | 50+/41− | conflict likely on the block list and the props; keep our `{{ SecureVideo` branch **above** the `{{ Video` branch. |
| `frontend/src/index.css` | 23+/0− | 120+/0− | append-only on both sides; keep both. |
| `lms/hooks.py` | 75+/1− | 11+/1− | keep both — our entries are additions to `after_install`, `after_migrate`, `doc_events` and `jinja.methods`, on doctypes upstream never touches. |
| `frontend/src/utils/index.js` | 11+/1− | 15+/12− | the `secureVideo` editor tool and the `lessonName` option; keep both. |
| `frontend/src/utils/video.ts` | 7+/1− | 8+/5− | two one-liners (a macro name in an alternation, a block type in a test); keep both. |
| `frontend/src/components/CourseCardOverlay.vue` | 38+/2− | 8+/4− | keep both; our shop branch must stay **before** upstream's Billing `router-link`. |
| `frontend/vite.config.js` | 9+/0− | 2+/1− | keep our `build` block (sourcemaps off, `target: esnext`) until nothing but CI builds the SPA. |
| `frontend/src/components/Layouts/DesktopLayout.vue` | 4+/3− | 1+/1− | keep ours (NeoCockpit replaces the LMS sidebar). |
| `frontend/src/pages/Courses/CourseOverview.vue` | 3+/0− | 3+/4− | small, keep both. |
| `lms/plugins.py` | 1+/1− | 1+/1− | different lines; both apply cleanly. |
| `lms/lms/doctype/course_lesson/test_save_progress.py` | 5+/2− | 1+/1− | our `frappe.client_cache` v15 guard; drop it once the fleet is on v16. |
| `frontend/components.d.ts` | generated | generated | regenerate, do not merge. |

**No whitespace-only divergence** was found: no source file's diff against BASE disappears under
`git diff -w --ignore-blank-lines`, so there is nothing to "just take upstream" for formatting.
**No whole-file reformat** either — our largest source diff is 75 added lines (`lms/hooks.py`).
