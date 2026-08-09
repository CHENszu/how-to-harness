# -*- coding: utf-8 -*-
"""
冒泡排序 (Bubble Sort) —— 详细注释版

冒泡排序是最经典的排序算法之一，思路非常简单：

  1. 从第一个元素开始，依次比较相邻的两个元素。
  2. 如果前一个元素比后一个元素大（升序排序时），就交换它们的位置。
  3. 每一轮（称为一趟）结束后，当前未排序区间中最大的元素
     就会像“气泡”一样浮到最右端。
  4. 重复以上过程，直到整个序列有序。

时间复杂度：
    - 最坏情况：O(n²)  （数组完全逆序时）
    - 最好情况：O(n)   （数组已经有序，且我们加了优化标志）
    - 平均情况：O(n²)
空间复杂度：O(1)  （原地排序，只用了少量额外变量）

下面我们用 Python 完整实现它，并给出非常详细的注释。
"""


def bubble_sort(arr):
    """
    对传入的列表 arr 进行原地升序冒泡排序。

    参数:
        arr (list): 待排序的数字列表（会被原地修改）

    返回:
        list: 排序后的列表（因为原地修改，返回的是同一个对象）
    """
    n = len(arr)

    # 外层循环：控制“趟数”
    # 每完成一趟，都会把当前未排序部分的最大值放到最后。
    # 一共最多需要 n-1 趟，因为 n 个元素最多冒 n-1 次就全部就位。
    for i in range(n - 1):

        # 这个标志用于优化：
        # 如果某一趟下来一次交换都没有发生，说明序列已经有序，
        # 我们就不必再继续后面无用的循环了。
        swapped = False

        # 内层循环：对未排序区间逐一比较相邻元素
        # 注意 j 的范围是 0 到 n - i - 1。
        # 因为经过 i 趟后，末尾的 i 个元素已经是正确的最大值了，
        # 无需再碰它们，所以结束边界要减去 i。
        for j in range(0, n - i - 1):

            # 比较相邻元素，若左边比右边大，则交换（升序）
            if arr[j] > arr[j + 1]:
                # 使用 Python 经典的元组交换语法，一行实现交换
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                # 发生了交换，把标志置为 True
                swapped = True

        # 优化：如果这一趟一次都没交换，说明整个数组已经有序
        # 直接提前结束外层循环，节省时间
        if not swapped:
            break

    # 返回排序后的列表
    return arr


def bubble_sort_desc(arr):
    """
    降序版本的冒泡排序（顺便演示一下改成降序只需改一个符号）。

    参数:
        arr (list): 待排序的数字列表（会被原地修改）

    返回:
        list: 排序后的列表
    """
    n = len(arr)
    for i in range(n - 1):
        swapped = False
        for j in range(0, n - i - 1):
            # 降序的关键：把比较符号从 > 改成 <
            if arr[j] < arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
    return arr


def print_list(arr):
    """打印列表到标准输出（可选的小工具函数）。"""
    print(" ".join(str(x) for x in arr))


def main():
    """
    主函数：用于演示冒泡排序的用法。
    """
    test_data = [
        [64, 34, 25, 12, 22, 11, 90],   # 乱序
        [5, 1, 4, 2, 8],                 # 乱序
        [1, 2, 3, 4, 5],                 # 已经有序（测试优化标志）
        [5, 4, 3, 2, 1],                 # 完全逆序（最坏情况）
    ]

    for data in test_data:
        # 注意：为了不污染原始数据，先复制一份再排序
        copy = data[:]
        print(f"排序前: {copy}")
        bubble_sort(copy)  # 升序
        print(f"升序后: {copy}")
        print("-" * 40)

    # 额外演示降序排序
    demo = [3, 1, 4, 1, 5, 9, 2, 6, 5]
    print(f"\n降序演示 - 原数据: {demo}")
    bubble_sort_desc(demo)
    print(f"降序后: {demo}")


# 当且仅当这个文件被直接运行时，才执行 main()。
# 这样如果别人 import 这个模块，不会自动跑 main()。
if __name__ == "__main__":
    main()
