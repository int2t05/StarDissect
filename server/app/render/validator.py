# 中文排版校验器(REQ-RPT-003;UIUX-16…20 高置信子集)
# 输入=渲染管线跳过代码的纯文本;违规只标记不阻断(快速原型)
# 白名单例外:含官方产品名的行豁免中英/数字间距规则(UX-20,如 GitHub 紧贴中文)
import re

# (规则名, 正则, 说明)
RULES = [
    ("UX-16 中英文间距", re.compile(r"[一-龥][A-Za-z]|[A-Za-z][一-龥]"), "中文与英文之间应加空格"),
    ("UX-17 数字中文间距", re.compile(r"[一-龥][0-9]|[0-9][一-龥]"), "中文与数字之间应加空格"),
    ("UX-18 标点重复", re.compile(r"[,,;;::。、]{2,}"), "标点不应重复"),
    ("UX-19 半角标点误用", re.compile(r"[一-龥][,.!?;:](\s|$|[一-龥])"), "中文语境应使用全角标点"),
    ("UX-20 专有名词拼写", re.compile(r"\bGithub\b|\bh5\b|\bFED\b|\bIos\b"), "专有名词拼写不规范"),
]

WHITELIST = {"GitHub", "GitLab", "TypeScript"}


def validate(text: str) -> list[dict]:
    violations: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        has_product = any(w in line for w in WHITELIST)
        for name, rx, hint in RULES:
            if has_product and name in ("UX-16 中英文间距", "UX-17 数字中文间距"):
                continue
            for m in rx.finditer(line):
                start = max(0, m.start() - 20)
                violations.append({
                    "rule": name, "line": line_no, "hint": hint,
                    "context": line[start : m.end() + 20].strip(),
                })
    return violations
