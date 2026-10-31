# Brand pages

Every image in `docs/img/` (except the app screenshots) is an HTML page here, in the app's own colours and system fonts. The pages load nothing from the network.

| Page | Renders to | Size |
|---|---|---|
| `banner.html` | `docs/img/banner.png` | 1280 × 400 |
| `devto-cover.html` | `docs/img/devto-cover.png` | 1000 × 420 (logo, name and tagline inside the middle 80 %) |
| `social-preview.html` | `docs/img/social-preview.png` | 1280 × 640 (uses `docs/img/morgue.png`) |
| `sweep.html` | `docs/img/sweep.png` | 1200 wide, real `undertaker sweep` output |
| `how-it-works.html` | `docs/img/diagrams/how-it-works.png` | 1600 wide |
| `causes.html` | `docs/img/diagrams/causes.png` | 1600 wide |
| `certificate-checks.html` | `docs/img/diagrams/certificate-checks.png` | 1600 wide |

`brand.css` holds the palette (the same values as `src/undertaker/morgue/static/theme.css`); `diagram.css` the diagram layout. `logo.svg` is the logo; `theme-preview.html` is the original look reference.

## Render

Playwright with the installed Google Chrome (`channel: "chrome"`); every non-`file:` request is aborted. Nothing is installed.

```sh
NODE_PATH=<node_modules> node docs/brand/render.cjs                 # all pages, device scale 1
NODE_PATH=<node_modules> node docs/brand/render.cjs banner sweep    # some pages
NODE_PATH=<node_modules> node docs/brand/render.cjs --scale 2 --out /tmp/check banner   # crispness check
```

`<node_modules>` is a folder that contains the `playwright` package.

## App screenshots

`shoot.cjs` takes `morgue.png` and the four `certificate-*.png` from the running morgue at 1440 wide, device scale 2, page only. Only requests to `http://127.0.0.1:8666` are allowed, and it stops if a certificate isn't Gemma's yet.

```sh
uv run undertaker demo up
uv run undertaker serve --source src/undertaker/demo     # wait until every certificate says "written by gemma4:e4b"
NODE_PATH=<node_modules> node docs/brand/shoot.cjs
uv run undertaker demo down
```
