# Release Checklist

## Local source and package checks

- Run `python -m unittest discover -s tests -v`, `python -m orqivra.cli --help`, and `npm.cmd test --prefix node` on supported local runtimes.
- Run `node tools/generate-online-context.mjs --check` and `python -m unittest tests.test_online_context -v` after orchestration-method changes. Exercise `config validate` and `config show` regressions in both runtimes.
- Run focused filesystem regressions, shared fixtures, and affected Python/Node state and installation interoperability.
- Exercise the declared Python 3.11 minimum on Windows, including a real junction test. A skipped or unavailable test remains unresolved.
- In the Windows Python 3.11 CI job, run `python scripts/verify_windows_python311_junctions.py`; this release gate must execute both required junction regressions with zero skips. The ordinary cross-platform suite may retain its Windows-only test skip on Linux.
- Build Python wheel/source distributions and the npm tarball. Inspect that schemas, defaults, model catalog, profiles, contracts, and skills appear in each applicable package; record package inventories and SHA-256 values.
- Install and run each artifact outside the checkout with the other runtime unavailable.
- Review the complete source diff, documentation links, package metadata, and generated archive inventory.
- Record local verification, local commit readiness, public repository preparation, and package publication readiness as separate states. A checked-in or queued workflow remains `NOT_RUN` until an actual GitHub Actions run is observed.

## External publication checklist

- Verify the private vulnerability-reporting route on the public GitHub repository, or provide an approved verified private contact. Do not claim this route is enabled without observing it.
- Observe a real GitHub Actions run; a checked-in workflow or local equivalent is not an Actions result.
- Qualify each supported client by actual discovery and activation using an authorized account and a disposable project.
- Verify preview/client model access separately from API documentation. Gemini CLI owns automatic routing and fallback, and Claude Code may apply native fallback; ORQIVRA's own `fallback.policy: none` does not disable client behavior. Gemini 3.8 Flash CLI qualification remains unresolved until supported client documentation or actual CLI execution establishes it.
- Check npm and PyPI package name ownership and publisher account access. A 404 does not reserve a name.
- Review the exact source commit and artifact hashes with the release owner.
- Publish only after a separate explicit authorization. This repository preparation does not publish packages, push commits, create releases, or change repository settings.
