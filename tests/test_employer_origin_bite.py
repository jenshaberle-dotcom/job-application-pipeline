from __future__ import annotations

import json

from src.connectors.employer_origin_bite import (
    BITE_API_ENDPOINT,
    BitePosting,
    bite_inventory_payload,
    bite_raw_detail_url,
    discover_bite_binding,
    filter_bite_postings,
    parse_bite_postings,
    parse_bite_runtime,
    prove_bite_raw_detail,
)


def _binding():
    return discover_bite_binding(
        page_url="https://employer.example/careers/jobs",
        html='''
        <script src="https://static.b-ite.com/jobs-api/loader-v1/api-loader-v1.min.js"></script>
        <div data-bite-jobs-api-listing="tenantx:tenantx-listing"></div>
        ''',
    )


def _runtime():
    binding = _binding()
    assert binding is not None
    javascript = '''
    const config={
      key:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      channel:0,
      locale:"de",
      page:{offset:0,num:1000},
      sort:{by:"endsOn",order:"desc"},
      filter:{"custom.homepage":{in:["tenantx"]}}
    };
    '''
    runtime = parse_bite_runtime(
        binding=binding,
        asset_url=binding.asset_url,
        javascript=javascript,
    )
    assert runtime is not None
    return runtime


def _posting(title: str = "Senior Data Engineer") -> BitePosting:
    return BitePosting(
        posting_id="abcdef0123456789",
        title=title,
        url="https://jobs.employer.example/jobposting/abcdef0123456789",
        apply_url="https://jobs.employer.example/jobposting/abcdef0123456789/apply",
        employer_name="Example GmbH",
        raw={"title": title, "keywords": ["Python", "Data Platform"]},
    )


def test_employer_page_uniquely_derives_customer_asset() -> None:
    binding = _binding()

    assert binding is not None
    assert binding.customer == "tenantx"
    assert binding.asset_name == "tenantx-listing"
    assert binding.asset_url == "https://cs-assets.b-ite.com/tenantx/jobs-api/tenantx-listing.min.js"


def test_binding_requires_loader_and_exactly_one_tenant() -> None:
    assert discover_bite_binding(
        page_url="https://employer.example/jobs",
        html='<div data-bite-jobs-api-listing="tenantx:listing"></div>',
    ) is None

    assert discover_bite_binding(
        page_url="https://employer.example/jobs",
        html='''
        <script src="https://static.b-ite.com/jobs-api/loader-v1/api-loader-v1.min.js"></script>
        <div data-bite-jobs-api-listing="tenantx:listing"></div>
        <div data-bite-jobs-api-listing="other:listing"></div>
        ''',
    ) is None


def test_customer_asset_derives_bounded_runtime_and_payload() -> None:
    runtime = _runtime()

    assert runtime.customer == "tenantx"
    assert runtime.page_num == 1000
    assert runtime.filter_key == "custom.homepage"
    payload = bite_inventory_payload(
        runtime=runtime,
        origin_url="https://employer.example/careers/jobs",
    )
    assert payload == {
        "key": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "channel": 0,
        "locale": "de",
        "sort": {"by": "endsOn", "order": "desc"},
        "origin": "https://employer.example/careers/jobs",
        "page": {"offset": 0, "num": 1000},
        "filter": {"custom.homepage": {"in": ["tenantx"]}},
    }
    assert BITE_API_ENDPOINT == "https://jobs.b-ite.com/api/v1/postings/search"


def test_runtime_rejects_asset_with_unrelated_tenant_filter() -> None:
    binding = _binding()
    assert binding is not None

    runtime = parse_bite_runtime(
        binding=binding,
        asset_url=binding.asset_url,
        javascript='''
        const config={key:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",channel:0,locale:"de",
        page:{offset:0,num:1000},sort:{by:"endsOn",order:"desc"},
        filter:{"custom.homepage":{in:["someone-else"]}}};
        ''',
    )

    assert runtime is None


def test_complete_inventory_is_queryable_locally_and_control_stays_empty() -> None:
    body = json.dumps(
        {
            "jobPostings": [
                {
                    "id": "a1",
                    "title": "Senior Data Engineer",
                    "url": "https://jobs.example.test/jobposting/a1",
                    "applyUrl": "https://jobs.example.test/jobposting/a1/apply",
                    "keywords": ["Python", "Platform"],
                    "employer": {"name": "Example GmbH"},
                },
                {
                    "id": "b2",
                    "title": "Finance Controller",
                    "url": "https://jobs.example.test/jobposting/b2",
                    "keywords": ["Finance"],
                },
            ],
            "page": {"offset": 0, "num": 1000},
        }
    )
    postings = parse_bite_postings(body, page_num=1000)

    assert postings is not None
    assert [item.posting_id for item in postings] == ["a1", "b2"]
    assert [item.posting_id for item in filter_bite_postings(postings, "Data Engineer")] == ["a1"]
    assert filter_bite_postings(postings, "qzxvplmn847362951") == ()


def test_inventory_at_page_cap_is_not_claimed_complete() -> None:
    body = json.dumps(
        {
            "jobPostings": [
                {"id": str(index), "title": f"Job {index}", "url": f"https://jobs.example.test/jobposting/{index}"}
                for index in range(2)
            ]
        }
    )

    assert parse_bite_postings(body, page_num=2) is None


def test_raw_detail_is_still_subject_to_unchanged_genuine_job_proof() -> None:
    posting = _posting()
    raw_url = bite_raw_detail_url(posting.url)
    assert raw_url is not None

    job = prove_bite_raw_detail(
        posting=posting,
        raw_url=raw_url,
        response_url=raw_url,
        status_code=200,
        raw_body=(
            "Senior Data Engineer. Job description. Your responsibilities include Python data platform work. "
            "Requirements include SQL and cloud engineering. Apply now for this job. " * 3
        ),
    )

    assert job is not None
    assert job.final_url == posting.url
    assert job.title == "Senior Data Engineer"
    assert job.proof_kind == "job_url_and_job_content"
    assert job.discovery_source == "bite_finite_inventory_raw_detail"


def test_raw_detail_rejects_wrong_host_or_non_job_content() -> None:
    posting = _posting()
    raw_url = bite_raw_detail_url(posting.url)
    assert raw_url is not None

    assert prove_bite_raw_detail(
        posting=posting,
        raw_url=raw_url,
        response_url="https://attacker.example/raw",
        status_code=200,
        raw_body="Job description and requirements " * 20,
    ) is None
    assert prove_bite_raw_detail(
        posting=posting,
        raw_url=raw_url,
        response_url=raw_url,
        status_code=200,
        raw_body="Company news and culture " * 20,
    ) is None
