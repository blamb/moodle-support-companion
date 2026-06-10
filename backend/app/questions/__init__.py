"""Question import — parse messy instructor questions into Moodle-importable formats.

This package powers the "Import" tab of the Companion. It turns the questions
instructors paste (often in inconsistent or malformed formats) into validated
Moodle question files: GIFT, Moodle XML, and Aiken.

Two parsing strategies are combined:

- ``parser``      — a robust, deterministic rules parser for clean-ish input
  (fast, free, fully private). It is deliberately forgiving and, crucially,
  *reports* what it could not understand rather than silently dropping it.
- ``ai_normalizer`` — a Claude-backed fallback that reads truly messy input
  (pasted Word docs, inconsistent answer marking) and normalizes it into the
  same internal question model, returning its assumptions for staff to verify.

Both strategies feed the same ``serializers`` so output is identical regardless
of how the questions were parsed.
"""
