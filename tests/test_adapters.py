from __future__ import annotations

import unittest

from orqivra.adapters.generic import normalize_project as normalize_generic
from orqivra.adapters.mip import normalize_project as normalize_mip
from orqivra.adapters.mip import resolve_obligation


class AdapterTests(unittest.TestCase):
    def test_generic_adapter_does_not_add_mip_policy(self) -> None:
        project = {"id": "sample", "kind": "project"}

        normalized = normalize_generic(project)

        self.assertEqual(normalized["adapter"], "generic")
        self.assertEqual(normalized["obligations"], [])
        self.assertNotIn("adapter", project)

    def test_mip_adapter_defers_obligations_without_mutating_input(self) -> None:
        project = {
            "id": "mip-sample",
            "adapter": "mip",
            "obligations": [{"id": "external-check", "description": "Run external validation."}],
        }

        normalized = normalize_mip(project)

        self.assertEqual(normalized["obligations"][0]["status"], "DEFERRED_EXTERNAL")
        self.assertEqual(normalized["obligations"][0]["evidence"], [])
        self.assertNotIn("status", project["obligations"][0])
        self.assertNotIn("evidence", project["obligations"][0])

    def test_mip_obligation_requires_final_sprint_observation_and_evidence(self) -> None:
        obligation = {"id": "external-check", "status": "DEFERRED_EXTERNAL", "evidence": []}

        cases = (
            (False, True, ["e1"]),
            (True, False, ["e1"]),
            (True, True, []),
        )
        for final_sprint, observed, evidence in cases:
            with self.subTest(final_sprint=final_sprint, observed=observed, evidence=evidence):
                resolved = resolve_obligation(
                    obligation,
                    final_validation_sprint=final_sprint,
                    external_validation_observed=observed,
                    evidence_ids=evidence,
                )
                self.assertEqual(resolved["status"], "DEFERRED_EXTERNAL")

        verified = resolve_obligation(
            obligation,
            final_validation_sprint=True,
            external_validation_observed=True,
            evidence_ids=["e2", "e1", "e2"],
        )
        self.assertEqual(verified["status"], "VERIFIED")
        self.assertEqual(verified["evidence"], ["e1", "e2"])


if __name__ == "__main__":
    unittest.main()
