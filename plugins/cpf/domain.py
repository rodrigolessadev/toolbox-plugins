import random
import re

def only_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def is_valid_cpf(cpf: str) -> bool:
    digits = only_digits(cpf)
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    def calc_digit(s, factor):
        total = sum(int(ch) * (factor - i) for i, ch in enumerate(s))
        rem = (total * 10) % 11
        return 0 if rem == 10 else rem

    d1 = calc_digit(digits[:9], 10)
    d2 = calc_digit(digits[:9] + str(d1), 11)
    return digits[-2:] == f"{d1}{d2}"

def format_cpf(digits: str) -> str:
    d = only_digits(digits)
    if len(d) != 11:
        return digits
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"

def generate_cpf(formatted: bool = True) -> str:
    base = [random.randint(0, 9) for _ in range(9)]
    d1 = sum(v * (10 - i) for i, v in enumerate(base)) * 10 % 11
    d1 = 0 if d1 == 10 else d1
    base.append(d1)
    d2 = sum(v * (11 - i) for i, v in enumerate(base)) * 10 % 11
    d2 = 0 if d2 == 10 else d2
    base.append(d2)
    digits = "".join(str(x) for x in base)
    return format_cpf(digits) if formatted else digits
