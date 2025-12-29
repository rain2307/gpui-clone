import os
import shutil
import toml
import subprocess
import tempfile

def read_toml(path):
    with open(path, 'r') as f:
        return toml.load(f)

def write_toml(path, data):
    with open(path, 'w') as f:
        toml.dump(data, f)

def robust_copy_tree(src, dst):
    """
    Recursively copies a directory tree, handling symlinks by copying the target file/dir
    (dereferencing), and ignoring errors for missing files (dangling links).
    """
    if not os.path.exists(dst):
        os.makedirs(dst)

    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        try:
            if os.path.isdir(s):
                robust_copy_tree(s, d)
            else:
                # shutil.copy2 follows symlinks by default (dereferences them)
                shutil.copy2(s, d)
        except (FileNotFoundError, OSError) as e:
            # Skip dangling symlinks or unreadable files
            print(f"Skipping {s}: {e}")
            continue

def get_workspace_dependencies(root_cargo_toml):
    return root_cargo_toml.get("workspace", {}).get("dependencies", {})

def get_crate_dependencies(crate_path):
    cargo_path = os.path.join(crate_path, "Cargo.toml")
    if not os.path.exists(cargo_path):
        return []
    
    data = read_toml(cargo_path)
    deps = []
    
    for section in ["dependencies", "dev-dependencies", "build-dependencies"]:
        if section in data:
            deps.extend(data[section].keys())
            
    if "target" in data:
        for target in data["target"]:
            if "dependencies" in data["target"][target]:
                deps.extend(data["target"][target]["dependencies"].keys())
            if "build-dependencies" in data["target"][target]:
                deps.extend(data["target"][target]["build-dependencies"].keys())
                
    return deps

def resolve_local_dependencies(start_crate, root_path, workspace_deps):
    to_visit = [start_crate]
    visited = set()
    local_crates = set()

    dep_name_to_path = {}
    for name, defn in workspace_deps.items():
        if isinstance(defn, dict) and "path" in defn:
            path = defn["path"]
            if path.startswith("crates/"):
                crate_name = os.path.basename(path)
                dep_name_to_path[name] = crate_name

    while to_visit:
        current_crate = to_visit.pop()
        if current_crate in visited:
            continue
        visited.add(current_crate)
        local_crates.add(current_crate)

        crate_path = os.path.join(root_path, "crates", current_crate)
        deps = get_crate_dependencies(crate_path)
        
        for dep in deps:
            if dep in dep_name_to_path:
                next_crate = dep_name_to_path[dep]
                if next_crate not in visited:
                    to_visit.append(next_crate)

    return local_crates

def main():
    # Use a temporary directory for the entire workspace
    with tempfile.TemporaryDirectory() as work_dir:
        print(f"Created temporary workspace at: {work_dir}")
        
        # Define paths within the temporary directory
        SOURCE_DIR = os.path.join(work_dir, "source", "zed")
        OUTPUT_DIR = os.path.join(work_dir, "output", "zed")
        UPLOAD_DIR = os.path.join(work_dir, "upload", "gpui-clone")

        # 0. Setup and Clone source
        zed_repo_url = "https://github.com/zed-industries/zed.git"
        
        print(f"Cloning {zed_repo_url} into {SOURCE_DIR}...")
        # Ensure parent dir exists
        os.makedirs(os.path.dirname(SOURCE_DIR), exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", zed_repo_url, SOURCE_DIR], check=True)

        # 1. Copy project
        print(f"Copying {SOURCE_DIR} to {OUTPUT_DIR}...")
        # No need to check exists for new temp dir, but good practice
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        
        robust_copy_tree(SOURCE_DIR, OUTPUT_DIR)

        # 2. Analyze dependencies
        print("Analyzing dependencies...")
        root_cargo_path = os.path.join(OUTPUT_DIR, "Cargo.toml")
        root_cargo = read_toml(root_cargo_path)
        workspace_deps = get_workspace_dependencies(root_cargo)
        
        needed_crates = resolve_local_dependencies("gpui", OUTPUT_DIR, workspace_deps)
        print(f"Identified {len(needed_crates)} required local crates: {sorted(list(needed_crates))}")

        # 3. Clean crates directory
        print("Cleaning crates directory...")
        crates_dir = os.path.join(OUTPUT_DIR, "crates")
        for item in os.listdir(crates_dir):
            item_path = os.path.join(crates_dir, item)
            if os.path.isdir(item_path):
                if item not in needed_crates:
                    shutil.rmtree(item_path)

        # Clean remaining crates (remove README, LICENSE, symlinks, etc.)
        if os.path.exists(crates_dir):
            for root, dirs, files in os.walk(crates_dir):
                for d in ["docs"]:
                    if d in dirs:
                        shutil.rmtree(os.path.join(root, d))
                        dirs.remove(d)
                
                for f in files:
                    file_path = os.path.join(root, f)
                    
                    # Check for symlinks
                    if os.path.islink(file_path):
                         try:
                            os.remove(file_path)
                         except OSError:
                            pass
                         continue

                    lower_f = f.lower()
                    # Special case: gpui needs its README.md for compilation
                    if lower_f == "readme.md" and "gpui" in root.split(os.sep):
                        continue

                    if (lower_f.startswith("readme") or 
                        lower_f.startswith("license") or 
                        lower_f.startswith("changelog") or 
                        lower_f.startswith("contributing") or
                        lower_f.startswith("dockerfile") or
                        lower_f.endswith(".md") or
                        lower_f.endswith(".txt")):
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass

        # 4. Clean tooling and extensions
        print("Cleaning tooling and extensions...")
        tooling_dir = os.path.join(OUTPUT_DIR, "tooling")
        if os.path.exists(tooling_dir):
            shutil.rmtree(tooling_dir)
        
        extensions_dir = os.path.join(OUTPUT_DIR, "extensions")
        if os.path.exists(extensions_dir):
            shutil.rmtree(extensions_dir)

        # 4.5. Clean non-Rust files
        print("Cleaning non-Rust files...")
        dirs_to_remove = [
            ".cargo", ".cloudflare", ".config", ".factory", ".github", ".zed", 
            "ci", "docs", "legal", "nix", "script", "assets"
        ]
        for d in dirs_to_remove:
            path = os.path.join(OUTPUT_DIR, d)
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                
        files_to_keep = {
            "Cargo.toml", "Cargo.lock", "clippy.toml", "rust-toolchain.toml", "crates", "target", ".gitignore"
        }
        
        for f in os.listdir(OUTPUT_DIR):
            path = os.path.join(OUTPUT_DIR, f)
            
            # Remove symbolic links in root
            if os.path.islink(path):
                print(f"Removing symbolic link: {f}")
                os.remove(path)
                continue

            if f not in files_to_keep:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)

        # 4.6. Stub util_macros (remove perf dependency)
        print("Stubbing util_macros...")
        util_macros_cargo = os.path.join(OUTPUT_DIR, "crates/util_macros/Cargo.toml")
        if os.path.exists(util_macros_cargo):
            data = read_toml(util_macros_cargo)
            if "dependencies" in data and "perf" in data["dependencies"]:
                del data["dependencies"]["perf"]
                write_toml(util_macros_cargo, data)
                
        util_macros_src = os.path.join(OUTPUT_DIR, "crates/util_macros/src/util_macros.rs")
        if os.path.exists(util_macros_src):
            with open(util_macros_src, "r") as f:
                content = f.read()
            
            stub_code = """
mod perf {
    #[derive(Default, Clone, Copy, Debug)]
    pub enum Importance { Critical, Important, #[default] Average, Iffy, Fluff }
    impl std::fmt::Display for Importance {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            write!(f, "{:?}", self)
        }
    }
    pub mod consts {
        pub const SUF_NORMAL: &str = "";
        pub const SUF_MDATA: &str = "";
        pub const ITER_ENV_VAR: &str = "";
        pub const MDATA_LINE_PREF: &str = "";
        pub const MDATA_VER: u32 = 0;
        pub const WEIGHT_DEFAULT: u8 = 0;
        pub const ITER_COUNT_LINE_NAME: &str = "";
        pub const WEIGHT_LINE_NAME: &str = "";
        pub const IMPORTANCE_LINE_NAME: &str = "";
        pub const VERSION_LINE_NAME: &str = "";
    }
}
use perf::*;
"""
            content = content.replace("use perf::*;", stub_code)
            with open(util_macros_src, "w") as f:
                f.write(content)

        # 5. Fix root Cargo.toml
        print("Updating Cargo.toml...")
        
        if "default-members" in root_cargo["workspace"]:
            root_cargo["workspace"]["default-members"] = ["crates/gpui"]
            
        if "members" in root_cargo["workspace"]:
            new_members = []
            for member in root_cargo["workspace"]["members"]:
                if os.path.exists(os.path.join(OUTPUT_DIR, member)):
                    new_members.append(member)
            root_cargo["workspace"]["members"] = new_members

        if "dependencies" in root_cargo["workspace"]:
            new_deps = {}
            for name, defn in root_cargo["workspace"]["dependencies"].items():
                keep = True
                if isinstance(defn, dict) and "path" in defn:
                    full_path = os.path.join(OUTPUT_DIR, defn["path"])
                    if not os.path.exists(full_path):
                        keep = False
                
                if keep:
                    new_deps[name] = defn
            root_cargo["workspace"]["dependencies"] = new_deps

        if "profile" in root_cargo:
            for profile_name in root_cargo["profile"]:
                profile = root_cargo["profile"][profile_name]
                if isinstance(profile, dict) and "package" in profile:
                    new_package_overrides = {}
                    for pkg_name, pkg_defn in profile["package"].items():
                        exists = False
                        for member in root_cargo["workspace"]["members"]:
                            if member.endswith("/" + pkg_name) or member == pkg_name:
                                exists = True
                                break
                        if exists:
                            new_package_overrides[pkg_name] = pkg_defn
                    
                    profile["package"] = new_package_overrides

        write_toml(root_cargo_path, root_cargo)

        # 6. Build
        if shutil.which("cargo"):
            print("Building gpui...")
            subprocess.run(["cargo", "build", "-p", "gpui"], check=True, cwd=OUTPUT_DIR)
        else:
            print("Cargo not found, skipping build.")

        # 7. Sync to upload/gpui-clone
        repo_url = "https://github.com/rain2307/gpui-clone.git"

        # Ensure upload parent directory exists (inside temp)
        os.makedirs(os.path.dirname(UPLOAD_DIR), exist_ok=True)

        print(f"Cloning {repo_url} into {UPLOAD_DIR}...")
        try:
            subprocess.run(["git", "clone", repo_url, UPLOAD_DIR], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone repository: {e}")
            return

        if os.path.exists(UPLOAD_DIR) and os.path.isdir(UPLOAD_DIR):
            print(f"Syncing to {UPLOAD_DIR}...")
            
            # Get source commit hash
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"], 
                    cwd=SOURCE_DIR, 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                source_commit = result.stdout.strip()
            except subprocess.CalledProcessError:
                source_commit = "unknown"
                print("Warning: Could not get source commit hash.")

            # Sync files
            # Remove files in UPLOAD_DIR that are not in OUTPUT_DIR (except .git and .github)
            for root, dirs, files in os.walk(UPLOAD_DIR):
                path_parts = root.split(os.sep)
                if ".git" in path_parts or ".github" in path_parts:
                    continue
                
                # Remove files
                for f in files:
                    if f == ".git": continue
                    
                    rel_path = os.path.relpath(os.path.join(root, f), UPLOAD_DIR)
                    if rel_path.startswith(".github"): continue
                    if f == "README.md": continue

                    src_path = os.path.join(OUTPUT_DIR, rel_path)
                    
                    if not os.path.exists(src_path):
                        os.remove(os.path.join(root, f))
                
                # Remove directories
                for d in dirs:
                    if d == ".git": continue
                    
                    rel_path = os.path.relpath(os.path.join(root, d), UPLOAD_DIR)
                    if rel_path.startswith(".github"): continue
                    
                    src_path = os.path.join(OUTPUT_DIR, rel_path)
                    
                    if not os.path.exists(src_path):
                        shutil.rmtree(os.path.join(root, d))

            # Copy files from OUTPUT_DIR to UPLOAD_DIR
            robust_copy_tree(OUTPUT_DIR, UPLOAD_DIR)

            # Git operations
            print("Committing changes...")
            try:
                subprocess.run(["git", "add", "."], cwd=UPLOAD_DIR, check=True)
                
                # Check for changes
                status = subprocess.run(
                    ["git", "status", "--porcelain"], 
                    cwd=UPLOAD_DIR, 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                
                if status.stdout.strip():
                    commit_msg = f"Sync with zed commit: {source_commit}"
                    subprocess.run(["git", "commit", "-m", commit_msg], cwd=UPLOAD_DIR, check=True)
                    print(f"Committed changes with message: {commit_msg}")
                    
                    # Push changes
                    print("Pushing changes...")
                    subprocess.run(["git", "push"], cwd=UPLOAD_DIR, check=True)
                else:
                    print("No changes to commit.")
                    
            except subprocess.CalledProcessError as e:
                print(f"Git operation failed: {e}")

if __name__ == "__main__":
    main()