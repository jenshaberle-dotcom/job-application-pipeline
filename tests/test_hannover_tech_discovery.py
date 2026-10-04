from scripts.discover_hannover_tech_hsh import is_region, is_tech, parse_company_blocks


HTML = """
<html><body>
<div>537 Firmen gefunden</div>
<div>IBS - Ingenieurbuero fuer Bahnbetriebssysteme GmbH</div>
<div>Berufsfeld(er)</div>
<div>Informationstechnologie</div><div>Softwarentwicklung/-kenntnisse</div>
<div>Anschrift</div><div>Lister Straße 15, 30163 Hannover</div>
<div>Beschreibung</div><div>Engineering</div>
<div>Mitarbeitende</div><div>1-50</div>
<div>Homepage</div><div>http://www.simu.de/</div>
<div>Remote Corp</div><div>Berufsfeld(er)</div><div>Informationstechnologie</div>
<div>Anschrift</div><div>10117 Berlin</div><div>Homepage</div><div>https://remote.example</div>
</body></html>
"""


def test_parse_company_blocks_keeps_structured_directory_evidence():
    rows = parse_company_blocks(HTML)
    assert rows[0]["company_name"] == "IBS - Ingenieurbuero fuer Bahnbetriebssysteme GmbH"
    assert rows[0]["website"] == "http://www.simu.de/"
    assert "Informationstechnologie" in rows[0]["fields"]


def test_region_and_tech_selection_are_explicit():
    assert is_region("Lister Straße 15, 30163 Hannover")
    assert not is_region("10117 Berlin")
    assert is_tech(["Informationstechnologie"])
    assert not is_tech(["Gesundheit & Soziale Dienste"])
