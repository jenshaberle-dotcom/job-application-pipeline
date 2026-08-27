from __future__ import annotations

from src.search_intelligence.client_code_api_delegation import (
    client_code_delegated_response_host,
    explicit_client_code_api_get_delegation,
)


PAGE = "https://www.example.com/careers/jobs"
ROUTE = "https://www.example.com/_next/static/chunks/pages/careers/jobs-abc.js"
APP = "https://www.example.com/_next/static/chunks/pages/_app-def.js"


def _route(*, method: str = "get", path: str = "/career/api-v1/get-all-jobs") -> str:
    return (
        "var b=t(63016);"
        f"client.{method}(`${{(0,b.S)()}}{path}`).then(handle);"
    )


def _module(*, base: str = "https://api.example.com", export: str = "S") -> str:
    return (
        '1:(e,t,r)=>{"use strict"},'
        '63016:(e,t,r)=>{"use strict";'
        f'r.d(t,{{{export}:()=>n}});'
        f'let n=()=>"{base}"'
        '},66184:(e,t,r)=>{"use strict"}'
    )


def test_resolves_one_explicit_same_host_get_api_delegation() -> None:
    delegation = explicit_client_code_api_get_delegation(
        page_url=PAGE,
        route_script_url=ROUTE,
        route_script_body=_route(),
        module_scripts=((APP, _module()),),
    )

    assert delegation is not None
    assert delegation.request_method == "GET"
    assert delegation.endpoint_path == "/career/api-v1/get-all-jobs"
    assert delegation.api_base_url == "https://api.example.com"
    assert delegation.api_url == "https://api.example.com/career/api-v1/get-all-jobs"
    assert delegation.api_host == "api.example.com"
    assert delegation.module_id == "63016"
    assert delegation.export_name == "S"
    assert (
        client_code_delegated_response_host(
            delegation,
            allowed_page_hosts=("www.example.com",),
        )
        == "api.example.com"
    )


def test_bjak_observed_minified_shape_is_supported_without_company_special_case() -> None:
    route_body = (
        'b=t(63016),O=(0,h.useCallback)(async()=>{'
        'let e=(await j.GP.get(`${(0,b.S)()}/career/api-v1/get-all-jobs`)).data.data;'
        'y(e),T(e)},[])'
    )
    module_body = (
        '(e,{pages:t})=>t.length,'
        '63016:(e,t,r)=>{"use strict";r.d(t,{S:()=>n});'
        'let n=()=>"https://be.example.test"},'
        '66184:(e,t,r)=>{"use strict"}'
    )

    delegation = explicit_client_code_api_get_delegation(
        page_url="https://example.test/en/career/jobs",
        route_script_url=(
            "https://example.test/_next/static/chunks/pages/career/jobs-123.js"
        ),
        route_script_body=route_body,
        module_scripts=(
            (
                "https://example.test/_next/static/chunks/pages/_app-456.js",
                module_body,
            ),
        ),
    )

    assert delegation is not None
    assert delegation.api_url == "https://be.example.test/career/api-v1/get-all-jobs"
    assert delegation.api_host == "be.example.test"


def test_recognition_does_not_grant_authority_when_page_host_is_not_allowed() -> None:
    delegation = explicit_client_code_api_get_delegation(
        page_url=PAGE,
        route_script_url=ROUTE,
        route_script_body=_route(),
        module_scripts=((APP, _module()),),
    )

    assert delegation is not None
    assert (
        client_code_delegated_response_host(
            delegation,
            allowed_page_hosts=("other.example.com",),
        )
        is None
    )


def test_cross_host_route_script_is_not_evidence() -> None:
    assert (
        explicit_client_code_api_get_delegation(
            page_url=PAGE,
            route_script_url="https://cdn.example.net/jobs.js",
            route_script_body=_route(),
            module_scripts=((APP, _module()),),
        )
        is None
    )


def test_cross_host_module_script_is_not_evidence() -> None:
    assert (
        explicit_client_code_api_get_delegation(
            page_url=PAGE,
            route_script_url=ROUTE,
            route_script_body=_route(),
            module_scripts=(("https://cdn.example.net/_app.js", _module()),),
        )
        is None
    )


def test_post_call_does_not_create_get_delegation() -> None:
    assert (
        explicit_client_code_api_get_delegation(
            page_url=PAGE,
            route_script_url=ROUTE,
            route_script_body=_route(method="post"),
            module_scripts=((APP, _module()),),
        )
        is None
    )


def test_non_job_endpoint_does_not_delegate_api_host() -> None:
    assert (
        explicit_client_code_api_get_delegation(
            page_url=PAGE,
            route_script_url=ROUTE,
            route_script_body=_route(path="/api-v1/content-feed"),
            module_scripts=((APP, _module()),),
        )
        is None
    )


def test_dynamic_export_value_fails_closed() -> None:
    dynamic_module = (
        '63016:(e,t,r)=>{"use strict";r.d(t,{S:()=>n});'
        'let n=()=>window.API_BASE}'
    )

    assert (
        explicit_client_code_api_get_delegation(
            page_url=PAGE,
            route_script_url=ROUTE,
            route_script_body=_route(),
            module_scripts=((APP, dynamic_module),),
        )
        is None
    )


def test_ambiguous_module_import_binding_fails_closed() -> None:
    route = (
        "var b=t(63016);"
        "b=t(63017);"
        "client.get(`${(0,b.S)()}/career/api-v1/get-all-jobs`)"
    )

    assert (
        explicit_client_code_api_get_delegation(
            page_url=PAGE,
            route_script_url=ROUTE,
            route_script_body=route,
            module_scripts=((APP, _module()),),
        )
        is None
    )


def test_competing_module_definitions_fail_closed() -> None:
    other = "https://www.example.com/_next/static/chunks/other.js"

    assert (
        explicit_client_code_api_get_delegation(
            page_url=PAGE,
            route_script_url=ROUTE,
            route_script_body=_route(),
            module_scripts=(
                (APP, _module(base="https://api-one.example.com")),
                (other, _module(base="https://api-two.example.com")),
            ),
        )
        is None
    )


def test_query_bearing_or_protocol_relative_endpoint_fails_closed() -> None:
    for path in (
        "/career/api-v1/get-all-jobs?tenant=example",
        "//api.example.com/career/jobs",
    ):
        assert (
            explicit_client_code_api_get_delegation(
                page_url=PAGE,
                route_script_url=ROUTE,
                route_script_body=_route(path=path),
                module_scripts=((APP, _module()),),
            )
            is None
        )
