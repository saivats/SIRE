"""Production source filtering, model instructions and speech presentation contracts."""

import unittest

from app.chat.service import SYSTEM
from app.core.prompt_policy import GROUNDING, VERSION
from app.core.errors import SireError
from app.evidence.context import restore_text
from app.providers.ollama import VISION_INSTRUCTIONS, vision_policy_fingerprint
from app.voice.text import display_safe_text


class GroundingContracts(unittest.TestCase):
    def test_ambiguous_lists_cannot_hide_unknown_sources(self):
        mapping = {"E1": "EV:" + "a" * 64}
        for bracket in ["[EV:short]", "[E1, SRC:invented]", "[E1, invented]", "[E1-E2]", "[user:unknown]"]:
            with self.subTest(bracket=bracket), self.assertRaises(SireError):
                restore_text(bracket, mapping)
        self.assertEqual(restore_text("[E1]", mapping), "[" + mapping["E1"] + "]")
        self.assertEqual(restore_text("See [drawing] and [E1; e1]", mapping).count(mapping["E1"]), 2)

    def test_grounding_policy_and_vision_cache_identity(self):
        self.assertTrue(VERSION and SYSTEM)
        self.assertIn(GROUNDING, VISION_INSTRUCTIONS)
        self.assertEqual(len(vision_policy_fingerprint()), 64)

    def test_speech_keeps_narrative_and_omits_table(self):
        self.assertEqual(display_safe_text("Flow fell.\n| Asset | Flow |\n| --- | --- |\n| A | 12 |\nCheck its source."), "Flow fell. Check its source.")
