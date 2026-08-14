"""
冒泡排序算法 (Bubble Sort)

冒泡排序是一种简单的排序算法。它重复地走访要排序的数列，
一次比较两个元素，如果它们的顺序错误就把它们交换过来。
走访数列的工作是重复地进行直到没有再需要交换，也就是说该数列已经排序完成。

时间复杂度:
    - 最好情况: O(n)  (已经有序)
    - 平均情况: O(n²)
    - 最坏情况: O(n²)

空间复杂度: O(1)
稳定性: 稳定
"""


def bubble_sort(arr):
    """
    对列表进行冒泡排序（升序）

    参数:
        arr: 待排序的列表

    返回:
        排序后的列表（原地排序，直接修改原列表）
    """
    n = len(arr)
    # 外层循环控制需要比较的轮数
    for i in range(n - 1):
        # 优化标志：如果某一轮没有发生交换，说明已经有序，提前结束
        swapped = False
        # 内层循环进行相邻元素比较
        # 每轮结束后，最大的元素会"冒泡"到末尾
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                # 交换相邻元素
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        # 如果没有发生交换，说明已经有序，提前退出
        if not swapped:
            break
    return arr


def bubble_sort_desc(arr):
    """
    对列表进行冒泡排序（降序）

    参数:
        arr: 待排序的列表

    返回:
        排序后的列表（原地排序，直接修改原列表）
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
    """主函数：演示冒泡排序的使用"""
    # 测试用例
    test_cases = [
        [64, 34, 25, 12, 22, 11, 90],
        [5, 1, 4, 2, 8],
        [1, 2, 3, 4, 5],          # 已经有序
        [5, 4, 3, 2, 1],          # 完全逆序
        [3, 3, 3, 3],             # 全部相同
        [],                        # 空列表
        [42],                      # 单个元素
    ]

    print("=" * 50)
    print("冒泡排序演示 (升序)")
    print("=" * 50)

    for i, test in enumerate(test_cases, 1):
        original = test.copy()
        result = bubble_sort(test)
        print(f"测试 {i}: {original} -> {result}")

    print("\n" + "=" * 50)
    print("冒泡排序演示 (降序)")
    print("=" * 50)

    test = [64, 34, 25, 12, 22, 11, 90]
    original = test.copy()
    result = bubble_sort_desc(test)
    print(f"原始数据: {original}")
    print(f"降序结果: {result}")


if __name__ == "__main__":
    main()
