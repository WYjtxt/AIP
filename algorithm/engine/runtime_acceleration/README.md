# 算能 x86 录像加速

在 Linux x86_64 构建环境中，从仓库根目录执行 `make -C algorithm/engine/runtime_acceleration`。构建需要 C 编译器和 `make`，生成的两个 `.so` 文件须与本目录 Python 加载模块放在一起。

差分录像模块加载 AVX2 库前会检查 CPU 能力。缺少本地库时，帧缓存和画面标注使用 Python 路径，保留报警录像功能。
