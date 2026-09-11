"""A range-sum segment tree with O(log n) point updates and queries."""


class SegmentTree:
    """Store numeric values and efficiently calculate inclusive range sums."""

    def __init__(self, values: list[int | float]) -> None:
        self._length = len(values)
        self._size = 1
        while self._size < self._length:
            self._size *= 2

        self._tree: list[int | float] = [0] * (2 * self._size)
        self._tree[self._size : self._size + self._length] = values
        for node in range(self._size - 1, 0, -1):
            self._tree[node] = self._tree[node * 2] + self._tree[node * 2 + 1]

    def update(self, index: int, value: int | float) -> None:
        """Replace the value at *index* in O(log n) time."""
        self._validate_index(index)
        node = self._size + index
        self._tree[node] = value
        node //= 2
        while node:
            self._tree[node] = self._tree[node * 2] + self._tree[node * 2 + 1]
            node //= 2

    def query(self, left: int, right: int) -> int | float:
        """Return the sum from *left* through *right*, inclusive, in O(log n)."""
        if left < 0 or right < left or right >= self._length:
            raise IndexError("query bounds must be valid inclusive indices")

        left += self._size
        right += self._size
        total: int | float = 0
        while left <= right:
            if left % 2:
                total += self._tree[left]
                left += 1
            if not right % 2:
                total += self._tree[right]
                right -= 1
            left //= 2
            right //= 2
        return total

    def _validate_index(self, index: int) -> None:
        if index < 0 or index >= self._length:
            raise IndexError("index out of range")


if __name__ == "__main__":
    tree = SegmentTree([2, 1, 3, 4])
    assert tree.query(1, 3) == 8
    tree.update(2, 10)
    assert tree.query(1, 3) == 15
    print("Segment tree example passed.")
