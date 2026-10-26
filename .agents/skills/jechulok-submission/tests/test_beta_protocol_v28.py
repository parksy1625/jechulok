"""v2.8 beta-study planning, no identifiers, no writes and no false claims."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import beta_protocol_v28 as beta


class BetaProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.before = self.root / "before.json"
        self.after = self.root / "after.json"
        self.sentinel = self.root / "confidential-notice.pdf"
        self.sentinel.write_bytes(b"do not access or replace")

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, cohort="baseline", **changes):
        result = beta.template(cohort)
        result.update({item: True for item in beta.CHECKS})
        result.update(changes)
        return result

    @staticmethod
    def write(path, obj):
        path.write_text(json.dumps(obj), encoding="utf-8")

    def test_preview_has_five_identical_stage_ids_in_both_languages(self):
        ko = beta.protocol("ko")
        en = beta.protocol("en")
        self.assertEqual(ko["status"], "protocol_preview_only")
        self.assertEqual(len(ko["tasks"]), 5)
        self.assertEqual([x["stage"] for x in ko["tasks"]],
                         [x["stage"] for x in en["tasks"]])
        self.assertFalse(ko["participants_contacted"])
        self.assertFalse(ko["real_study_performed"])

    def test_template_starts_with_unchecked_attestations(self):
        result = beta.template()
        self.assertTrue(all(result[x] is False for x in beta.CHECKS))
        self.assertEqual(result["cohort"], "baseline")
        self.assertEqual(len(result), len(beta.KEYS))

    def test_default_unchecked_manifest_is_hold(self):
        self.write(self.before, beta.template())
        report = beta.audit(self.before)
        self.assertEqual(report["status"], "hold_for_manual_review")
        self.assertEqual(set(report["incomplete_checklist_items"]), set(beta.CHECKS))

    def test_all_checked_does_not_claim_verified_consent(self):
        self.write(self.before, self.manifest())
        report = beta.audit(self.before)
        self.assertEqual(report["status"], "self_attested_checklist_complete")
        self.assertFalse(report["consent_independently_verified"])
        self.assertFalse(report["real_study_performed"])
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_rejects_free_text_extra_fields_and_identifiers(self):
        for extra in ("name", "email", "session_id", "comment", "file_path"):
            with self.subTest(extra=extra):
                invalid = {**self.manifest(), extra: "private@example.com"}
                with self.assertRaises(ValueError):
                    beta.check_manifest(invalid)

    def test_boolean_attestations_must_be_real_booleans(self):
        with self.assertRaises(ValueError):
            beta.check_manifest(self.manifest(consent_notice_presented="yes"))
        with self.assertRaises(ValueError):
            beta.check_manifest(self.manifest(identifiers_excluded=1))

    def test_fixed_protocol_and_recruitment_choices_only(self):
        for item in (
            self.manifest(task_set="custom-user-name"),
            self.manifest(recruitment="someone@example.com"),
            self.manifest(moderation="record_full_screen"),
            self.manifest(questionnaire="ask_for_personal_details"),
        ):
            with self.assertRaises(ValueError):
                beta.check_manifest(item)

    def test_refuses_missing_and_oversized_manifest(self):
        with self.assertRaises(ValueError):
            beta.read_manifest(self.root / "missing.json")
        self.before.write_bytes(b"x" * 4096)
        with self.assertRaises(ValueError):
            beta.read_manifest(self.before)

    def test_refuses_symlink_and_nonregular_file(self):
        marker = self.root / "source.json"
        self.write(marker, self.manifest())
        try:
            self.before.symlink_to(marker)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(ValueError):
            beta.read_manifest(self.before)
        self.before.unlink()
        self.before.mkdir()
        with self.assertRaises(ValueError):
            beta.read_manifest(self.before)

    def test_malformed_json_is_rejected_without_echo(self):
        self.before.write_text('{"email":"private@example.com"}', encoding="utf-8")
        with self.assertRaises(ValueError) as error:
            beta.read_manifest(self.before)
        self.assertNotIn("private@example.com", str(error.exception))

    def test_duplicate_json_keys_are_rejected(self):
        content = json.dumps(self.manifest())
        self.before.write_text(content[:-1] + ',"cohort":"current"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            beta.read_manifest(self.before)

    def test_non_json_extension_is_rejected(self):
        path = self.root / "not-a-manifest.pdf"
        path.write_bytes(b"private data marker")
        with self.assertRaises(ValueError):
            beta.read_manifest(path)

    def test_matching_manifests_only_self_attested(self):
        self.write(self.before, self.manifest("baseline"))
        self.write(self.after, self.manifest("current"))
        report = beta.compare_preflight(self.before, self.after)
        self.assertEqual(report["status"], "self_attested_protocols_match")
        self.assertFalse(report["participants_and_collection_comparable_verified"])
        self.assertFalse(report["product_improvement_measured"])

    def test_mismatched_recruitment_blocks_comparison(self):
        self.write(self.before, self.manifest("baseline"))
        self.write(self.after, self.manifest("current", recruitment="open_volunteers"))
        report = beta.compare_preflight(self.before, self.after)
        self.assertEqual(report["status"], "hold_for_manual_review")
        self.assertFalse(report["task_and_recruitment_settings_match"])

    def test_wrong_cohort_roles_block_comparison(self):
        self.write(self.before, self.manifest("current"))
        self.write(self.after, self.manifest("baseline"))
        self.assertFalse(beta.compare_preflight(self.before, self.after)["roles_correct"])

    def test_unchecked_attestation_blocks_comparison(self):
        self.write(self.before, self.manifest("baseline"))
        self.write(self.after, self.manifest("current", feedback_optional=False))
        report = beta.compare_preflight(self.before, self.after)
        self.assertEqual(report["status"], "hold_for_manual_review")
        self.assertFalse(report["self_attested_checklists_complete"])

    def test_same_manifest_is_rejected(self):
        self.write(self.before, self.manifest())
        with self.assertRaises(ValueError):
            beta.compare_preflight(self.before, self.before)

    def test_cli_error_hides_private_path(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = beta.main(["audit", "--manifest", str(self.root / "missing.json")])
        self.assertEqual(code, 1)
        self.assertNotIn(str(self.root), stream.getvalue())

    def test_read_only_existing_files_untouched(self):
        self.write(self.before, self.manifest())
        original = self.before.read_bytes()
        beta.audit(self.before)
        beta.protocol()
        beta.template()
        self.assertEqual(self.before.read_bytes(), original)
        self.assertEqual(self.sentinel.read_bytes(), b"do not access or replace")


if __name__ == "__main__":
    unittest.main()
