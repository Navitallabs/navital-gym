"""v1.1 GST grader changes: commas only as digit grouping; lists are order-free but a repeated id fails."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from decimal import Decimal
from navital_gym.envs.gst.rules import num

class Num(unittest.TestCase):
    def test_grouped_numbers_still_parse(self):
        self.assertEqual(num("4,680.00"), Decimal("4680.00")); self.assertEqual(num("1,23,456"), Decimal(123456)); self.assertEqual(num("123,456"), Decimal(123456))
        self.assertEqual(num(4680), Decimal(4680)); self.assertEqual(num("4680.5"), Decimal("4680.5"))

    def test_stray_commas_are_not_stripped(self):
        """v1.0.1 read '1,2,3' as 123."""
        for bad in ("1,2,3", "12,34", "1,23", ",100", "100,"):
            self.assertIsNone(num(bad), bad)

if __name__ == "__main__":
    unittest.main()
