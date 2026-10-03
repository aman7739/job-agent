"""Unit tests for user profile validation, strict schema, and loading."""

from pathlib import Path
import pytest
from pydantic import ValidationError
from job_digest.profile import load_profile_from_file, parse_profile_yaml, UserProfile


def test_profile_example_yaml_loads_cleanly():
    """Verify that profile.example.yaml adheres strictly to UserProfile schema."""
    example_path = Path(__file__).resolve().parent.parent / "profile.example.yaml"
    profile = load_profile_from_file(example_path)

    assert isinstance(profile, UserProfile)
    assert profile.version == 3
    assert profile.education.batch_year == 2027
    assert len(profile.target_roles) >= 40
    assert len(profile.skills) >= 25
    assert "telegram" in profile.digest.channels
    assert "email" in profile.digest.channels


def test_missing_required_field_fails_loudly():
    """Verify that missing a required field (e.g., education.batch_year) fails with clear error."""
    yaml_content = """
version: 3
user:
  name: "Candidate"
  email: "candidate@example.com"
education:
  degree: "B.Tech"
  field: "Computer Science"
  # Missing batch_year
target_roles: ["Software Engineer"]
skills:
  - name: "Python"
"""
    with pytest.raises(ValidationError) as exc_info:
        parse_profile_yaml(yaml_content)

    errors = exc_info.value.errors()
    assert any("batch_year" in str(err["loc"]) for err in errors)


def test_typo_or_unknown_key_rejected():
    """Verify that strict schema forbids unknown keys (catches typos immediately)."""
    yaml_content = """
version: 3
user:
  name: "Candidate"
  email: "candidate@example.com"
education:
  degree: "B.Tech"
  field: "Computer Science"
  batch_year: 2027
target_roles: ["Software Engineer"]
skills:
  - name: "Python"
unknown_typo_key: "some value"
"""
    with pytest.raises(ValidationError) as exc_info:
        parse_profile_yaml(yaml_content)

    err_str = str(exc_info.value)
    assert "unknown_typo_key" in err_str
    assert "extra_forbidden" in err_str or "Extra inputs are not permitted" in err_str


def test_nested_typo_rejected():
    """Verify that typos inside nested objects are also forbidden."""
    yaml_content = """
version: 3
user:
  name: "Candidate"
  email: "candidate@example.com"
education:
  degree: "B.Tech"
  field: "Computer Science"
  batch_year: 2027
  typo_field: true
target_roles: ["Software Engineer"]
skills:
  - name: "Python"
"""
    with pytest.raises(ValidationError) as exc_info:
        parse_profile_yaml(yaml_content)

    err_str = str(exc_info.value)
    assert "typo_field" in err_str


def test_list_deduplication():
    """Verify target roles, preferred cities, and aliases are deduplicated."""
    yaml_content = """
version: 3
user:
  name: "Candidate"
  email: "candidate@example.com"
education:
  degree: "B.Tech"
  field: "Computer Science"
  batch_year: 2027
target_roles:
  - "Software Engineer"
  - "software engineer"
  - "Backend Developer"
skills:
  - name: "Python"
    aliases: ["python3", "PYTHON3", "py"]
locations:
  preferred_cities:
    - "Noida"
    - "noida"
    - "Pune"
"""
    profile = parse_profile_yaml(yaml_content)
    assert len(profile.target_roles) == 2
    assert profile.target_roles == ["Software Engineer", "Backend Developer"]

    py_skill = next(s for s in profile.skills if s.name == "Python")
    assert len(py_skill.aliases) == 2  # python3 and py

    assert len(profile.locations.preferred_cities) == 2
    assert profile.locations.preferred_cities == ["Noida", "Pune"]


def test_invalid_channel_rejected():
    """Verify that non-supported channels fail validation."""
    yaml_content = """
version: 3
user:
  name: "Candidate"
  email: "candidate@example.com"
education:
  degree: "B.Tech"
  field: "Computer Science"
  batch_year: 2027
target_roles: ["Software Engineer"]
skills:
  - name: "Python"
digest:
  channels:
    - "telegram"
    - "whatsapp" # invalid
"""
    with pytest.raises(ValidationError) as exc_info:
        parse_profile_yaml(yaml_content)

    assert "whatsapp" in str(exc_info.value)
