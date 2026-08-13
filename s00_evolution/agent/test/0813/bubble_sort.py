def bubble_sort(arr):
    """冒泡排序算法"""
    n = len(arr)
    # 遍历所有数组元素
    for i in range(n):
        # 最后 i 个元素已经就位
        for j in range(0, n - i - 1):
            # 如果当前元素大于下一个元素，则交换
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


if __name__ == '__main__':
    # 测试示例
    test_list = [64, 34, 25, 12, 22, 11, 90]
    print('原始列表:', test_list)
    sorted_list = bubble_sort(test_list.copy())
    print('排序后列表:', sorted_list)