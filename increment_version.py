"""
打包前自动递增版本号
读取 attendance_tool.py 中的 APP_VERSION，版本号+1 后写回文件
"""
import re, sys

py_file = "attendance_tool.py"
with open(py_file, encoding="utf-8") as f:
    content = f.read()

# 匹配 APP_VERSION = "v数字"
def bump(m):
    ver = int(m.group(1)) + 1
    return f'APP_VERSION = "v{ver}"'

new_content, n = re.subn(r'APP_VERSION = "v(\d+)"', bump, content)
if n == 0:
    print("[版本] 未找到 APP_VERSION，直接打包")
else:
    with open(py_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    # 提取新版本号用于显示
    m = re.search(r'APP_VERSION = "v(\d+)"', new_content)
    print(f"[版本] v{m.group(1)}  ← 已在 attendance_tool.py 中更新")
