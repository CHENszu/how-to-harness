"""
冒泡排序 (Bubble Sort)
======================
一种简单的排序算法，通过重复遍历要排序的数列，
比较相邻元素并交换位置，直到没有需要交换的元素为止。

时间复杂度: O(n²)
空间复杂度: O(1)
稳定性: 稳定
"""


def bubble_sort(arr):
    """
    对列表进行冒泡排序（升序）

    参数:
        arr: 待排序的列表

    返回:
        排序后的列表（原地排序）
    """
    n = len(arr)

    # 外层循环控制遍历轮数
    for i in range(n - 1):
        # 标记是否发生交换，用于优化（如果一轮没有交换说明已有序）
        swapped = False

        # 内层循环进行相邻元素比较
        # 每轮结束后，最大的元素会"冒泡"到末尾
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                # 交换相邻元素
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True

        # 如果没有发生交换，说明已经有序，提前结束
        if not swapped:
            break

    return arr


def bubble_sort_desc(arr):
    """
    冒泡排序（降序版本）

    参数:
        arr: 待排序的列表

    返回:
        排序后的列表（原地排序）
    """
    n = len(arr)

    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if arr[j] < arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break

    return arr


def main():
    """演示冒泡排序的使用"""
    # 测试用例
    test_cases = [
        [64, 34, 25, 12, 22, 11, 90],
        [5, 2, 8, 1, 9],
        [1, 2, 3, 4, 5],          # 已经有序
        [5, 4, 3, 2, 1],          # 完全逆序
        [3, 3, 3, 3],             # 全部相同
        [],                        # 空列表
        [42],                      # 单个元素
    ]

    for i, arr in enumerate(test_cases, 1):
        original = arr.copy()
        sorted_arr = bubble_sort(arr)
        print(f"测试 {i}: {original} -> {sorted_arr}")

    print("\n--- 降序排序演示 ---")
    arr = [64, 34, 25, 12, 22, 11, 90]
    print(f"原始: {arr}")
    print(f"降序: {bubble_sort_desc(arr)}")


if __name__ == "__main__":
    main()
