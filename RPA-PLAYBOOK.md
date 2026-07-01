# RPA-Playbook — sådan laver vi en ny RPA fra en PDD

Standard "indgang" for ITK-RPA-projekter bygget på denne skabelon (OpenOrchestrator +
[itk_dev_shared_components](https://github.com/itk-dev-rpa/itk_dev_shared_components)).
Følg trinnene i rækkefølge, når en ny PDD skal automatiseres.

## De 10 trin

1. **Saml PDD op & forstå opgaven.** Udled trigger/output, anvendte systemer, de detaljerede
   trin, forgreninger, forretningsregler (hvad er en `BusinessError`?) og stop-betingelser.
   Noter alle åbne spørgsmål/uklarheder til fagpersonen.
2. **Undersøg referencer.** Find et lignende `itk-dev-rpa`-repo der bruger samme systemer (fx
   [rykker-borgere-ukendt-adresse](https://github.com/itk-dev-rpa/rykker-borgere-ukendt-adresse))
   og slå de nødvendige funktioner op i `itk_dev_shared_components`.
3. **Vælg framework & OpenOrchestrator-flow.** Linear (én kørsel / intern loop) vs. Queue
   (OpenOrchestrator-kø + separat job der fylder køen). Vælg i `robot_framework/__main__.py`,
   og beslut trigger-type (se afsnittet om OpenOrchestrator nedenfor).
4. **Definér config, credentials & constants** i `robot_framework/config.py`: queue-navn (hvis
   queue), credential-/constant-navne, KLE-numre, mappenavne, mail-emner, afdelings-/sagsbehandler-id'er.
5. **Implementér stubs:**
   - `robot_framework/initialize.py` — valider forudsætninger / log ind.
   - `robot_framework/reset.py` — `open_all`/`close_all`/`kill_all` (minimal hvis ren API-robot).
   - `robot_framework/process.py` — kernelogikken.
6. **Tilføj dependencies** i `pyproject.toml` (typisk `itk_dev_shared_components`).
7. **Fejlhåndtering.** Kast `BusinessError` ved forretningsregel-brud (stopper uden retry);
   andre fejl giver retry op til `MAX_RETRY_COUNT` + error-screenshot på mail.
8. **Test/dry-run** lokalt med test-args; overvej dry-run/mock-mønster før produktion.
9. **Lint:** `pylint`/`flake8` (CI kører automatisk på PR via `.github/workflows/Linting.yml`).
10. **Commit & PR** på en feature-branch.

## Skabelon-fakta

- Indgang: `python -m robot_framework` (via `main.py`, der bruger `uv`).
- `process(orchestrator_connection, queue_element=None)` — samme signatur for begge frameworks.
- Hent hemmeligheder: `orchestrator_connection.get_credential(name)` (`.username`/`.password`)
  og `orchestrator_connection.get_constant(name).value`.

## OpenOrchestrator — flow & begreber

[OpenOrchestrator](https://github.com/itk-dev-rpa/OpenOrchestrator) kører og styrer robotterne.
To dele: **Orchestrator** (administrér processer, køer, credentials, constants) og **Scheduler**
(kører på maskinen og starter robotter når en trigger udløses).

- **Robotten forbinder** via `OrchestratorConnection.create_connection_from_args()`. Args:
  `"<process navn>" "<connection string>" "<secret key>" "<arguments>"`.
- **Trigger-typer** (vælges når processen oprettes i Orchestrator):
  - **Single trigger** — kør én gang (manuelt/ad hoc). Passer ofte til Linear.
  - **Scheduled trigger** — cron-lignende tidsplan (fx hver nat). Passer til Linear, hvis
    arbejdsmængden hentes inde i `process()`.
  - **Queue trigger** — starter når der ligger elementer i en navngiven kø. Passer til Queue
    framework; kræver typisk et separat job der *fylder* køen.
- **Queue & queue elements:** arbejdsenheder (`get_next_queue_element`, `set_queue_element_status`).
- **Credentials & Constants:** hemmeligheder/konfiguration gemmes i Orchestrator, ikke i kode.

## itk_dev_shared_components — subpakker

Slå altid op her før der skrives ny integrationskode
([docs](https://itk-dev-rpa.github.io/itk-dev-shared-components-docs/)):

| Subpakke | System / formål |
|----------|-----------------|
| `kmd_nova` | KMD Nova sagssystem: sager, dokumenter, opgaver, noter, CPR-opslag. |
| `graph` | Microsoft Graph: auth + læs/flyt mails i delte postkasser, vedhæftninger, filer, SharePoint-sites. |
| `getorganized` | GetOrganized ESDH/dokumenthåndtering (SharePoint-baseret sagssystem). |
| `eflyt` | eFlyt (flyttemeldinger/folkeregister): login, søgning, sager, breve. |
| `sap` | SAP GUI: login, multi-session-håndtering, borgerkontakt. |
| `smtp` | Afsendelse af mail via SMTP. |
| `misc` | Hjælpefunktioner, fx CPR-validering og aldersberegning. |

### Nøgle-API: KMD Nova

- Auth: `from itk_dev_shared_components.kmd_nova.authentication import NovaAccess` → `NovaAccess(client_id, client_secret)`
- Sager (`kmd_nova.nova_cases`): `get_cases(nova_access, cpr=...)`, `add_case(case, nova_access)`, `set_case_state(...)`
- Dokumenter (`kmd_nova.nova_documents`): `upload_document(file, file_name, nova_access)` → `attach_document_to_case(case_uuid, document, nova_access)`
- Opgaver (`kmd_nova.nova_tasks`): `attach_task_to_case(case_uuid, task, nova_access)`
- Objekter (`kmd_nova.nova_objects`): `NovaCase`, `Task`, `Document`, `Caseworker`, `CaseParty`, `Department`

### Nøgle-API: Microsoft Graph

- Auth: `graph.authentication.authorize_by_username_password(username, password, *, client_id, tenant_id)` → `GraphAccess`
- Mail (`graph.mail`): `get_emails_from_folder(user, folder_path, graph_access)`, `Email.get_text()`,
  `get_email_as_mime(email, graph_access)`, `list_email_attachments(...)`, `get_attachment_data(...)`,
  `move_email(email, folder_path, graph_access)`
