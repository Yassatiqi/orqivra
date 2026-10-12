# Release Checklist

## Local source and package checks

- Run `python -m unittest discover -s tests -v`, `python -m orqivra.cli --help`, and `npm.cmd test --prefix node` on supported local runtimes.
- Run focused filesystem regressions, shared fixtures, and affected Python/Node state and installation interoperability.
- Exercise the declared Python 3.11 minimum on Windows, including a real junction test. A skipped or unavailable test remains unresolved.
- Build Python wheel/source distributions and the npm tarball. Inspect package inventories and SHA-256 values.
- Install and run each artifact outside the checkout with the other runtime unavailable.
- Review the complete source diff, documentation links, package metadata, and generated archive inventory.
- Record local verification, commit readiness, public repository preparation, and package publication readiness as separate states.

## External publication checklist

- Verify the private vulnerability-reporting route on the public GitHub repository, or provide an approved verified private contact. Do not claim this route is enabled without observing it.
- Observe a real GitHub Actions run; a checked-in workflow or local equivalent is not an Actions result.
- Qualify each supported client by actual discovery and activation using an authorized account and a disposable project.
- Check npm and PyPI package name ownership and publisher account access. A 404 does not reserve a name.
- Review the exact source commit and artifact hashes with the release owner.
- Publish only after a separate explicit authorization. This repository preparation does not publish packages, push commits, create releases, or change repository settings.
