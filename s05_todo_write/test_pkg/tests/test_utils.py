"""utils 模块的单元测试"""

import unittest

from test_pkg.utils import add, subtract, multiply, divide


class TestUtils(unittest.TestCase):
    """测试 utils 模块中的数学运算函数"""

    def test_add(self):
        """测试加法函数"""
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)

    def test_subtract(self):
        """测试减法函数"""
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(0, 5), -5)

    def test_multiply(self):
        """测试乘法函数"""
        self.assertEqual(multiply(3, 4), 12)
        self.assertEqual(multiply(0, 5), 0)

    def test_divide(self):
        """测试除法函数"""
        self.assertEqual(divide(10, 2), 5)
        self.assertAlmostEqual(divide(1, 3), 1 / 3)

    def test_divide_by_zero(self):
        """测试除数为零时抛出异常"""
        with self.assertRaises(ValueError):
            divide(10, 0)


if __name__ == "__main__":
    unittest.main()
