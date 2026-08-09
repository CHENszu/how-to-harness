"""工具模块：提供基础数学运算函数"""


def add(a, b):
    """返回两个数的和"""
    return a + b


def subtract(a, b):
    """返回两个数的差"""
    return a - b


def multiply(a, b):
    """返回两个数的积"""
    return a * b


def divide(a, b):
    """返回两个数的商，b 不能为 0"""
    if b == 0:
        raise ValueError("除数不能为零")
    return a / b
