# Sync GPUI

<div align="center">

[![Sync GPUI](https://github.com/rain2307/gpui-clone/actions/workflows/sync_gpui.yml/badge.svg)](https://github.com/rain2307/gpui-clone/actions/workflows/sync_gpui.yml)
[![License](https://img.shields.io/badge/license-AGPL%203.0-blue)](https://github.com/zed-industries/zed/blob/main/LICENSE-AGPL)
[![Rust](https://img.shields.io/badge/rust-stable-brightgreen.svg)](https://www.rust-lang.org/)

</div>

This project provides an automated pipeline to extract and synchronize the **GPUI** framework from the [Zed](https://github.com/zed-industries/zed) repository into a standalone, lightweight distribution.

## How it Works

The synchronization process is fully automated via GitHub Actions and performs the following steps:

-   **Source Sync**: Every 2 hours, the latest code is pulled from the official Zed repository.
2.  **Dependency Analysis**: The script analyzes the dependency graph of the `gpui` crate to identify all required local crates.
3.  **Code Cleanup**:
    -   Removes all files and crates unrelated to GPUI.
    -   Strips out non-essential assets, documentation, and tooling.
    -   Stubs out complex internal macros (like `perf`) to minimize external dependencies.
4.  **Transformation**: Adjusts the workspace `Cargo.toml` and crate paths to ensure the extracted code remains buildable as a standalone project.
5.  **Distribution**: Synchronizes the cleaned code to the [gpui-clone](https://github.com/rain2307/gpui-clone) repository.

## Important Notes

-   **No Git History**: This repository only tracks the *current* state of GPUI. All original Git commit history from the Zed repository is discarded during the extraction process to keep the distribution lightweight.
-   **Automated Only**: The code in the target repository is managed by an automated script. Manual changes should not be made there as they will be overwritten by the next sync.
-   **Upstream Updates**: We track the latest stable/main branch of Zed. Breaking changes from upstream will be reflected here within 2 hours.

## Target Repository

You can find the standalone GPUI crates here:
👉 **[rain2307/gpui-clone](https://github.com/rain2307/gpui-clone)**

## License

This project follows the licensing of the upstream Zed project (Apache 2.0 or AGPL 3.0). Please refer to the source crates for specific license details.