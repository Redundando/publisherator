import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from publisherator.publisher import Publisher, PublishError


@pytest.fixture
def temp_package(tmp_path):
    """Create a temporary package structure"""
    package_dir = tmp_path / "testpkg"
    package_dir.mkdir()
    
    # Create pyproject.toml
    pyproject = package_dir / "pyproject.toml"
    pyproject.write_text('[project]\nname = "testpkg"\nversion = "1.2.3"\n')
    
    # Create package __init__.py
    pkg_subdir = package_dir / "testpkg"
    pkg_subdir.mkdir()
    init_file = pkg_subdir / "__init__.py"
    init_file.write_text('__version__ = "1.2.3"\n')
    
    return package_dir


def test_get_current_version(temp_package):
    pub = Publisher(temp_package)
    assert pub.get_current_version() == "1.2.3"


def test_get_current_version_missing_file(tmp_path):
    pub = Publisher(tmp_path)
    with pytest.raises(PublishError, match="pyproject.toml not found"):
        pub.get_current_version()


def test_get_current_version_no_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"\n')
    pub = Publisher(tmp_path)
    with pytest.raises(PublishError, match="Version not found"):
        pub.get_current_version()


def test_bump_version_patch(temp_package):
    pub = Publisher(temp_package)
    assert pub.bump_version("patch") == "1.2.4"


def test_bump_version_minor(temp_package):
    pub = Publisher(temp_package)
    assert pub.bump_version("minor") == "1.3.0"


def test_bump_version_major(temp_package):
    pub = Publisher(temp_package)
    assert pub.bump_version("major") == "2.0.0"


def test_bump_version_invalid(temp_package):
    pub = Publisher(temp_package)
    with pytest.raises(PublishError, match="Invalid bump type"):
        pub.bump_version("invalid")


def test_update_version_files(temp_package):
    pub = Publisher(temp_package)
    pub.update_version_files("2.0.0")
    
    # Check pyproject.toml
    content = (temp_package / "pyproject.toml").read_text()
    assert 'version = "2.0.0"' in content
    
    # Check __init__.py
    content = (temp_package / "testpkg" / "__init__.py").read_text()
    assert '__version__ = "2.0.0"' in content


def test_update_version_files_no_init(temp_package):
    # Remove __init__.py
    (temp_package / "testpkg" / "__init__.py").unlink()
    
    pub = Publisher(temp_package)
    pub.update_version_files("2.0.0")
    
    # Should still update pyproject.toml
    content = (temp_package / "pyproject.toml").read_text()
    assert 'version = "2.0.0"' in content


@patch('subprocess.run')
def test_check_git_clean_success(mock_run, temp_package):
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    pub = Publisher(temp_package)
    pub.check_git_clean()  # Should not raise


@patch('subprocess.run')
def test_check_git_clean_dirty(mock_run, temp_package):
    mock_run.return_value = Mock(returncode=0, stdout="M file.py\n", stderr="")
    pub = Publisher(temp_package)
    with pytest.raises(PublishError, match="not clean"):
        pub.check_git_clean()


@patch('subprocess.run')
def test_check_git_clean_git_error(mock_run, temp_package):
    mock_run.return_value = Mock(returncode=1, stdout="", stderr="fatal: not a git repo")
    pub = Publisher(temp_package)
    with pytest.raises(PublishError, match="Git command failed"):
        pub.check_git_clean()


@patch('subprocess.run')
def test_git_commit_and_tag(mock_run, temp_package):
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    pub = Publisher(temp_package)
    pub.git_commit_and_tag("1.2.4", "Custom message")
    
    # Check git add was called
    assert any("git" in str(call) and "add" in str(call) for call in mock_run.call_args_list)


@patch('subprocess.run')
def test_publish_dry_run(mock_run, temp_package):
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
    pub = Publisher(temp_package)
    
    version = pub.publish("patch", dry_run=True)
    
    assert version == "1.2.4"
    # Verify no actual changes were made
    assert pub.get_current_version() == "1.2.3"


def test_str_method(temp_package):
    pub = Publisher(temp_package)
    assert str(pub) == "testpkg"


@patch('subprocess.run')
def test_publish_rollback_on_push_failure(mock_run, temp_package):
    """Test that git changes are rolled back if push fails"""
    def side_effect(*args, **kwargs):
        cmd = args[0]
        if "push" in cmd:
            return Mock(returncode=1, stdout="", stderr="push failed")
        return Mock(returncode=0, stdout="", stderr="")
    
    mock_run.side_effect = side_effect
    pub = Publisher(temp_package)
    
    with pytest.raises(PublishError, match="Git push failed.*rolled back"):
        pub.publish("patch", skip_pypi=True)
    
    # Verify rollback commands were called
    calls = [str(call) for call in mock_run.call_args_list]
    assert any("tag" in call and "-d" in call for call in calls)
    assert any("reset" in call and "--hard" in call for call in calls)


@patch('subprocess.run')
def test_publish_pypi_failure_with_recovery_instructions(mock_run, temp_package):
    """Test that helpful recovery instructions are provided if PyPI upload fails"""
    def side_effect(*args, **kwargs):
        cmd = args[0]
        if "twine" in cmd:
            return Mock(returncode=1, stdout="", stderr="upload failed")
        return Mock(returncode=0, stdout="", stderr="")
    
    mock_run.side_effect = side_effect
    pub = Publisher(temp_package)
    
    with pytest.raises(PublishError, match="PyPI upload failed"):
        pub.publish("patch")


@patch('subprocess.run')
def test_check_git_remote_missing(mock_run, temp_package):
    """Test that missing git remote is detected"""
    mock_run.return_value = Mock(returncode=1, stdout="", stderr="fatal: No such remote")
    pub = Publisher(temp_package)
    with pytest.raises(PublishError, match="No git remote 'origin' configured"):
        pub.check_git_remote()


@patch('subprocess.run')
def test_check_git_remote_exists(mock_run, temp_package):
    """Test that existing git remote passes check"""
    mock_run.return_value = Mock(returncode=0, stdout="https://github.com/user/repo.git", stderr="")
    pub = Publisher(temp_package)
    pub.check_git_remote()  # Should not raise
