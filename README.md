# scoop-puppet

scoop bucket for [puppet](https://github.com/romirr/puppet): your agents drive your real chrome.

```powershell
scoop bucket add puppet https://github.com/romirr/scoop-puppet
scoop install puppet
puppet install    # extension + native host, once
puppet doctor
```

`bucket/puppet.json` follows the latest github release: a workflow in this repo re-renders it every 6 hours from the release's `SHA256SUMS` (`render.py`). apache-2.0.
