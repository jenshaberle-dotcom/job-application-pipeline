from __future__ import annotations

from src.search_intelligence.requirement_section_evidence import (
    extract_requirement_section_evidence,
)


def test_finanz_informatik_profile_section_excludes_page_chrome_and_other_sections() -> None:
    html = """
    <html><body>
      <header><a>News</a><a>Podcast</a><a>Events</a></header>
      <h2>Deine Aufgaben</h2>
      <ul><li>Digitalisierung der Bankenwelt vorantreiben</li></ul>
      <h2>Profil:</h2>
      <ul>
        <li>2-3 Jahre fachbezogene Berufserfahrung</li>
        <li>Erfahrungen im Softwareentwicklungsprozess und agilen Methoden</li>
        <li>Erfahrungen mit Firmenkunden und EBICS Zahlungsverkehr sind wünschenswert</li>
        <li>Eine Zertifizierung z. B. ISTQB Foundation Level ist von Vorteil</li>
      </ul>
      <h2>Klingt interessant?</h2>
      <p>Jetzt bewerben!</p>
      <footer>LinkedIn Datenschutz News</footer>
    </body></html>
    """

    evidence = extract_requirement_section_evidence(html)

    assert len(evidence.sections) == 1
    assert evidence.sections[0].heading == "Profil:"
    assert "2-3 Jahre fachbezogene Berufserfahrung" in evidence.text
    assert "agilen Methoden" in evidence.text
    assert "EBICS Zahlungsverkehr" in evidence.text
    assert "ISTQB Foundation Level" in evidence.text
    assert "Digitalisierung der Bankenwelt" not in evidence.text
    assert "Jetzt bewerben" not in evidence.text
    assert "Podcast" not in evidence.text
    assert "LinkedIn" not in evidence.text


def test_english_requirement_section_stops_before_benefits() -> None:
    html = """
    <html><body>
      <nav>Cookies Search Options</nav>
      <h2>Your responsibilities</h2>
      <p>Build scalable integration services.</p>
      <h2>What we're looking for</h2>
      <ul>
        <li>Experience with C#/.NET and Angular</li>
        <li>Knowledge of Azure and CI/CD pipelines</li>
      </ul>
      <h2>What we offer</h2>
      <p>Flexible working and employee events.</p>
    </body></html>
    """

    evidence = extract_requirement_section_evidence(html)

    assert len(evidence.sections) == 1
    assert "C#/.NET and Angular" in evidence.text
    assert "Azure and CI/CD pipelines" in evidence.text
    assert "Build scalable integration services" not in evidence.text
    assert "Flexible working" not in evidence.text
    assert "Cookies" not in evidence.text


def test_hannover_re_style_equipped_with_section_stops_before_offer() -> None:
    html = """
    <html><body>
      <h2>Your responsibilities</h2>
      <p>Analyse reinsurance portfolios and support international stakeholders.</p>
      <h2>You come equipped with</h2>
      <ul>
        <li>A degree in mathematics, statistics or a comparable discipline</li>
        <li>Experience with Python, SQL and actuarial modelling</li>
        <li>Strong analytical and communication skills</li>
      </ul>
      <h2>You can look forward to</h2>
      <p>International teams, flexible working and employee benefits.</p>
    </body></html>
    """

    evidence = extract_requirement_section_evidence(html)

    assert len(evidence.sections) == 1
    assert evidence.sections[0].heading == "You come equipped with"
    assert "mathematics" in evidence.text
    assert "Python, SQL" in evidence.text
    assert "actuarial modelling" in evidence.text
    assert "Analyse reinsurance portfolios" not in evidence.text
    assert "flexible working" not in evidence.text


def test_long_pseudo_heading_benefit_block_stops_requirement_capture() -> None:
    html = """
    <html><body>
      <p>What you bring:</p>
      <ul>
        <li>Experience with Python, SQL and CI/CD.</li>
        <li>Knowledge of distributed systems and data modelling.</li>
      </ul>
      <p>You can look forward to flexible working, e-learning opportunities, fitness
         training sessions, employee events, international collaboration and many
         further benefits across our worldwide locations and partner network.</p>
      <p>More employer boilerplate that must never become requirement evidence.</p>
    </body></html>
    """

    evidence = extract_requirement_section_evidence(html)

    assert len(evidence.sections) == 1
    assert "Python, SQL and CI/CD" in evidence.text
    assert "distributed systems" in evidence.text
    assert "e-learning" not in evidence.text
    assert "fitness" not in evidence.text.casefold()
    assert "boilerplate" not in evidence.text


def test_personio_style_profile_heading_can_be_pseudo_heading_paragraph() -> None:
    html = """
    <html><body>
      <h2>About the role</h2>
      <p>Design a virtual power plant.</p>
      <p>What you bring:</p>
      <ul>
        <li>Strong Go experience and knowledge of communication protocols</li>
        <li>Experience with IoT devices and edge systems</li>
      </ul>
      <p>Benefits:</p>
      <p>Remote-first collaboration and team events.</p>
    </body></html>
    """

    evidence = extract_requirement_section_evidence(html)

    assert len(evidence.sections) == 1
    assert evidence.sections[0].heading == "What you bring:"
    assert "Go experience" in evidence.text
    assert "communication protocols" in evidence.text
    assert "IoT devices" in evidence.text
    assert "Remote-first" not in evidence.text


def test_multiple_requirement_sections_are_combined_without_raw_html() -> None:
    html = """
    <html><body>
      <h2>Qualifikationen</h2>
      <p>Sehr gute SQL-Kenntnisse.</p>
      <h2>Ihre Kenntnisse</h2>
      <p>Erfahrung mit Power BI und Datenmodellierung.</p>
      <h2>Wir bieten</h2>
      <p>Ein modernes Büro.</p>
    </body></html>
    """

    evidence = extract_requirement_section_evidence(html)
    payload = evidence.canonical_payload()

    assert len(evidence.sections) == 2
    assert "SQL-Kenntnisse" in evidence.text
    assert "Power BI und Datenmodellierung" in evidence.text
    assert "modernes Büro" not in evidence.text
    assert payload["raw_html_persisted"] is False
    assert "<" not in evidence.text


def test_empty_or_unstructured_page_fails_closed_to_no_sections() -> None:
    evidence = extract_requirement_section_evidence(
        "<html><body><p>Welcome to our careers page.</p></body></html>"
    )

    assert evidence.sections == ()
    assert evidence.text == ""
    assert evidence.truncated is False
