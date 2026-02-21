import os
import re
import shutil
import subprocess
from pathlib import Path
from logorator import Logger


class PublishError(Exception):
    """Raised when publishing fails"""
    pass


class Publisher:
    def __init__(self, package_dir: Path):
        self.package_dir = package_dir
        self.pyproject_path = package_dir / "pyproject.toml"
        self.package_name = package_dir.name
        self.init_path = package_dir / self.package_name / "__init__.py"
    
    def __str__(self):
        return self.package_name
        
    @Logger()
    def get_current_version(self) -> str:
        """Extract current version from pyproject.toml"""
        if not self.pyproject_path.exists():
            raise PublishError(f"pyproject.toml not found in {self.package_dir}")
        
        content = self.pyproject_path.read_text()
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        if not match:
            raise PublishError("Version not found in pyproject.toml")
        
        return match.group(1)
    
    @Logger()
    def bump_version(self, bump_type: str) -> str:
        """Bump version based on type (major, minor, patch)"""
        current = self.get_current_version()
        parts = list(map(int, current.split('.')))
        
        if bump_type == "major":
            parts = [parts[0] + 1, 0, 0]
        elif bump_type == "minor":
            parts = [parts[0], parts[1] + 1, 0]
        elif bump_type == "patch":
            parts = [parts[0], parts[1], parts[2] + 1]
        else:
            raise PublishError(f"Invalid bump type: {bump_type}")
        
        return ".".join(map(str, parts))
    
    @Logger()
    def update_version_files(self, new_version: str):
        """Update version in pyproject.toml and __init__.py"""
        # Update pyproject.toml
        content = self.pyproject_path.read_text()
        content = re.sub(
            r'(version\s*=\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{new_version}\g<2>',
            content
        )
        self.pyproject_path.write_text(content)
        Logger.note(f"Updated {self.pyproject_path.name}")
        
        # Update __init__.py
        if self.init_path.exists():
            content = self.init_path.read_text()
            content = re.sub(
                r'(__version__\s*=\s*["\'])[^"\']+(["\'])',
                rf'\g<1>{new_version}\g<2>',
                content
            )
            self.init_path.write_text(content)
            Logger.note(f"Updated {self.init_path.name}")
    
    @Logger()
    def check_git_clean(self):
        """Ensure git working directory is clean"""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.package_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise PublishError(f"Git command failed: {result.stderr}")
        
        if result.stdout.strip():
            raise PublishError("Git working directory is not clean. Commit or stash changes first.")
    
    @Logger()
    def git_commit_and_tag(self, version: str, commit_msg: str = None):
        """Commit changes and create git tag"""
        msg = commit_msg or f"Bump version to {version}"
        
        # Add files
        subprocess.run(["git", "add", "pyproject.toml"], cwd=self.package_dir, check=True)
        if self.init_path.exists():
            subprocess.run(["git", "add", str(self.init_path.relative_to(self.package_dir))], 
                         cwd=self.package_dir, check=True)
        
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=self.package_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise PublishError(f"Git commit failed: {result.stderr}")
        
        Logger.note(f"Committed: {msg}")
        
        # Tag
        result = subprocess.run(
            ["git", "tag", version],
            cwd=self.package_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise PublishError(f"Git tag failed: {result.stderr}")
        
        Logger.note(f"Tagged: {version}")
    
    @Logger()
    def git_push(self):
        """Push commits and tags to origin"""
        # Push commits
        result = subprocess.run(
            ["git", "push", "origin"],
            cwd=self.package_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise PublishError(f"Git push failed: {result.stderr}")
        
        Logger.note("Pushed commits")
        
        # Push tags
        result = subprocess.run(
            ["git", "push", "origin", "--tags"],
            cwd=self.package_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise PublishError(f"Git push tags failed: {result.stderr}")
        
        Logger.note("Pushed tags")
    
    @Logger()
    def clean_dist(self):
        """Remove old build artifacts"""
        dist_dir = self.package_dir / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
            Logger.note("Cleaned dist/")
    
    @Logger()
    def build_package(self):
        """Build the package using python -m build"""
        result = subprocess.run(
            ["python", "-m", "build"],
            cwd=self.package_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise PublishError(f"Build failed: {result.stderr}")
        
        Logger.note("Package built")
    
    @Logger()
    def upload_to_pypi(self):
        """Upload package to PyPI using twine"""
        result = subprocess.run(
            ["twine", "upload", "dist/*"],
            cwd=self.package_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise PublishError(f"PyPI upload failed: {result.stderr}")
        
        Logger.note("Uploaded to PyPI")
    
    @Logger()
    def publish(self, bump_type: str, commit_msg: str = None, skip_git: bool = False, 
                skip_pypi: bool = False, dry_run: bool = False):
        """Execute full publishing workflow"""
        try:
            # Pre-flight checks
            if not skip_git:
                self.check_git_clean()
            
            # Version bump
            new_version = self.bump_version(bump_type)
            Logger.note(f"Version: {self.get_current_version()} → {new_version}")
            
            if dry_run:
                Logger.note("DRY RUN - No changes made")
                return new_version
            
            self.update_version_files(new_version)
            
            # Git operations
            if not skip_git:
                self.git_commit_and_tag(new_version, commit_msg)
                self.git_push()
            
            # Build and publish
            if not skip_pypi:
                self.clean_dist()
                self.build_package()
                self.upload_to_pypi()
            
            Logger.note(f"✓ Published {self.package_name} {new_version}")
            return new_version
            
        except subprocess.CalledProcessError as e:
            raise PublishError(f"Command failed: {e.stderr if hasattr(e, 'stderr') else str(e)}")
        except Exception as e:
            raise PublishError(str(e))
