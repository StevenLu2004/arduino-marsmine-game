
def f1(s: str) -> list[int]:
    b = s.encode("u8")
    l = []
    for x in b:
        l.append(x >> 4)
        l.append(x & 15)
    while l and not l[-1]:
        l.pop()
    return l

cl = [
    (0, 0, 0),
    (0, 0, 170),
    (0, 170, 0),
    (0, 170, 170),
    (170, 0, 0),
    (170, 0, 170),
    (170, 170, 0),
    (170, 170, 170),
    (85, 85, 85),
    (85, 85, 255),
    (85, 255, 85),
    (85, 255, 255),
    (255, 85, 85),
    (255, 85, 255),
    (255, 255, 85),
    (255, 255, 255),
]

for i, c in enumerate(map(cl.__getitem__, f1(input()))):
    print(f"strip.setPixelColor{(i,)+c};")
