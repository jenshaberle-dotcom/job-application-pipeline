# Hannover Browser-Agent – isolierter A/B-Test

Branch: experiment/hannover-browser-agent-discovery-20261108

Ziel: Ein LLM-steuerbarer Browser-Agent wird gegen die bislang berichtete
Trefferquote von höchstens 20 % brauchbaren Jobquellen getestet. Die 20 %
sind eine Nutzerbeobachtung, kein in diesem Branch neu gemessener Wert.

## Arbeitsweise

Der Agent verwendet die Brave Web Search API als Suchindex und einen lokalen,
echten Playwright-/Chromium-Browser zum Lesen und Verfolgen der Ergebnisse.
Das Modell wählt selbst Suchbegriffe, Seiten und Kandidaten. Es gibt keine
neuen geratenen ATS-Slugs. Das ist eine text-/DOM-basierte Browser-Agentik,
noch keine Screenshot-/Maussteuerung. Der ChatGPT-Work-Browser ist nicht
direkt als lokale JAP-Bibliothek nutzbar.

Der separate Validator ignoriert Modellbehauptungen: Mindestens eine echte
Jobanzeige plus plausibel unabhängig belegte Arbeitgeberzugehörigkeit sind
für VERIFIED_ACTIVE erforderlich. Greenhouse und Lever werden durch die
vorhandenen JAP-Extractor-/Factory-Funktionen geprüft. Für andere Portale
ist eine JobPosting-Auszeichnung mit passender hiringOrganization und
korrespondierender Unternehmensdomain möglich; das ersetzt keinen Factory
Connector. Die Zustände JOB_FOUND_EMPLOYER_CLAIM_UNCORROBORATED und
SOURCE_VERIFIED_JOB_UNPROVEN verhindern voreilige Freigaben.

## Lokal installieren unter WSL2

In dem bereits vorhandenen JAP-Classic-Checkout:

    git fetch origin experiment/hannover-browser-agent-discovery-20261108
    git worktree add --detach ../jap-browser-agent-poc \
      origin/experiment/hannover-browser-agent-discovery-20261108
    cd ../jap-browser-agent-poc
    python3.12 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    python -m pip install -r requirements-browser-discovery-poc.txt
    python -m playwright install chromium
    python -m pytest -q tests/test_human_browser_discovery.py

Getrennte API-Zugänge sind erforderlich. Das ChatGPT-Abo stellt keine
OpenAI-API-Kosten oder Brave-Suchanfragen bereit. Keine API-Schlüssel
oder lokale Reports committen.

    export OPENAI_API_KEY="DEIN_OPENAI_API_KEY"
    export BRAVE_API_KEY="DEIN_BRAVE_API_KEY"

Genau eine Firma:

    python -m scripts.run_hannover_browser_agent \
      --company "enercity AG" \
      --website "https://www.enercity.de/" \
      --output runs/browser-agent-enercity

Oder echte akzeptierte Hannover-Census-Daten:

    python -m scripts.run_hannover_browser_agent \
      --census /ABSOLUTER/PFAD/hannover-census.json \
      --limit 5 \
      --output runs/browser-hannover-five

Nur bei einer zuvor tatsächlich geprüften (live/replay) Baseline:

    python -m scripts.run_hannover_browser_agent \
      --census /ABSOLUTER/PFAD/hannover-census.json \
      --baseline-report /ABSOLUTER/PFAD/registry-poc/report.json \
      --only-unresolved \
      --limit 20 \
      --output runs/browser-vs-old

Ein Registry-only-Report wird ausdrücklich nicht als vermeintlich 0 %
verifizierte Baseline akzeptiert. Die Firmen werden per company_key
abgeglichen. Die Daten bleiben als JSON im angegebenen lokalen runs/-Pfad.

## Akzeptanz

Als erste Stichprobe 30 Unternehmen anhand der bestehenden Census- und
Baseline-Ergebnisse stratifizieren: 10 bisher erfolgreich, 10 bekannte
aber vom Finder verpasste Portale, 10 schwierige unbekannte Fälle.
Nicht die ersten alphabetischen 30 als repräsentativ ausgeben.

Messen: Candidate Recall@4, verifizierte aktive Arbeitgeberquellen,
falsche Arbeitgeberzuordnungen, Factory-Definitionen, Bearbeitungszeit,
Suche-Aufrufe und Modell-Token pro erfolgreich bestätigtem Unternehmen.

Ein Agent darf erst dann als Verbesserung gelten, wenn er zusätzliche
richtige Quellen findet, statt nur lockere Validierung anzuwenden.
Ziel für automatische Freigaben: mindestens 98 % Präzision auf manuell
geprüften Positiv- und Negativbeispielen.

## Grenzen

- Maximal 2 Suchanfragen, 8 Browserseiten, 10 Modellschritte und 4
  Kandidatennominierungen je Firma; max. 30 Firmen je Start.
- Public-HTTPS only, kein Login, keine Bewerbungen, kein CAPTCHA-Bypass,
  keine Downloads, keine Datenbank-/Scheduler-Änderung.
- Websites sind untrusted Input. Modell erhält nur read-only Toolzugriff.
- Der PoC-HTTP/DNS-Schutz ist kein vollständig DNS-rebinding-resistentes
  Sandboxing; für unbeaufsichtigte Massendurchläufe eine extern isolierte
  Browser-/Netzwerkumgebung verwenden.
- Robots- und Website-Nutzungsbedingungen sind zu beachten.
- JobPortal-URLs und Screenshots/Berichte nicht ungeprüft ins öffentliche
  Repository pushen.
- VERFIED_ACTIVE ist eine aktuelle Evidenz; ein gültiges Portal ohne Job
  kann korrekt sein, bleibt in diesem auf aktive Jobs ausgelegten PoC offen.
- Definition-only-Factory-Erfolg ist keine Runtime-Freigabe.

Stand: Alle Dateien sind remote gesichert. Eine echte Browser-/Modell-
Ausführung auf dem Nutzer-Host ist noch nicht erfolgt. Die Offline-Tests
müssen zunächst lokal ausgeführt werden.

## Alte 20-%-Baseline aus dem lokalen JAP übernehmen

Wenn der alte Finder keinen kompatiblen PoC-Report erzeugt, stattdessen
prüfbar eine CSV mit genau zwei Pflichtspalten exportieren:

    company_key,verified_active
    acme,1
    beta,0

Die Werte 1/0 dürfen nicht bloß HTTP-200-Erreichbarkeit ausdrücken, sondern
müssen den gleichen überprüften Arbeitgeber-/Jobquellenstandard repräsentieren.
Unbekannt bleibt unbekannt und darf nicht zu 0 umgedeutet werden.

    python -m scripts.run_hannover_browser_agent \\
      --census /ABSOLUTER/PFAD/hannover-census.json \\
      --baseline-report /ABSOLUTER/PFAD/old_finder_verified.csv \\
      --only-unresolved --limit 20 \\
      --output runs/human-browser-long-tail

Wichtig: Die Filterung nach nicht verifizierten Firmen findet statt, BEVOR
--limit angewandt wird. So startet der Agent auf echten Fehlfällen, nicht
zufällig nur den alphabetisch ersten Firmen.

Pilotdaten reichen nicht für einen statistisch engen Nachweis von 98 %
Precision. Die 30 Firmen sind ein Machbarkeits- und Fehleranalyseversuch;
für ein Produktions-Gate ist ein größerer blind geprüfter Holdout nötig.


## Standalone UI and repository hygiene companion

The separate **JAP_Browser_Scout_Standalone.zip** distributed with the
experiment contains a local-only HTTP dashboard (Python 3.12+, no extra
dependencies for synthetic demo), company/source/job cards, browser evidence,
Factory status, baseline-delta metrics and JSON export. It is a companion
artifact, **not** automatically installed in this repository.

After extracting the ZIP:

    cd JAP_Browser_Scout_Standalone
    ./run.sh

Open http://127.0.0.1:8765 and choose the explicitly labeled synthetic demo.

For a real browser experiment, activate the Python environment of the
*separate* experiment checkout and start:

    python server.py --repo /ABSOLUTE/PATH/TO/jap-browser-agent-poc

Never put API keys in UI fields; the runner reads OPENAI_API_KEY and
BRAVE_API_KEY from the host process environment. No databases or productive
sources are changed.

The ZIP includes a Git hygiene script which is read-only by default and
only allows reviewed, unchanged, **already merged** non-open-PR remote refs
to be deleted. That is distinct from user-unpublished source backup; do
not substitute it for the JAP Local Safety Guard.

For the full 2026-11-08 branch/PR inventory and consolidation blockers,
see docs/current/BRANCH_CONSOLIDATION_AUDIT_20261108.md. Both Classic and
Runtime already have delete_branch_on_merge=true. The sole-main/sole-experiment
branch target is **not completed** until divergent work is qualified and
consolidated; no high-risk branch deletes or mass merges were performed.

## Cross-sector Solution Architect cohort through Browser Scout

Optional --expanded-companies accepts the same sourced JSON/CSV employer seeds
as the Hannover Registry PoC. The old TECH Census remains the frozen baseline,
while a second profile-market segment adds cross-sector companies without
declaring them to have current jobs.

    python -m scripts.run_hannover_browser_agent \
      --census /ABSOLUTE/PATH/TO/HANNOVER_CENSUS.json \
      --expanded-companies \
        examples/hannover-tech-registry-poc/profile-market-expansion-hannover-example.json \
      --limit 10 \
      --output runs/browser-expanded-role-market

The illustrative expansion is not a complete regional market census.
Solution Architect / Lösungsarchitekt is an additional role-family signal,
not proof of a suitable vacancy. The standalone UI supports the same
optional cross-sector JSON/CSV path alongside the Census input.

Before a fair A/B comparison, ensure baseline company keys and validation
definitions match the exact experiment cohort.
