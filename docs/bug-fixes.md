# Bug 修复记录

## 2026-09-03 · 同步脚本删除 Cargo 本地 patch

- 状态：已修复
- 现象：同步任务构建 GPUI 时无法读取 `corgi-patches/scratch/Cargo.toml`，Cargo 以退出码 101 失败。
- 根因：清理输出工作区时，脚本用固定根目录白名单删除了 Zed 新增的 `corgi-patches`，但根 `Cargo.toml` 仍保留指向该目录的 `[patch.crates-io]` 条目。
- 修复：从根 Cargo 清单的所有 `[patch]` 表收集安全的仓库内路径，在清理输出根目录时保留相应顶层目录；将回归测试接入同步工作流。
- 验证：`UV_CACHE_DIR=/tmp/gpui-clone-uv-cache uv run --with toml python -m unittest discover -s .github/scripts/tests -p 'test_*.py' -v` 通过 3 个测试；其中集成用例确认清理后 patch 清单仍存在，且 `cargo metadata --no-deps --offline --format-version 1` 成功。另以 Zed 当前官方 `Cargo.toml` 检查，脚本识别出的本地 patch 根目录包含 `corgi-patches`。
- 尝试：
  1. 从根 Cargo 清单收集安全的仓库内 patch 路径并加入保留集合；针对性测试和当前上游清单检查均通过，原缺失清单故障消失。
- 相似问题检索：未触发（少于两次失败）
