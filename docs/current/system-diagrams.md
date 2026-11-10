# Current system diagrams

These diagrams describe responsibilities. Runtime arrows do not prove live acceptance.

## End-to-end Search Intelligence control surface

```mermaid
flowchart TD
    Sensor[Market sensors] --> Candidate[Employer candidates]
    Candidate --> Evidence[Origin and detail evidence]
    Evidence --> Gate[Validation and approval]
    Gate -->|authorized| Connector[Controlled connector]
    Gate -->|blocked| Review[Repair or operator review]
    Review --> Evidence
    Connector --> Bronze[Bronze raw records]
    Bronze --> Silver[Silver canonical jobs]
    Silver --> Product[Fit and ranking]
    Product --> UI[React Control Center]
```

## Product decisions

```mermaid
flowchart TD
    Jobs[Verified jobs] --> Fit[Candidate Fit]
    Facts[Approved private facts] --> Fit
    Jobs --> Affinity[Affinity view]
    Fit --> Filter[Hard filters]
    Filter --> Ranking[Ranking authority]
    Ranking --> Top[Top 5]
    Top --> Draft[Application preparation]
    Facts --> Draft
    Template[Approved template] --> Draft
    Draft --> Track[Application tracking]
```

Affinity is separately explained; no combined-score edge exists. Preparation is not sending.

## Learning and repair loops

```mermaid
flowchart TD
    Health[Health and yield evidence] --> Diagnose[Reusable gap diagnosis]
    Diagnose -->|evidence gap| Repair[Bounded repair]
    Diagnose -->|uncertain| Review[Operator review]
    Repair --> Validate[Validation]
    Review --> Validate
    Validate -->|supported| Health
    Validate -->|blocked| Diagnose
```

Health and yield are separate dimensions. Zero relevant jobs is not a technical failure.
Promotion Gatekeeper and Origin URL Detective describe discovery/evidence responsibilities,
not an autonomous approval loop.

## Runtime and presentation

```mermaid
flowchart TD
    Host[Windows WebView2 host] --> UI[React bundle]
    UI --> API[Local Python API]
    API --> DB[PostgreSQL]
    API --> Private[Private facts and documents]
    Update[Verified immutable release] --> Stage[Staged frozen target]
    Stage --> Consent[Operator consent]
    Consent --> Host
```

The installed updater owns transactional cutover/rollback. WSL supplies the private local
execution environment. Runtime identity, not checkout location, proves installed source.

## RCC assignment boundary

```mermaid
flowchart TD
    Demand[JAP workload demand] --> RCC[RCC admission and reservation]
    RCC --> Linux[General Linux member]
    RCC --> Windows[General Windows member]
    Linux --> Verify[Exact assignment verification]
    Windows --> Verify
    Verify --> Work[JAP workload]
    Work --> Cleanup[RCC result and cleanup]
    Cleanup --> RCC
```

JAP supplies requirements and exact product source; RCC chooses capacity and owns lifecycle.
No fixed members, cardinality or hosted fallback are implied.

## URL finder and factory integration

C4 container and component views for the reviewed candidate. Dashed paths are
not yet admitted production flows for these candidates.

### Container view (C2)

```mermaid
flowchart LR
  user["Jens / Christina\nNutzer und Abnahme"]
  employers["Arbeitgeber-Websites und ATS\nExternes System: HTTPS / XML / JSON / HTML"]
  providers["Tavily / Codex\nOptionale externe Eskalation, hier nicht aufgerufen"]
  github["GitHub\nQuellcode, Review und Sicherung"]
  rcc["RCC\nExternes Ausführungssystem: Aufträge, Leases, Isolation"]
  subgraph jap["JAP – Container-Sicht, Integrationsentwurf"]
    sensors["Sensor-/Census-Prozess\nPython: Arbeitgeber und beobachtete Metadaten"]
    worker["URL-Finder / Factory-Prüfprozess\nPython: Identität, ATS-Inhalt, Rezepte"]
    evidence[("Belegspeicher\nZeitstempel, Antwortinhalt, SHA-256")]
    registry[("Kandidaten-/Rezeptkatalog\nFachliche Daten, Zulassung separat")]
    db[("JAP PostgreSQL\nProduktstellen und Profile")]
    api["JAP Reader/API\nPython: profilgebundene Anzeige"]
    cc["Classic CC\nWindows / WebView2, GUI-Basis 1.2.7"]
    delivery["Produktiver Connector-Worker\nGetrennt zuzulassende Runtime"]
    sensors -->|"Arbeitgeber + Herkunft"| worker
    worker -->|"Prüfbelege"| evidence
    worker -->|"Noch inaktive Rezepte"| registry
    registry -.->|"Qualifikation und Zulassung offen"| delivery
    delivery -.->|"Produktive Übernahme offen"| db
    db -->|"Begrenzte Leseprojektion"| api
    api -->|"HTTP-Vertrag"| cc
  end
  user -->|"Profil / Review"| cc
  worker -->|"Begrenzte öffentliche GETs"| employers
  worker -.->|"Separate Budgetfreigabe"| providers
  rcc -.->|"Geplante Ausführung zugelassener Rezepte"| delivery
  github -.->|"Geprüfter Code; kein automatisches Deployment behauptet"| worker
  user -->|"Aktueller Operator-Prüflauf, kein Broker-Dispatch"| worker
```

### URL-Finder/Factory components (C3)

```mermaid
flowchart LR
  input["Sensor-/Census-Metadaten und Firmenverzeichnis\nExterne Eingaben zum Prüfprozess"]
  source["Arbeitgeber / ATS\nExterne öffentliche Websites"]
  store[("Belegspeicher\nOriginalantworten mit Beobachtungszeit")]
  output[("Inaktiver Rezeptkatalog\nKeine Produktionsregistrierung")]
  subgraph process["URL-Finder / Factory-Prüfprozess – C3-Komponentenentwurf"]
    hints["Hinweisnormalisierung\ndirectory_match / family_contracts"]
    transport["Begrenzter Lesetransport\nfield_transport / resume_transport"]
    identity["Arbeitgeber- und Delegationsnachweis\nidentity_contract / field_html"]
    parsers["ATS-Familienparser\nJOIN, Personio, Greenhouse, d.vinci, SmartRecruiters"]
    classify["Konkrete Stellenprobe\nAllgemeine Bewerbung getrennt zählen"]
    compiler["Generischer Factory-Compiler\njap_connector_factory / field_factory"]
    metrics["Ergebnis und Herkunft\nFester Nenner, Lücken, Budgets, alte/neue Belege"]
    hints --> transport
    transport --> identity
    identity -->|"Belegte Arbeitgeberzuordnung"| parsers
    parsers --> classify
    classify --> compiler
    identity --> metrics
    classify --> metrics
    compiler --> metrics
  end
  input --> hints
  transport -->|"HTTPS GET"| source
  store -->|"Wiederverwendung; Zeit bleibt erhalten"| transport
  transport -->|"Neue Antworten und Hashes"| store
  compiler -->|"Rezept + Stellenprobe; noch nicht zugelassen"| output
```
