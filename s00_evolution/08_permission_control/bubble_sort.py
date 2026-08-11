def bubble_sort(arr):
    """
    冒泡排序算法
    通过重复遍历列表，比较相邻元素并交换位置，
    将较大的元素逐渐"冒泡"到列表末尾。

    参数:
        arr: 待排序的列表

    返回:
        排序后的列表（原地排序）
    """
    n = len(arr)
    # 外层循环控制遍历轮数
    for i in range(n):
        # 优化：如果某一轮没有发生交换，说明已经有序，提前结束
        swapped = False
        # 内层循环进行相邻元素比较
        # 每轮结束后，最大的元素会到达正确位置，所以可以减去 i
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                # 交换相邻元素
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        # 如果没有发生交换，说明已经排序完成
        if not swapped:
            break
    return arr


def main():
    """主函数：演示冒泡排序的使用"""
    # 测试用例
    test_cases = [
        [64, 34, 25, 12, 22, 11, 90],
        [5, 2, 8, 1, 9],
        [1, 2, 3, 4, 5],  # 已经有序
        [5, 4, 3, 2, 1],  # 完全逆序
        [3],              # 单个元素
        [],               # 空列表
    ]

    for i, test in enumerate(test_cases, 1):
        original = test.copy()
        sorted_arr = bubble_sort(test)
        print(f"测试 {i}: {original} -> {sorted_arr}")


if __name__ == "__main__":
    main()
