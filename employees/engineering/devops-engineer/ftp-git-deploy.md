# FTP/FTPS git-to-live deploy (folded from the former ftp-deploy gig, 2026-06-14)

Reclassified per Shai: this is a DEPLOY SKILL, not a gig. Methodology preserved here under devops-engineer (which owns deployment). The deploy runs via GitHub Actions (SamKirkland/FTP-Deploy-Action) from GitHub servers - SHA-pin the action per fleet doctrine.

## Skill (verbatim methodology)
---
name: ftp-deploy
description: "Deploy project code from GitHub to a live hosting server via FTP/FTPS. Use this skill whenever Shai says 'deploy to live', 'push to live', 'deploy kellbell', 'deploy to production', 'deploy to server', 'push to hosting', 'FTP deploy', 'go live', or any variation of deploying a project's code to its hosting server. Also trigger when Shai asks to 'set up deployment' or 'configure FTP' for a project, or when discussing version tagging after deployment. This skill handles the full deploy pipeline - pre-deploy checks, FTP sync, version tagging, and post-deploy verification. Only activated on projects where Shai has explicitly requested it. Trigger aggressively on any mention of deploying, going live, pushing to production, or FTP in a project context."
---

# FTP Deploy Skill

Deploy code changes from a GitHub repository to a live server using GitHub Actions with SamKirkland/FTP-Deploy-Action. GitHub Actions runs FTP from GitHub servers, not from Claude container (which cannot make FTP connections).

## Reference Files

| File | Purpose |
|------|---------|
| `references/lessons.md` | Self-updating log of deploy mistakes, hosting quirks, malware patterns, and process improvements. Read at the start of every session. Grows with every deploy. |
| `scripts/generate_deploy.py` | Deploy workflow generator |

**Read `references/lessons.md` BEFORE starting any deploy work.** Past mistakes are in there.

## Self-Learning Protocol (MANDATORY)

After EVERY deploy session (setup, pull, dry-run, live deploy, or troubleshooting):

1. Read `references/lessons.md`
2. Append new entries for:
   - Deploy process mistakes (wrong path, wrong credentials, skipped check)
   - Hosting-specific quirks (SiteGround, cPanel, WP Engine, Cloudways, etc.)
   - Malware or server security patterns encountered
   - New file/directory exclusion needs
   - GitHub Actions configuration gotchas
   - Repo setup mistakes
3. Use the format: specific mistake/discovery → *Rule: what prevents repeat*
4. Report to Shai what was added so he knows the skill evolved

**General, not project-specific.** "SiteGround requires FTPS with loose TLS" is general. "Kellbell FTP root is /home/user/kellbell" is project-specific - that belongs in the project's Handoff, not this skill.

## CRITICAL SAFETY RULES - NON-NEGOTIABLE

These rules exist because mistakes here DELETE LIVE SITES. Every single one is mandatory.

### Rule 1: NEVER ENABLE DEPLOY BEFORE FULL CODEBASE IS IN REPO
SamKirkland FTP-Deploy-Action SYNCS local to remote. If repo has 3 files and server has 3,000, it DELETES 2,997 from the server. Deploy workflow MUST be disabled until full codebase is pulled and verified in the repo.

### Rule 2: DEPLOY WORKFLOW STARTS AS MANUAL ONLY
Every new project deploy.yml uses workflow_dispatch (manual trigger). NEVER use push trigger on a new repo. Only switch to push trigger after full codebase is verified and a dry-run deploy succeeds.

### Rule 3: ALWAYS DRY-RUN FIRST
Before any new deploy config goes live, run with dry-run: true. Review what WOULD be uploaded/deleted. Only proceed if changes look correct. Get explicit approval from Shai.

### Rule 4: VERIFY SERVER PATH BEFORE SETTING IT
Run a directory exploration workflow to LIST the FTP structure. Confirm the exact path. FTP accounts may have different root paths. Never guess. Wrong path = deploying to wrong location = wiping files.

### Rule 5: PULL BEFORE PUSH - ALWAYS
Sequence for every new project:
1. Create repo with deploy DISABLED
2. Explore FTP directory structure
3. Pull codebase FROM server INTO repo
4. Verify codebase is complete (check key dirs, file count)
5. Dry-run deploy
6. Manual deploy with Shai approval
7. THEN enable auto-deploy

### Rule 6: NEVER DEPLOY CREDENTIALS
.env, API keys, database passwords, Stripe keys NEVER go in repo or get deployed.

### Rule 7: EXCLUDE LARGE NON-CODE FILES
Never pull or push: vendor/, node_modules/, storage/, uploaded media (user images/documents), .env, .git/. Check GitHub limits: 5GB soft limit per repo, 100MB hard limit per file. Code-only repos should be under 500MB.

### Rule 8: WHEN IN DOUBT, DON'T DEPLOY. ASK SHAI.

### Rule 9: VERIFY AFTER EVERY DEPLOY
Check the live site loads. Check changed functionality works. If anything breaks, identify the file and revert immediately.

### Rule 10: NEVER RUN BOTH PULL AND DEPLOY WORKFLOWS SIMULTANEOUSLY
Pull workflow commits to repo. If deploy is auto-triggered by that commit, it runs on incomplete data. Deploy must be disabled during pulls.

### Rule 11: SHA-PIN EVERY GITHUB ACTION IN THE WORKFLOW
Never reference a third-party action by a mutable tag (`@v4`, `@master`). A tag can be moved to point at malicious code after you trust it, and these workflows hold live FTP credentials. Pin every action to a full 40-char commit SHA with the human-readable version in a trailing comment, for example:
`uses: SamKirkland/FTP-Deploy-Action@<full-commit-sha>  # v4.x`
`uses: actions/checkout@<full-commit-sha>  # v4`
Look up the SHA for the release tag on GitHub before writing the workflow; refresh it deliberately when bumping versions. This applies to FTP-Deploy-Action, checkout, and any other action used.

---

## Setup Process

### Step 1: Create Private GitHub Repo
ALL client repos MUST be private. No exceptions.

### Step 2: Add Secrets
FTP_SERVER, FTP_USERNAME, FTP_PASSWORD, GH_PAT as GitHub Actions secrets.

### Step 3: Ask Shai for CORRECT FTP credentials
Do not guess. Do not try multiple combinations. Ask once, get the right ones.

### Step 4: Explore FTP Directory
Run exploration workflow to LIST directories. Confirm the app path. Document it.

### Step 5: Pull Codebase
Mirror from server to repo. Exclude vendor, node_modules, .env, storage, uploads.

### Step 6: Verify Completeness
For Laravel: app/, routes/, config/, database/, resources/, composer.json, artisan must exist. File count should be hundreds/thousands.

### Step 7: Dry-Run Deploy
Set dry-run: true. Trigger manually. Review output. Confirm with Shai.

### Step 8: First Real Deploy (Manual)
Remove dry-run. Trigger manually. Verify live site works.

### Step 9: Enable Auto-Deploy
Switch to push trigger with paths-ignore for workflow files and docs.

---

## SiteGround Notes
- Requires FTPS (explicit TLS), not plain FTP
- FTP accounts may have different root paths than main account
- Has CAPTCHA that blocks data center IPs from viewing site
- PHP version managed in Site Tools, not via deploy

## Mistakes Log

Historical deploy mistakes and their preventive rules now live in `references/lessons.md`. Read that file at the start of every session. Append to it at the end of every session per the Self-Learning Protocol above.

---

## Server Cleanup Guide

When onboarding a new project from an existing server, always audit the server for junk before pulling code. Common space wasters on shared hosting:

### Safe to Delete (never needed in GitHub)
- **Backup zip files** (.zip, .tar.gz) - Old manual backups left on the server. SiteGround has its own backup system. These are redundant and often 100MB-500MB each.
- **Staging/temp folders** (kellbell-temp, staging/, temp/, old/) - Delete the ENTIRE folder, not just files inside. These are complete copies of the site used during development and forgotten.
- **Composer cache** (.composer/cache/) - Download cache, rebuilt automatically by composer install.
- **PHP error logs** (php_errorlog, php_files.txt) - Delete the files. PHP recreates them when new errors occur.
- **AWStats/webstats** (webstats/) - Server traffic statistics. Not code. SiteGround regenerates these.
- **Server logs** (logs/*.gz) - Access logs. SiteGround manages these automatically.
- **Old/unused directories** (kell/, old/, backup/) - Check contents first, if empty or clearly unused, delete.
- **Malware symlinks and folders** - Delete BOTH the symlinks in public_html AND the actual malware folders they point to (usually one level up with domain-style names like login.blockchaln.com.sitename/).
- **FTP state files** (.ftp-deploy-sync-state.json) - Created by deploy actions. Delete from server if starting fresh.

### Never Delete
- **source/** or **app/** - The actual application code
- **public_html/.htaccess** - Apache routing config, breaks the site if removed
- **.env** - Application secrets (but never pull into GitHub)
- **vendor/** - Dependencies (don't delete on server, but don't pull to GitHub either. Can be rebuilt with composer install but might break the site if deleted without running composer)
- **storage/app/** - May contain user uploaded files (cleaner photos, documents)
- **database/** - Migration files are code, these DO go to GitHub
- **public/assets/, public/admin/, public/customer/** - Frontend assets the app needs

### Ask Before Deleting
- **storage/app/public/** or **public/uploads/** - May contain user-uploaded content (photos, documents). Check with Shai.
- **public/admin/**, **public/customer/** - Could be static assets or uploaded content
- Any folder you're not sure about - screenshot it and ask

### Identifying Malware
Malware on shared hosting typically appears as:
- Symlinks in public_html pointing to folders with domain-style names (login.blockchain.com, membership-amazon-subscribe.com)
- The actual malware folders live one level above public_html or at the hosting root, named like `malware-domain.sitename.tld/`
- Delete BOTH the symlink AND the source folder
- Check DNS records for unauthorized Amazon SES DKIM entries (attackers use these to send phishing emails from the domain)
- After cleanup: change ALL passwords (FTP, SSH, admin panel, database)

### SiteGround-Specific Cleanup
- SiteGround has automatic daily backups in Site Tools > Security > Backups. Manual zip backups on the server are redundant.
- Server logs at the hosting root (/logs/) are managed by SiteGround and safe to delete
- AWStats at /webstats/ can be viewed in Site Tools > Statistics. The files on disk are redundant.
- The .composer/ folder at root is SiteGround's global composer cache, safe to clear

### Size Estimation Before Pull
Before pulling code to GitHub, estimate what you're getting:
- Laravel app code only (app/, routes/, config/, database/, resources/, bootstrap/, public/): typically 20-100MB
- With compiled assets (public/css/, public/js/): add 5-20MB
- GitHub soft limit: 5GB per repo, hard limit: 100MB per file
- If estimated size exceeds 500MB, something is wrong - likely pulling vendor/, node_modules/, uploads, or backup files
- Always exclude: vendor/, node_modules/, storage/, .env, *.zip, *.gz, *.sql, *.log, files over 100MB



## Lessons (carried over)
# FTP Deploy - Lessons Log

Running log of deployment mistakes, hosting quirks, and learnings. Updated every session something goes wrong or a new pattern is discovered. This file prevents repeat mistakes across projects.

---

## Deployment Process Mistakes

**Deployed near-empty repo to live server**
Deploy auto-triggered on push when repo only had README. SamKirkland FTP-Deploy syncs local to remote - empty repo meant server got wiped to 1 file.
*Rule: Deploy workflow starts DISABLED on every new project. Use workflow_dispatch (manual). Only switch to push trigger after full codebase pulled, verified, and first deploy succeeds.*

**Wrong server-dir path**
Used `public_html/` path when the app was actually at FTP root. Deploy would have uploaded to wrong location.
*Rule: Always run a directory exploration workflow FIRST to LIST the FTP tree. Confirm exact path before setting server-dir. FTP accounts can have different root paths than the main hosting account.*

**Wrong FTP credentials - tried 3 sets before asking**
Wasted session time guessing at FTP username/password combinations.
*Rule: Ask Shai for the exact FTP credentials immediately. Do not guess. Do not try combinations.*

**Tried direct FTP from Claude container**
Container egress proxy only allows HTTP/HTTPS - cannot make FTP connections directly.
*Rule: FTP deployments run via GitHub Actions (SamKirkland/FTP-Deploy-Action) from GitHub's servers. Never attempt direct FTP from Claude container.*

**Recreated existing skill twice instead of configuring it**
Started from scratch when the skill already existed.
*Rule: Check if the skill/workflow already exists before recreating. Modify, don't duplicate.*

**Did not disable deploy during codebase pull**
Risk of deploy auto-triggering on pull commit before full codebase was in repo.
*Rule: Deploy MUST be disabled during pull workflows. Never run pull and deploy simultaneously.*

---

## Hosting-Specific Quirks

**SiteGround requires FTPS (explicit TLS), not plain FTP**
Plain FTP connection fails on SiteGround. FTPS with explicit TLS works.
*Rule: For SiteGround, always set `protocol: ftps` and `security: loose` in the GitHub Action.*

**SiteGround FTP accounts can have different root paths**
A sub-FTP account might chroot into a subdirectory, not the main hosting root.
*Rule: Explore first. Don't assume the FTP login lands in the same place the main cPanel account does.*

**SiteGround has data-center IP CAPTCHA blocking**
GitHub Actions runners can't fetch the site for post-deploy verification because SiteGround serves a CAPTCHA page to known data-center IPs.
*Rule: Post-deploy verification from GitHub Actions is unreliable on SiteGround. Verify manually or from Shai's IP.*

**PHP version managed in SiteGround Site Tools, not via deploy**
Changing PHP version requires dashboard action, not a file push.
*Rule: PHP version upgrades are manual in Site Tools. Note as a pre-deploy checklist item if upgrade is needed.*

---

## Malware & Server Security Patterns

**Phishing malware on Kellbell server (April 2026)**
Symlinks in public_html pointing to folders with domain-style names (login.blockchain.com, membership-amazon-subscribe.com). Actual malware folders lived one level above public_html at the hosting root.
*Rule: When onboarding a server with suspected malware: (1) delete BOTH symlinks AND source folders, (2) check DNS records for unauthorized Amazon SES DKIM entries (used for phishing email), (3) change ALL passwords - FTP, SSH, admin panel, database - after cleanup.*

**Server junk wastes space on shared hosting**
Backup zips, staging folders, composer cache, PHP error logs, AWStats, server logs - all redundant on SiteGround (which has its own backup/logging systems) and all take space.
*Rule: Audit the server before pulling code. Delete entire redundant folders (not just files inside). See "Server Cleanup Guide" in SKILL.md for the full safe-to-delete list.*

---

## Repo & GitHub Mistakes

**Pulled vendor/ or node_modules/ into repo**
Pushed the repo over GitHub's 100MB-per-file or 5GB-per-repo limits.
*Rule: Always exclude vendor/, node_modules/, storage/, .env, *.zip, *.gz, *.sql, *.log, and files over 100MB during pull. Code-only repos should stay under 500MB.*

**Deployed .env with credentials**
.env with DB password, API keys pushed to repo.
*Rule: .env NEVER goes in repo. .gitignore MUST include .env before first commit. If .env ever got committed, rotate every credential it contained.*

**Public repo for client project**
Client code in a public GitHub repo.
*Rule: ALL client repos MUST be private. No exceptions. Set visibility at repo creation, verify before first push.*

---

## Process Improvements Made

- Deploy workflow always starts as workflow_dispatch (manual) on new projects
- Dry-run mandatory before first real deploy
- Pre-deploy checklist: disable deploy → explore FTP → pull → verify completeness → dry-run → manual deploy → enable auto-deploy
- Server cleanup audit added as standard pre-pull step for onboarding existing servers
- Malware cleanup playbook documented (symlinks + source folders + DNS + password rotation)

---

*Add new entries above this line after each deploy session. Date them. State the rule that prevents repeat.*
