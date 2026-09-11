"""Read two numbers from standard input and print their sum."""


def main() -> None:
    first, second = map(float, input().split())
    result = first + second
    print(int(result) if result.is_integer() else result)


if __name__ == "__main__":
    main()
