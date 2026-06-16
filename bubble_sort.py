"""
冒泡排序 (Bubble Sort) - Python 实现

原理：重复遍历数组，依次比较相邻元素，
      如果顺序错误则交换，每轮将最大元素"冒泡"到末尾。

时间复杂度: O(n²)  最优: O(n)  空间复杂度: O(1)
稳定性: 稳定
"""


def bubble_sort(arr):
    """
    冒泡排序（升序）

    原理：重复遍历数组，比较相邻元素，如果顺序错误就交换。
    每轮遍历后，最大的未排序元素会"冒泡"到末尾。

    参数：
        arr: 待排序列表（会原地修改）

    返回：
        排序后的列表（原地排序，返回引用）
    """
    n = len(arr)
    # 外层循环：控制需要遍历的轮数
    for i in range(n - 1):
        # 优化标志：如果某一轮没有发生交换，说明已经有序
        swapped = False

        # 内层循环：比较相邻元素
        # 每轮结束后最后 i 个元素已经是正确的，无需再比较
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                # 交换相邻元素
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True

        # 如果没有交换，提前终止
        if not swapped:
            break

    return arr


# 测试代码
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        [64, 34, 25, 12, 22, 11, 90],
        [5, 1, 4, 2, 8],
        [1, 2, 3, 4, 5],        # 已经有序
        [5, 4, 3, 2, 1],        # 完全逆序
        [1],                     # 单元素
        [],                      # 空列表
    ]

    for i, arr in enumerate(test_cases, 1):
        original = arr.copy()
        sorted_arr = bubble_sort(arr)
        print(f"测试 {i}: {original} → {sorted_arr}")
