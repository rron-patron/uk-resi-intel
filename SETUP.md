# Setup

About 15 minutes end to end. Do the Anthropic part first — you need the key
before the GitHub part will do anything useful.

Replace `YOUR-USERNAME` with your GitHub username throughout.

---

## Part 1 — Anthropic (5 minutes)

### 1.1 Create an account and an organisation

Go to **[platform.claude.com](https://platform.claude.com)** and sign up or log
in. This is the developer console, and it is a separate thing from a Claude Pro
subscription on claude.ai — a Pro plan does **not** give you API access, and API
credit does not give you Pro. You need the console.

### 1.2 Add credit

**Billing** in the left sidebar → **Add credit**. The minimum is $5, which at
this project's usage is roughly six weeks of daily briefings.

While you are on that page, set a spend cap so a bug can never surprise you:

- **Billing → Usage limits** → set a monthly limit of $10
- Turn on the email alert at 50%

### 1.3 Create an API key

**API keys** in the left sidebar → **Create key**.

- Name it `uk-resi-intel` so you can revoke it in isolation later
- Copy it immediately — the console will never show it again
- It starts `sk-ant-api03-...`

Keep the tab open, or paste it somewhere temporary. You need it in step 2.4.

> **Never commit this key.** If it ends up in a commit, revoke it in the console
> straight away and create a new one. Rotating the key is a 30-second job;
> cleaning a key out of git history is not.

### 1.4 Optional: check the model is available to you

**Workbench** → pick `claude-sonnet-5` from the model dropdown → send anything.
If it answers, the model string in this project's default config is valid for
your account. If the model is missing, use whatever current Sonnet or Opus model
is listed and set `ANTHROPIC_MODEL` accordingly in step 2.7.

---

## Part 2 — GitHub (10 minutes)

### 2.1 Create the repository

On GitHub, **New repository**:

- **Name:** `uk-resi-intel`
- **Visibility:** **Public**. On a free account GitHub Pages only serves from
  public repositories, and Actions minutes are unlimited for public repos.
  Private works on a paid plan.
- Do **not** add a README, `.gitignore` or licence — this project already has them

### 2.2 Push the code

From the project folder on your machine:

```bash
cd uk-resi-intel
git init
git add .
git commit -m "UK residential property intelligence dashboard"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/uk-resi-intel.git
git push -u origin main
```

### 2.3 Point the project at your own repository

Three files carry the placeholder `YOUR-USERNAME`. Fix them now so links and
the User-Agent are correct:

```bash
grep -rl "YOUR-USERNAME" . --exclude-dir=.git
```

Edit each:

- `docs/assets/app.js` — the `REPO` constant at the top
- `src/uk_resi/config.py` — the `USER_AGENT` default
- `README.md` — the live site URL

Then regenerate the placeholder page and push:

```bash
export PYTHONPATH=src
python scripts/make_seed.py
git commit -am "Point at my repository"
git push
```

### 2.4 Add the API key as a secret

In the repository: **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**.

- **Name:** `ANTHROPIC_API_KEY` — exactly this, it is case-sensitive
- **Secret:** paste the key from step 1.3

Secrets are write-only. You will not be able to read it back, only replace it.

### 2.5 Give the workflow permission to commit

**Settings** → **Actions** → **General** → scroll to **Workflow permissions**:

- Select **Read and write permissions**
- **Save**

Without this the daily run cannot commit the day's data back to the repository,
and the job fails at the push step with a 403.

### 2.6 Turn on GitHub Pages

**Settings** → **Pages** → under **Build and deployment**:

- **Source:** **GitHub Actions**

Not "Deploy from a branch". This project deploys with
`actions/upload-pages-artifact` and `actions/deploy-pages`, which needs the
Actions source. Selecting the branch option will serve a stale copy and ignore
your workflow.

### 2.7 Optional: override the model

Only if you want something other than the default. **Settings** → **Secrets and
variables** → **Actions** → **Variables** tab → **New repository variable**:

| Name | Example | Effect |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Cheaper, faster, less nuanced |
| `UK_RESI_MAX_ARTICLES` | `40` | Fewer items to the model, lower cost |

If you set `ANTHROPIC_MODEL` as a variable, also delete the hardcoded default in
the `env:` block of `.github/workflows/daily.yml`, or the workflow value will win.

### 2.8 Check which sources actually work

**Do this before trusting the first edition.** Feed URLs drift, and several in
this project are researched best guesses rather than confirmed endpoints.

Locally:

```bash
export PYTHONPATH=src
python -m uk_resi.cli verify
```

Or on GitHub: **Actions** → **Source health** → **Run workflow**. The result
appears in the run's summary.

You will get a per-source report ending with a count. Anything listed under
`No items from:` needs attention — see [SOURCES.md](SOURCES.md) for how to fix
it. Six or seven of nine working is a normal starting point; the paywalled
titles are the usual failures.

### 2.9 Publish the first edition

**Actions** → **Daily briefing** → **Run workflow**:

- Leave **force** ticked — it bypasses the "already published today" gate
- Leave **offline** unticked so the AI step runs

Watch the run. It takes 2–4 minutes. Expect two jobs: *Collect, analyse and
build*, then *Deploy to GitHub Pages*.

The run summary shows the story count, the sentiment reading, token usage and a
per-source table. If a step failed, jump to Troubleshooting below.

### 2.10 Confirm the site is live

`https://YOUR-USERNAME.github.io/uk-resi-intel/`

The first deployment can take a couple of minutes to propagate. You should see a
real edition with the day's date — not the "Placeholder edition" banner. If you
still see the placeholder, the deploy job ran but the build job was gated out;
re-run with **force** ticked.

### 2.11 Confirm the schedule

Nothing more to configure — the cron is in the workflow. Tomorrow at 09:00
London time a new edition should appear on its own.

The workflow fires at 08:00, 09:00 and 10:30 UTC and gates on London local time,
so it lands at 09:00 in both BST and GMT. Weekdays only. To change the hour,
edit `--hour 9` in the gate step of `.github/workflows/daily.yml` and move the
cron entries to match.

---

## Verification checklist

Work down this list; each line is something you can see.

- [ ] `ANTHROPIC_API_KEY` appears under Settings → Secrets and variables → Actions
- [ ] Workflow permissions are set to **Read and write**
- [ ] Pages source is **GitHub Actions**
- [ ] `python -m uk_resi.cli verify` reports at least five live sources
- [ ] A manual **Daily briefing** run finishes green, both jobs
- [ ] The run summary shows a non-zero story count and a token count
- [ ] The live URL shows today's date, with no placeholder banner
- [ ] `data/raw/` and `data/analysis/` contain a file for today
- [ ] `docs/data/archive/` contains a file for today
- [ ] The next weekday, a new edition appears without you doing anything

---

## Troubleshooting

**Workflow fails at "Commit the day's data" with `403` or `permission denied`**
Step 2.5 was missed. Set workflow permissions to Read and write.

**Workflow fails at "Analyse with Claude" with `ANTHROPIC_API_KEY is not set`**
The secret name is wrong. It must be exactly `ANTHROPIC_API_KEY`. Check for a
trailing space in the name.

**Analysis step reports `authentication_error` or `401`**
The key is invalid or revoked. Create a new one in the console and replace the
secret.

**Analysis step reports `credit balance is too low`**
Add credit in the console. The run will still publish a degraded edition.

**The page shows "Degraded edition"**
Collection worked but analysis did not. The reason is printed in the banner and
in the run log. The most common causes are no credit, a bad key, or an API
outage. Re-run the workflow with **force** once fixed.

**The page shows "Placeholder edition"**
No successful run has happened yet, or the gate skipped it. Run manually with
**force** ticked.

**Story count is zero or very low**
Sources are failing. Run `verify` and fix them per SOURCES.md. Note the
collector only reports items published in the last 48 hours that it has not seen
before, so a Monday run after a quiet weekend is legitimately thin — the
analysis step pools the last three days when a day brings fewer than eight new
items.

**Editions stopped appearing after a few weeks**
GitHub disabled the cron for inactivity. Open the Actions tab; there will be a
banner with a button to re-enable. Push any commit to reset the 60-day clock.

**The scheduled run did not fire at 09:00**
GitHub's shared scheduler is best-effort and often runs late. That is why there
is a 10:30 UTC safety net. If nothing ran all day, check the Actions tab for a
disabled-workflow banner.

**Site returns 404**
Pages source is probably still set to a branch. Set it to GitHub Actions and
re-run. Also confirm the deploy job actually ran — it is skipped when the build
job is gated out.

**Local preview shows "Could not load data/dashboard.json"**
You opened the file from disk. `fetch` does not work on `file://`. Run
`python -m http.server --directory docs 8000` and use `http://localhost:8000`.
