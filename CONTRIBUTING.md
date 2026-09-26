# Contributing

Contributions are welcome, especially fixes for existing adapters and adapters
for public file hosts with a stable, verifiable download flow.

## Development setup

```powershell
python -m pip install -e ".[browser]"
python -m unittest discover -s tests -v
```

Keep each host-specific flow inside `linkfetch/resolvers`. The shared downloader
should receive a final URL, optional file name, and only the headers required by
that transfer.

Please include focused tests for parsing and failure handling. Never commit live
credentials, authentication tokens, copyrighted files, or a catalog of hosted
content. CAPTCHA solving and verification bypasses are outside the project scope.
