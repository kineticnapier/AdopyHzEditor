import math
import unittest
from unittest.mock import patch

from core.note_model import Note
from exporters import adofai
from tests.test_auto_route_twirl import _timing_relatives, _without_twirls, _twirl_floors


def revisits(level):
    x = y = 0.0
    seen = set()
    count = 0
    for angle in level['angleData']:
        x += math.cos(math.radians(angle))
        y += math.sin(math.radians(angle))
        cell = (round(x, 5), round(y, 5))
        count += cell in seen
        seen.add(cell)
    return count


class HarmonyAutoRouteTests(unittest.TestCase):
    def export(self, mode, **kwargs):
        return adofai.build_adofai_level(
            [Note(1, 121, 69)], method='harmony', harmony_mode='custom',
            harmony_custom_semitone=5, harmony_timing_mode='ratio-polyrhythm',
            visual_path_mode=mode, song_offset_ms=123, **kwargs,
        )[0]

    def test_route_preserves_timing_and_actions_and_reduces_revisits(self):
        raw = self.export('raw')
        routed = self.export('auto_route_twirl')
        self.assertFalse(_twirl_floors(raw['actions']))
        self.assertEqual(_timing_relatives(raw)[:6], [180, 60, 120, 120, 60, 180])
        self.assertTrue(_twirl_floors(routed['actions']))
        self.assertEqual(_timing_relatives(raw), _timing_relatives(routed))
        self.assertEqual(len(raw['angleData']), len(routed['angleData']))
        self.assertEqual(raw['settings'], routed['settings'])
        self.assertEqual(_without_twirls(raw['actions']), _without_twirls(routed['actions']))
        self.assertNotEqual(raw['angleData'], routed['angleData'])
        self.assertLess(revisits(routed), revisits(raw) / 2)
        self.assertEqual(routed, self.export('twirl upward'))
        planner = adofai.plan_auto_route_twirls
        with patch.object(adofai, 'plan_auto_route_twirls', side_effect=lambda r, **kw: planner(r, **{**kw, 'avoid_retracing': False})):
            previous = self.export('twirl upward')
        self.assertLess(revisits(routed), revisits(previous))

    def test_raw_never_calls_planner(self):
        with patch.object(adofai, 'plan_auto_route_twirls') as planner:
            self.export('raw')
        planner.assert_not_called()

    def test_variable_sequence_and_large_input(self):
        relatives = [180, 60, 120, 120, 60, 180, 135, 225] * 12500
        original = relatives.copy()
        floors, _ = adofai.plan_auto_route_twirls(relatives, avoid_retracing=True)
        actions = [adofai.twirl_event(f) for f in floors]
        level = {'actions': actions, 'angleData': adofai.rebuild_angle_data_from_relatives(relatives, actions)}
        self.assertEqual(_timing_relatives(level), original)
        self.assertEqual(relatives, original)


if __name__ == '__main__':
    unittest.main()
