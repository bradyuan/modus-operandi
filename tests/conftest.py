import pytest

from mo.store import Profile


@pytest.fixture
def mo_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MO_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def profile(mo_home):
    return Profile("default")


def write_exemplar(profile: Profile, register: str, name: str, text: str) -> None:
    folder = profile.root / "exemplars" / register
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text(text)


def write_rules(profile: Profile, rules: list[dict]) -> None:
    import yaml

    profile.root.mkdir(parents=True, exist_ok=True)
    (profile.root / "profile.yaml").write_text(yaml.safe_dump({"rules": rules}))
