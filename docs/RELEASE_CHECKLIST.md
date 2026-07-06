# NovelClaw — Release Checklist

## Pre-Release

- [ ] `python tools/check_all.py` — all checks pass
- [ ] `python tools/validate_data.py --all` — all data valid
- [ ] Reader starts: `cd reader && npm start` → localhost:4173
- [ ] Home page loads with novels
- [ ] Reader page loads chapter content
- [ ] Admin dashboard accessible
- [ ] `novelctl status` shows correct data
- [ ] `novelctl report` generates summary
- [ ] No test novels visible in reader UI (slug prefix check: test-, fixture-, tmp-)

## Schema & Data

- [ ] All `novels/*/chapters/*.json` pass schema validation
- [ ] `novels/*/novel.json` has valid metadata
- [ ] `novels/*/chapters.json` index is in sync with actual files
- [ ] Search index is built: `python tools/novelctl.py --slug <name> rebuild`

## Backup

- [ ] Backup created: `python tools/novelctl.py --slug <name> backup` (if implemented)
- [ ] Archive `novels/`, `jobs/`, `logs/` for external backup

## Release

- [ ] Version tag created: `git tag stable-<name>-v<X>`
- [ ] Tag pushed: `git push origin stable-<name>-v<X>`
- [ ] Release notes written in GitHub Releases
- [ ] Rollback plan documented

## Quick Rollback

```bash
# From backup archive
tar -xzf backup-<date>-v<X>.tar.gz
cp -r backup/novels/* novels/
cp -r backup/jobs/* jobs/
cp -r backup/logs/* logs/
```
