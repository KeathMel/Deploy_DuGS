# Setting this up: GitHub + auto-built container

## 0. What's in this zip

```
backend/                                 <- the whole API, container-ready
.github/workflows/build-and-publish-api.yml   <- the "auto setup" part
```

Both go at the **root** of your `DuGS` repo, as siblings — `backend/` next to
`ui.py`, `theme.py`, etc, and `.github/` next to `backend/`. GitHub only
looks for workflows in `.github/workflows/` at the repo root, so this can't
live inside `backend/`.

## 1. Drop it into your repo and push

From inside your local clone of `KeathMel/DuGS`:

```bash
# unzip so backend/ and .github/ land at the repo root
unzip -o dugs-repo-addon.zip -d .

git add backend .github
git commit -m "Split API into backend/, add container + auto-build"
git push
```

That's it — the push itself is what triggers step 2.

## 2. What happens automatically after that push

GitHub Actions picks up `.github/workflows/build-and-publish-api.yml` and,
on every push that touches `backend/`:

1. Builds the Docker image from `backend/`.
2. Publishes it to **GitHub Container Registry** (ghcr.io) — free, and
   already authenticated with your repo, no secrets to create.
3. Tags it two ways: `:latest` (always the newest) and `:<commit-sha>`
   (a permanent, pinned version of that exact push).

You can watch it run under the **Actions** tab of your repo. First run
takes a couple minutes; after that, Docker's layer caching (`cache-from`/
`cache-to` in the workflow) makes it much faster.

Once it's finished, your image lives at:

```
ghcr.io/keathmel/dugs/dugs-api:latest
```

## 3. Make the package public (one-time, optional but recommended)

By default, a freshly published GHCR package is **private** — pulling it
elsewhere would need a login. To make it pullable with no auth:

Repo → **Packages** (right sidebar) → click **dugs-api** → **Package settings**
→ **Change visibility** → **Public**.

## 4. Run it — anywhere, no build step needed anymore

Once it's published, running the API is just:

```bash
docker run -d -p 5800:5800 -v dugs_data:/data --name dugs-api \
  ghcr.io/keathmel/dugs/dugs-api:latest
```

No git clone, no Docker build, no Python install — just that one command,
on any machine with Docker. That's the payoff of the auto-build: every push
becomes a ready-to-run image without you ever running `docker build`
yourself again.

## 5. Point the desktop UI at it

```bash
DUGS_API_URL=http://your-server:5800 python3 ui.py
```

(or `http://localhost:5800` if it's running on the same machine)

## Still fully offline-capable

None of this requires the internet to *use* day-to-day — only the initial
`docker pull`/`git push`/Action run touches the network. After the image is
pulled once, `docker run` and everything the UI/API do together works with
zero internet, same as running `python3 api.py` directly always has.
