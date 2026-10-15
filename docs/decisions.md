# Decisions, 9 October 2026

Four questions were left open in `docs/v1-roadmap.md` §7. They are decided
here, each with the reason, what it costs, and what changing it later would
take. The last section is the setup that only the owner of the accounts can
do; everything before it is built.

---

## 1. Hosting: Vercel, with Neon Postgres and a private Vercel Blob store

**Decided.** The control plane runs as its own Vercel project whose root
directory is `api/`: FastAPI on Vercel's Python runtime, Postgres on Neon
through the Vercel Marketplace, artifacts in a private Vercel Blob store. The
website stays where it is, in the `faultline` project. `api/Dockerfile`
remains for self-hosting and for any container host.

**Why.**

- One vendor and one bill. The website is already on Vercel; Neon and Blob
  are created from the same dashboard and arrive as environment variables
  (`DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`), which the API reads as they are.
- The control plane is light. It stores records and hands out jobs; the
  simulation runs on the customer's runner. A function that scales to zero
  fits a company with no customers yet.
- Every branch gets a preview deployment, as the website does now.

**What it costs.**

- Long-polling would hold a function instance open while it waits. On Vercel
  a runner's claim returns at once and asks the runner to come back in ten
  seconds (`Retry-After`). Measured in a local rehearsal of the Vercel
  settings: one empty claim every 9 s or so while idle, and a CI gate on the
  demo program still finished in 27 s.
- Requests to Vercel functions have a body-size limit (4.5 MB, not verified in
  this session). Today's artifacts are far below it: about 170 KB for a replay
  and 12 KB for a trace (measured). Larger archives, in M4, would upload
  straight to Blob with signed URLs.
- Vercel describes its free Hobby plan as for personal use (not verified in
  this session against the current terms). A company's product should be on
  Pro; check the plan before the first design partner signs in.

**Changing it later.** Run the Docker image anywhere and point it at the same
Neon database. Moving artifacts off Blob means writing an S3 backend for
`api/teeter_api/storage.py`, about a hundred lines beside the Blob one.

---

## 2. Sign-in: WorkOS AuthKit

**Decided.** WorkOS AuthKit, as the product plan proposed. It is built
(`api/teeter_api/routes/auth_workos.py`) and tested against a mocked WorkOS;
this session could not reach WorkOS itself. It switches on when
`WORKOS_CLIENT_ID` and `WORKOS_API_KEY` are set, and until then sign-in is by
one-time link, as in v0.

**Why.** The customers are robotics companies with security teams, and the
first thing such a team asks about sign-in is SAML single sign-on and
directory sync. WorkOS is built for that, and AuthKit gives the sign-in pages
without our having to build them. Clerk would be quicker to style, but its
centre of gravity is consumer apps.

**How it behaves.**

- AuthKit proves who someone is; this server decides whether they come in.
  Only an address a workspace has invited is let in, with the role it was
  given (`POST /v1/members`, or `teeter-api member --email … --role …`).
- Roles are enforced: a viewer reads everything in the workspace and is
  refused every change.
- A browser session lasts thirty days. The OAuth state is signed and bound to
  a cookie, so a callback this browser did not start is refused.

**Changing it later.** Sign-in ends by minting the same workspace token every
other path mints. Another provider is another pair of endpoints.

---

## 3. Simulator: MuJoCo first

**Decided.** MuJoCo stays the only simulator through v1. A design partner
whose policy was trained in Isaac Lab is served by testing that policy in
MuJoCo: the checkpoint exported to ONNX, its observation layout declared
(`harness/faultline/observe.py`), the robot as MJCF. An Isaac Lab runner is
built when a partner needs results in Isaac's own physics, which is M6.

**Why.**

- The engine, the published record and every test run on MuJoCo 3.12.0,
  pinned exactly because contact solvers change between versions. A second
  simulator doubles what evidence has to be reproducible on.
- Isaac Lab needs an NVIDIA GPU. The runner would stop running on a laptop or
  a plain CI machine, which is how v0's runner is used.
- Running a policy in a simulator other than the one it was trained in is
  already a step many robotics teams take before hardware, so a finding in
  MuJoCo is useful to them, provided it is reported as MuJoCo's.

**What it costs.** A partner who trusts only Isaac's physics will discount a
MuJoCo finding. That partner is the trigger for M6.

**Changing it later.** The runner already resolves robots and policies by
name and speaks versioned contracts; an Isaac runner is another backend
behind the same `execute` step, not a new protocol.

---

## 4. The older pages: retired

**Decided.** Retired, not updated. The pages drawn in the previous identity
(`faultline.html`, `atlas/`, `surreal/`, `next/`, `archive/`, `start/`,
`configure/`, `report/`, `ink/`, `app/`, `v1/`–`v3/`) are no longer deployed
(`.vercelignore`), and their addresses redirect to the Teeter front page, the
old `app/` to the Teeter app (`vercel.json`). Checked on a preview deployment.

**Why.** Several quote numbers by hand that the fixed engine no longer
produces, such as the two-mode result and the 2.7–5.5% uniform interval.
Updating them would mean keeping a second site, in a withdrawn identity, in
step with the record.

**Not deleted.** They are still in the repository, for reference. Removing
them needs the owner's go-ahead; this session's permissions blocked a bulk
delete. Their last deployed state is commit `5fc47c5`.

---

## The setup only the account owner can do

This session's Vercel connection can read projects but not create them, nor
create sandboxes or stores, and its network cannot reach Neon or WorkOS. So
the hosted control plane is built, configured and rehearsed, but not
provisioned. These steps provision it.

1. **Create the project.** In Vercel: Add New → Project → import
   `Davuddevelop/Faultline`. Set the root directory to `api` and the framework
   to FastAPI if it is not detected from `api/pyproject.toml`. Make sure
   "Include files outside the root directory" is on: the build copies
   `teeter/` in from beside it. The first
   build stops with "production needs DATABASE_URL". That is intended: it
   refuses to deploy without a database.
2. **Add the database.** Project → Storage → Neon (Postgres) → connect it to
   Production. If the integration offers a database branch per preview, take
   it; otherwise leave Preview unconnected, so previews never touch
   production data.
3. **Add artifact storage.** Storage → Blob → **private** → connect it.
4. **Add two variables** (Settings → Environment Variables, Production):
   `TEETER_SECRET`, at least 32 random characters (`python3 -c "import
   secrets; print(secrets.token_urlsafe(32))"`), and `TEETER_DEMO_WORKSPACE`
   = `demo` for the read-only demo on the sign-in page.
5. **Redeploy.** The production build migrates the database
   (`api/vercel_build.py`).
6. **Make the demo workspace and a runner token.** From a checkout, with the
   production `DATABASE_URL` in the environment (from `vercel env pull`, or
   copied from the Neon console if Vercel will not show it):
   `TEETER_PUBLIC_URL=https://<your project>.vercel.app teeter-api demo`. It
   prints a sign-in link and writes runner and CI tokens to `.teeter/`.
7. **Run a runner** on any machine:
   `teeter runner start --api https://<your project>.vercel.app --token-file
   .teeter/runner-token --config runner/demo-runner.yaml`, then gate a
   checkpoint: `teeter gate --api https://<your project>.vercel.app
   --token-file .teeter/ci-token --program quadruped --checkpoint tall-v2`.
8. **WorkOS, when wanted.** Create a WorkOS account, turn on AuthKit, add the
   redirect URI `https://<your project>.vercel.app/v1/auth/workos/callback`,
   and set `WORKOS_CLIENT_ID` and `WORKOS_API_KEY`. Invite yourself first:
   `teeter-api member --email <your address> --role owner`.

Steps 6 and 7 were rehearsed locally with Vercel's settings (a fresh Postgres
reached through a `postgres://` URL, migrated by the build script, served
through the same entrypoint), and the gate blocked `tall-v2` with the same
widened push as everywhere else, 7.875 → 6.89 N·s requested.

Two more things only the owner can do: register the package names
`faultline-harness`, `teeter-api` and `teeter-runner` on PyPI before anyone
else does, and connect the Neon, Sentry and Railway connectors in Claude if
this work should be operated from a session next time.
