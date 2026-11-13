"""Small deterministic reasoning tools. No eval, shell, network or LLM calls."""
import ast
import operator
import re
import time
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
                   if unicodedata.category(c) != "Mn")


def number(text):
    text = text.strip()
    if re.fullmatch(r"[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?", text):
        text = text.replace(".", "")
    return Fraction(text.replace(",", "."))


def show(value):
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    with localcontext() as context:
        context.prec = 12
        result = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    approximate = Fraction(result) != value
    return ("≈ " if approximate else "") + result.rstrip("0").rstrip(".").replace(".", ",")


@dataclass
class Result:
    text: str
    skill: str
    facts: dict


def calculate(expression):
    if len(expression) > 200:
        raise ValueError("Biểu thức quá dài; tối đa 200 ký tự.")
    expression = expression.replace("×", "*").replace("÷", "/").replace("−", "-")
    expression = expression.replace("^", "**")
    expression = re.sub(r"(\d+(?:[.,]\d+)*)\s*%", r"(\1/100)", expression)
    expression = re.sub(r"(?<=\d)\s*[xX]\s*(?=[\d(])", "*", expression)
    expression = re.sub(r"\d+(?:[.,]\d+)*", lambda match: str(number(match[0])) if number(match[0]).denominator == 1
                        else "(" + str(number(match[0]).numerator) + "/" + str(number(match[0]).denominator) + ")", expression)
    if not re.fullmatch(r"[0-9\s.+*/()%-]+", expression):
        raise ValueError("Chỉ hỗ trợ số và các phép +, −, ×, ÷, lũy thừa, phần trăm, ngoặc.")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise ValueError("Biểu thức chưa hợp lệ.") from None
    if sum(1 for _ in ast.walk(tree)) > 70:
        raise ValueError("Biểu thức có quá nhiều phép tính.")
    functions = {ast.Add: operator.add, ast.Sub: operator.sub,
                 ast.Mult: operator.mul, ast.Div: operator.truediv}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = Fraction(str(node.value))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow):
                if right.denominator != 1 or abs(right) > 8:
                    raise ValueError("Số mũ cần là số nguyên từ −8 đến 8.")
                value = left ** int(right)
            elif type(node.op) in functions:
                value = functions[type(node.op)](left, right)
            else:
                raise ValueError("Phép tính chưa được hỗ trợ.")
        else:
            raise ValueError("Biểu thức chứa thành phần không được phép.")
        if abs(value) > 10**18 or value.denominator > 10**18:
            raise ValueError("Số vượt giới hạn tính toán nhẹ.")
        return value

    try:
        return visit(tree.body)
    except ZeroDivisionError:
        raise ValueError("Không thể chia cho 0.") from None


def arithmetic(question):
    text = normalize(question).strip().rstrip("?= ")
    percentage = re.fullmatch(r"(?:tinh\s+)?(\d+(?:[.,]\d+)?)\s*%\s*cua\s*(\d+(?:[.,]\d+)*)", text)
    if percentage:
        result = number(percentage[1]) / 100 * number(percentage[2])
        return Result(f"{percentage[1]}% của {percentage[2]} = **{show(result)}**.", "calculator", {"result": str(result)})
    explicit = re.match(r"^(?:/calc\s+|tinh\s+(?:giup\s+(?:toi|minh)\s+)?|tinh:\s*)", text)
    expression = text[explicit.end():] if explicit else text
    expression = re.sub(r"\s+(?:bang bao nhieu|bang may|la bao nhieu)$", "", expression).strip()
    if not explicit and not re.fullmatch(r"[\d\s.,+*/×÷^()xX%−-]+", expression):
        return None
    if explicit and not re.fullmatch(r"[\d\s.,+*/×÷^()xX%−-]+", expression):
        # Natural-language requests such as "tính thời gian" need another skill.
        return None
    if not re.search(r"\d", expression):
        return None
    try:
        result = calculate(expression)
        return Result(f"Kết quả: **{show(result)}**.", "calculator", {"expression": expression, "result": str(result)})
    except ValueError as exc:
        return Result(str(exc), "calculator", {"error": True})


_TIME = re.compile(r"(?P<n>\d+(?:[.,]\d+)?)\s*(?P<u>gio|tieng|phut|giay)\b")
_SCALE = {"gio": Fraction(60), "tieng": Fraction(60), "phut": Fraction(1), "giay": Fraction(1, 60)}


def durations(text):
    raw = list(_TIME.finditer(text))
    groups = []
    for match in raw:
        value = number(match["n"]) * _SCALE[match["u"]]
        if groups and re.fullmatch(r"\s*(?:va\s*)?", text[groups[-1]["end"]:match.start()]):
            groups[-1]["minutes"] += value
            groups[-1]["end"] = match.end()
        else:
            groups.append({"start": match.start(), "end": match.end(), "minutes": value})
    return groups


def time_plan(question):
    text = normalize(question)
    if re.search(r'\b(?:phuong an|lua chon|hoac|song song|dong thoi)\b', text):
        # Alternative choices and overlapping tasks are not additive activities.
        return None
    if not any(term in text for term in ("kip", "du thoi gian", "con lai", "tong thoi gian", "ke hoach", "co du")):
        return None
    groups = durations(text)
    if len(groups) < 2 or len(groups) > 12:
        return None
    budgets = []
    for index, item in enumerate(groups):
        before = text[max(0, item["start"] - 65):item["start"]]
        if re.search(r"(?:khong|chua|chang)\s+co\s*$", before):
            return Result("Chủ nhân có bao nhiêu thời gian thực tế? Em chưa thể dùng khoảng thời gian đang bị phủ định làm ngân sách.",
                          "time-planning", {"needs_clarification": True})
        if (re.search(r"(?:\bco|\bcon|\branh|\brong|toi da|gioi han|trong vong)\s*(?:khoang\s*)?$", before)
                or re.search(r"\bco kip\b[^.;?!\n\d]{0,40}\btrong\s*$", before)):
            budgets.append(index)
    if not budgets or len({groups[index]["minutes"] for index in budgets}) != 1:
        return Result("Chủ nhân có tổng cộng bao nhiêu thời gian? Hãy nêu thời gian rảnh và thời gian từng việc để em tính đúng.",
                      "time-planning", {"needs_clarification": True})
    budget_index = budgets[0]
    budget = groups[budget_index]["minutes"]
    activities = []
    for index, item in enumerate(groups):
        if index in budgets:
            continue
        before = text[groups[index - 1]["end"] if index else 0:item["start"]]
        end = groups[index + 1]["start"] if index + 1 < len(groups) else len(text)
        after = text[item["end"]:end]
        clause = re.split(r"[.;\n]", after)[0][:65]
        multiplier = 1
        if re.search(r"\b(?:moi|mot) chieu\b", clause) or re.search(r"(?:moi|mot) chieu\s*(?:mat|ton|la)?\s*$", before):
            multiplier = 2
        if re.search(r"khu hoi|ca (?:di va ve|di lan ve)|tong ca hai chieu", clause):
            multiplier = 1
        if re.search(r"moi (?:lan|luot)\b", clause):
            return Result("Chủ nhân thực hiện việc đó mấy lần/lượt? Em cần số lần để tính tổng.",
                          "time-planning", {"needs_clarification": True})
        repeat = re.match(r"\s*(?:x|nhan)\s*(\d+)\b", after)
        if repeat:
            multiplier = int(repeat[1])
            if not 1 <= multiplier <= 100:
                return Result("Số lượt cần từ 1 đến 100 trong phép tính này.", "time-planning", {"error": True})
        activities.append((item["minutes"], multiplier))
    if any(value < 0 or value > 10080 for value, _ in activities) or budget > 10080:
        return None
    total = sum((value * multiplier for value, multiplier in activities), Fraction())
    remaining = budget - total
    expression = " + ".join(show(value) + (f" × {multiplier}" if multiplier != 1 else "") for value, multiplier in activities)
    result = f"{'Kịp' if remaining >= 0 else 'Không kịp'}. Tổng cần **{show(total)} phút** ({expression}), chủ nhân có **{show(budget)} phút**. "
    result += f"Còn dư **{show(remaining)} phút**." if remaining >= 0 else f"Thiếu **{show(-remaining)} phút**."
    return Result(result, "time-planning", {"total_minutes": str(total), "budget_minutes": str(budget),
                                            "remaining_minutes": str(remaining), "feasible": remaining >= 0})


UNITS = {
    "km": ("length", Fraction(1000)), "m": ("length", Fraction(1)), "cm": ("length", Fraction(1, 100)), "mm": ("length", Fraction(1, 1000)),
    "kg": ("mass", Fraction(1000)), "g": ("mass", Fraction(1)), "mg": ("mass", Fraction(1, 1000)),
    "gio": ("time", Fraction(3600)), "tieng": ("time", Fraction(3600)), "phut": ("time", Fraction(60)), "giay": ("time", Fraction(1)),
}


def convert_units(question):
    text = normalize(question).strip().rstrip("?. ")
    names = "|".join(sorted(UNITS, key=len, reverse=True))
    match = re.fullmatch(r"(?:doi\s+|chuyen\s+)?(\d+(?:[.,]\d+)?)\s*(" + names +
                         r")\s*(?:sang|ra|thanh|bang)\s*(?:bao nhieu\s*)?(" + names + r")", text)
    if not match:
        return None
    amount, source, target = number(match[1]), match[2], match[3]
    if UNITS[source][0] != UNITS[target][0]:
        return Result("Hai đơn vị không cùng loại nên không thể đổi trực tiếp.", "unit-conversion", {"error": True})
    result = amount * UNITS[source][1] / UNITS[target][1]
    return Result(f"{match[1]} {source} = **{show(result)} {target}**.", "unit-conversion", {"result": str(result)})


def sudoku(question):
    if "sudoku" not in question.lower():
        return None
    rows = []
    for line in question.splitlines():
        if re.fullmatch(r"[\d.\s|]+", line) and len(re.sub(r"[^0-9.]", "", line)) == 9:
            rows.append(re.sub(r"[^0-9.]", "", line))
    if len(rows) == 9:
        grid = "".join(rows)
    else:
        match = re.search(r"(?<![0-9.])([0-9.]{81})(?![0-9.])", question)
        if not match:
            return Result("Gửi đề Sudoku 9 dòng, mỗi dòng 9 số; dùng 0 hoặc dấu chấm cho ô trống.", "sudoku", {"needs_grid": True})
        grid = match[1]
    values = [0 if char == "." else int(char) for char in grid]
    given = values[:]
    row_masks, col_masks, box_masks = [0] * 9, [0] * 9, [0] * 9
    for index, value in enumerate(values):
        if not value:
            continue
        row, col = divmod(index, 9)
        box, bit = row // 3 * 3 + col // 3, 1 << value
        if (row_masks[row] | col_masks[col] | box_masks[box]) & bit:
            return Result("Đề Sudoku có số trùng trong hàng, cột hoặc ô 3×3. Hãy kiểm tra lại đề.", "sudoku", {"invalid": True})
        row_masks[row] |= bit; col_masks[col] |= bit; box_masks[box] |= bit

    def choices(index):
        row, col = divmod(index, 9)
        return 1022 & ~(row_masks[row] | col_masks[col] | box_masks[row // 3 * 3 + col // 3])

    if "goi y" in normalize(question):
        for index, value in enumerate(values):
            if not value and choices(index).bit_count() == 1:
                row, col = divmod(index, 9)
                digit = choices(index).bit_length() - 1
                return Result(f"Ô hàng {row + 1}, cột {col + 1} chỉ còn ứng viên **{digit}**, sau khi loại các số đã có trong hàng, cột và ô 3×3.",
                              "sudoku", {"row": row + 1, "column": col + 1, "value": digit})
        return Result("Chưa có ô đơn ứng viên ngay. Chủ nhân có thể yêu cầu giải Sudoku để tìm nghiệm bằng bộ giải.", "sudoku", {"no_single": True})
    solutions, nodes = [], 0
    deadline, exhausted = time.monotonic() + .35, False

    def solve():
        nonlocal nodes, exhausted
        nodes += 1
        if nodes > 30000 or time.monotonic() > deadline:
            exhausted = True
            return
        empty = [index for index, value in enumerate(values) if not value]
        if not empty:
            solutions.append(values[:]); return
        index = min(empty, key=lambda item: choices(item).bit_count())
        candidates = choices(index)
        row, col = divmod(index, 9); box = row // 3 * 3 + col // 3
        while candidates and len(solutions) < 2 and not exhausted:
            bit = candidates & -candidates; candidates ^= bit
            values[index] = bit.bit_length() - 1
            row_masks[row] |= bit; col_masks[col] |= bit; box_masks[box] |= bit
            solve()
            row_masks[row] ^= bit; col_masks[col] ^= bit; box_masks[box] ^= bit
            values[index] = 0
    solve()
    if not solutions:
        return Result("Chưa tìm được nghiệm trong giới hạn xử lý nhẹ." if exhausted else "Đề Sudoku này không có nghiệm.",
                      "sudoku", {"exhausted": exhausted, "solutions": 0})
    solution = solutions[0]
    assert all(not digit or solution[index] == digit for index, digit in enumerate(given))
    heading = "Một nghiệm (đề có nhiều nghiệm):" if len(solutions) > 1 else "Đã tìm được một nghiệm; chưa xác định tính duy nhất trong giới hạn:" if exhausted else "Nghiệm duy nhất:"
    rendered = "\n".join(" ".join(map(str, solution[index:index + 9])) for index in range(0, 81, 9))
    return Result(heading + "\n\n" + rendered, "sudoku", {"solution": solution, "solutions": len(solutions), "nodes": nodes, "exhausted": exhausted})
