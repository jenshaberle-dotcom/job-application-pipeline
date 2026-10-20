import pytest
from src.connectors.employer_origin_acquisition_v4 import acquire_genuine_job_pages


@pytest.mark.parametrize("genuine", [True, False])
def test_empty_navigation_uses_same_host_sitemap_without_weakening_proof(genuine):
    root="https://employer.example/"
    detail=root+"jobs/platform-engineer-12345"
    body=(
        '<html><title>Platform Engineer</title><script type="application/ld+json">'
        '{"@type":"JobPosting","title":"Platform Engineer","description":"Build services",'
        '"hiringOrganization":{"@type":"Organization","name":"Employer"}}'
        '</script></html>'
    ) if genuine else "<html><title>Company news</title><p>Our next company party.</p></html>"
    pages={root:"<html>Welcome to Employer</html>",
           root+"sitemap.xml":f"<urlset><url><loc>{detail}</loc></url><url><loc>https://other.example/jobs/1</loc></url></urlset>",
           detail:body}
    calls=[]
    def fetch(url):
        calls.append(url)
        return pages[url],url,200
    jobs,_=acquire_genuine_job_pages(listing_url=root,allowed_hosts=("employer.example",),
                                   known_detail_urls=(),fetcher=fetch,max_followup_requests=2)
    assert calls==[root,root+"sitemap.xml",detail]
    assert bool(jobs) is genuine


def test_sitemap_index_does_not_expand_unboundedly():
    calls=[]
    def fetch(url):
        calls.append(url)
        return ("<html>Home</html>" if len(calls)==1 else
                "<sitemapindex><sitemap><loc>https://other.example/map.xml</loc></sitemap></sitemapindex>"),url,200
    jobs,_=acquire_genuine_job_pages(listing_url="https://employer.example/",
          allowed_hosts=("employer.example",),known_detail_urls=(),fetcher=fetch,max_followup_requests=2)
    assert not jobs and len(calls)==2
