import c


def b():
    import a

    a.a()
    print(c)


if __name__ == "__main__":
    b()
