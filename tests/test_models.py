import pytest

from radar.models import canonical_key
from tests.conftest import repo


@pytest.mark.parametrize("url,key", [
    ("https://github.com/owner/repo", "gh:owner/repo"),
    ("https://github.com/OWNER/Repo/", "gh:owner/repo"),
    ("https://github.com/owner/repo.git", "gh:owner/repo"),
    ("https://github.com/owner/repo/blob/main/README.md", "gh:owner/repo"),
    ("https://www.github.com/owner/repo#readme", "gh:owner/repo"),
    ("https://github.com/orgs/foo/discussions/1", "url:github.com/orgs/foo/discussions/1"),
    ("https://github.com/trending/rust", "url:github.com/trending/rust"),
    ("https://arxiv.org/abs/2609.12345", "arxiv:2609.12345"),
    ("http://arxiv.org/abs/2609.12345v2", "arxiv:2609.12345"),
    ("https://arxiv.org/pdf/2609.12345", "arxiv:2609.12345"),
    ("https://example.com/post?utm_source=x&id=5", "url:example.com/post?id=5"),
    ("https://www.example.com/post/", "url:example.com/post"),
    ("https://example.com/a?b=2&a=1", "url:example.com/a?a=1&b=2"),
    ("", ""),
])
def test_canonical_key(url, key):
    assert canonical_key(url) == key


def test_merge_unions_sources_evidence_and_keeps_max_metrics():
    a = repo("x/y", "short", source="github_search", stars=100, starred_by=["alice"])
    b = repo("x/y", "a much longer description", source="github_starred",
             stars=150, starred_by=["bob"])
    a.merge(b)
    assert a.sources == {"github_search", "github_starred"}
    assert len(a.evidence) == 2
    assert a.metrics["stars"] == 150
    assert a.metrics["starred_by"] == ["alice", "bob"]
    assert a.summary == "a much longer description"


@pytest.mark.xfail(strict=True, reason="fixed in phase 1")
def test_merge_does_not_duplicate_evidence():
    a = repo("x/y", source="github_search")
    b = repo("x/y", source="github_search")
    a.merge(b)
    assert len(a.evidence) == 1


@pytest.mark.xfail(strict=True, reason="fixed in phase 1")
def test_merge_prefers_github_title_over_hn_headline():
    hn = repo("x/y", source="hackernews")
    hn.title = "Show HN: My cool thing"
    gh = repo("x/y", source="github_search")
    hn.merge(gh)
    assert hn.title == "x/y"
