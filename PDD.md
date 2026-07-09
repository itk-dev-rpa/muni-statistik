# PDD — Muni-statistik (boost.ai Statistics API v2 → SQL Server)

> Process Design Document for ITK-RPA-robotten der indsamler statistik på Aarhus
> Kommunes Muni-chatbot (boost.ai) til et aggregeret ledelsesinformationslag.
>
> **Status:** Udkast. Felter markeret **[UDFYLDES]** afklares med Andreas.
> Bygger på discovery-spike (Fase 0), Andreas' opdrag og ITK-RPA-skabelonen.

## 1. Formål & baggrund

Andreas (opgavestiller) ønsker faste KPI'er på Muni-samtalerne til ledelsesinformation.
Sporet er: hent **Statistics API v2** som JSON → normalisér til **fakta-/dimensionstabeller
i MS SQL Server** → **PowerBI** kobles på databasen (ikke direkte på API'et). Databasen er
mellemled til transformation, historik og strukturering.

**Export API v4 er bevidst fravalgt:** højere kompleksitet og større GDPR-risiko (kommer
tættere på egentligt samtaleindhold). Statistics API v2 leverer kun aggregerede tal,
fordelinger og frekvenser — ikke samtaleindhold.

## 2. Trigger & output

- **Trigger:** Scheduled (natlig) via OpenOrchestrator. Linear framework (intern arbejdshentning).
- **Input:** ingen — kørslen er **inkrementel** og henter fra vandmærket (sidste fuldførte dag)
  frem til i går, i ugevise chunks. På tom database backfiller den fra `BACKFILL_START` (feb 2025).
- **Genoptagelse:** vandmærket udledes af `meta_ingest_run` (seneste `to_date` med `status='done'`,
  `mode='incremental'`) — en fejlet/stoppet kørsel hentes automatisk næste gang.
- **Gap-fill:** en valgfri `{"from","to"}`-argument til `process()` genindlæser en bestemt periode
  (`mode='manual'`) uden at flytte vandmærket.
- **Output:** rækker i SQL Server-fakta-/dimensionstabeller + rå JSON i staging.
- **Idempotens:** upsert pr. (dato, kanal, kilde, evt. sub-dim) — genkørsel duplikerer ikke.

## 3. Systemer & adgang

| System | Rolle | Adgang |
|--------|-------|--------|
| boost.ai Statistics API v2 | Datakilde | OAuth2 client_credentials, IP-whitelisted |
| MS SQL Server | Datalager | Connection string i OO-constant `Chat Statistics Connection String` (SQLAlchemy-URL, trusted connection, ODBC Driver 17). Server `SRVSQLHOTEL05`, database `ChatUsageStats` |
| OpenOrchestrator | Kørsel, credentials, constants, logning | Connection via args |
| PowerBI | Rapportering (uden for robottens scope) | Kobles på SQL Server |

**boost.ai auth (bekræftet via spike):**
```
POST https://ddh.boost.ai/api/oauth2/v1/token
Content-Type: application/x-www-form-urlencoded
grant_type=client_credentials, client_id, client_secret, scope=analytics:v1
→ { access_token, expires_in: 3600, token_type: "bearer" }
```
- **Scope: `analytics:v1`** (ikke `statistics`/`export` — verificeret).
- Token lever 1 time → fornyes automatisk ved lange kørsler.
- Alle statistics-kald er `POST` med `Authorization: Bearer <token>` og et søgefilter i body
  med påkrævet `from_date`/`to_date` (ISO-8601 med tidszone; halvåbent interval `[from, to)`).

**Credentials/constants:** lokalt fra `.env`; i produktion fra OpenOrchestrator
(`get_credential`/`get_constant`). Navne defineres i `robot_framework/config.py`.

## 4. Proces (detaljerede trin)

1. `initialize`: valider konfiguration + credentials (fail-fast).
2. `process`: bestem interval (vandmærke→i går; eller `{"from","to"}`-argument) og del i ugevise chunks.
3. For hvert chunk (én `meta_ingest_run`), for hver KPI × kanal × kilde:
   a. `POST` til boost-endpointet med søgefilter (inkl. `is_voice` + evt. `visited_url_text`).
   b. Gem rå svar i `stg_raw_response`.
   c. Normalisér JSON → faktarækker (drop tomme null-rækker); stempl kanal/kilde/`run_id`.
   d. Upsert til SQL Server (idempotent).
4. Marker kørslen `done` (rykker vandmærket for inkrementelle chunks) og log resultat.

For tidsserier hentes pr. dag via `histogram/{stat}` med `group_by=day` (én række pr. dag),
så daglige tal er korrekte uanset om robotten kører bagud i tid.

## 5. KPI'er & endpoint-mapping (verificeret mod tenant)

Alle nedenstående gav **200 OK med reelle data** i spiken. **Aktivt udvalg** (kundegodkendt):
conversations/messages, human transfer, sentiment, conversation + message feedback,
**conversation insight** (via `conversation_review` — `conversation_quality` er tom i tenanten),
token usage, goals (started/completed) og intents.

**To filtre lægges på alle datapunkter:** kanal (voice/chat via `is_voice`) og kommune/kilde
(via `visited_url_text` + `dim_source`-opslag). Se datamodel §6.

| KPI | Endpoint | Centrale JSON-felter |
|-----|----------|----------------------|
| ⭐ Antal samtaler over tid | `histogram/message` `group_by=day` | `conversations`, `billable_conversations`, `messages`, `messages_bot`, `messages_customer`, `messages_human_chat`, `period` |
| ⭐ Virtuel agent vs. human chat | `distribution/human_chat` | `va_only`, `unassisted`, `assisted` |
| ⭐ Feedback (samtale) | `distribution/conversation_feedback` | `no_feedback`, `any_feedback`, `thumbs_up`, `thumbs_down`, `*_with_message`, `*_on_message` |
| Feedback (besked) | `distribution/message_feedback` | `thumbs_up`, `thumbs_down` |
| ⭐ Sentiment | `distribution/sentiment` | `sentiment_positive`, `sentiment_neutral`, `sentiment_negative` |
| Samtalekvalitet | `distribution/conversation_quality` | `solved`, `partially_solved`, `unsolved_in_scope`, `unsolved_out_of_scope`, `not_relevant` (+ `*_v2`-varianter) |
| ⭐ Mest anvendte intents | `frequency/predicted_intent` | `[id, intent_title, count]` |
| ⭐ Ukendte svar | `frequency/predicted_label` + filter `unknown_responses_only=true` | `[id, label_type, count]` |
| Device | `distribution/device` | `device_desktop`, `device_smartphone`, `device_tablet` |
| Source URL / brugeradfærd | `frequency/source_url`, `frequency/link`, `distribution/click` | `[id, source_url, count]` / klik-felter |
| ⭐ Goals + completion rate | `frequency/goals_started` + `frequency/goals_completed` | `[id, goal_title, value, count]` (rate = completed/started) |
| ⭐ Token usage | `aggregates/token_usage` | liste: `vendor`, `feature`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `counts`, `billing_model_name` |
| Varighed | `distribution/duration` | `average_conversation`, `average_user_interaction`, `average_human_chat_queue`, `conversations` |
| Authentication | `distribution/authentication` | `openid`, `saml1`, `saml2`, `user_token`, `voice_biometrics`, `custom_auth`, `no_authentication` |
| NLU-detaljer | `distribution/nlu_stats`, `distribution/nlu_statusboard` | mange `session__*`/`message__*`-tællere |

**Responsformer (3 typer):**
- `distribution/{stat}` → `{label, distribution: {felt: tal, ...}}`
- `frequency/{stat}` → `{label, headers: [...], values: [[...], ...]}`
- `histogram/{stat}` → `{label, histogram: [{...felter, period}, ...]}`
- `aggregates/token_usage` → liste af objekter

## 6. Datamodel (relationelt stjerneskema — implementeret i `schema.py`)

Korn = **dato × kanal × kilde**, daglig granularitet. Unik nøgle muliggør idempotent upsert.

**Dimensioner (seedede):**
- `dim_channel(channel)` — chat, voice.
- `dim_source(domain, municipality)` — opslag: registrerbart domæne → kommunenavn (udvidbar;
  ukendte domæner får domænet som label; `dendigitalehotline.dk` → "DDH-portal").

**Fakta (daglige; hver med `run_id`, `loaded_at`):** `fact_conversations_daily`,
`fact_human_transfer_daily`, `fact_sentiment_daily`, `fact_conversation_feedback_daily`,
`fact_message_feedback_daily`, `fact_conversation_insight_daily`, `fact_token_usage_daily`
(+ vendor/feature/model), `fact_goals_daily` (+ goal_id/metric), `fact_intents_daily` (+ intent_id),
`fact_human_chat_skill_daily` (+ skill_id — skill-navnet bærer kommune for voice).

**Kanal/kommune-note (verificeret mod live data):** Kommune via `source_url` virker for **chat**;
**voice** har intet source_url (telefon), så voice-kommune aflæses i stedet af `human_chat_skill`
(`Voice_Aarhus`…). `dim_source.is_total` markerer `(alle)`-totalen, som ikke må summes med
kommune-rækkerne (dobbelttælling; totalen inkluderer også portal/utagget trafik).

**Audit/staging:**
- `meta_ingest_run(run_id, started_at, finished_at, from_date, to_date, mode, ingest_version, status, rows_written, error)`.
- `stg_raw_response(id, run_id, kpi, channel, domain, from_date, to_date, fetched_at, payload_json)`.

Robotten opretter tabellerne on-demand via SQLAlchemy (`database.py`) i `ChatUsageStats` — samme
kode kører lokalt på SQLite. DDL-ejerskab / om et fast skema skal forvaltes af DBA: **[UDFYLDES]**.

## 7. Forretningsregler & fejlhåndtering

- **`BusinessError`** (stop, ingen retry): `403 ForbiddenIPWhitelist` (IP ikke whitelisted),
  `403 Insufficient scopes` / `400 invalid_scope` (forkert/manglende scope), manglende
  constants/credentials.
- **Transiente fejl** (timeout, 5xx, DB-deadlock): retry op til `MAX_RETRY_COUNT` (3) +
  error-screenshot på mail (`ERROR_EMAIL`-constant).
- **`422 HTTPValidationError`**: forkert søgefilter → behandles som programfejl (skal rettes i kode).
- Token udløbet midt i kørsel: `boost_client` fornyer automatisk.

## 8. Stop-betingelser

- Robotten kører ét interval pr. trigger og stopper når alle valgte stats er hentet og upsertet.
- Ved `BusinessError` stopper robotten uden retry (forudsætning fejlet).
- Ved `MAX_RETRY_COUNT` overskredet markeres processen fejlet (`FAIL_ROBOT_ON_TOO_MANY_ERRORS`).

## 9. GDPR-betragtning

Statistics API v2 leverer kun **aggregerede** tal/fordelinger/frekvenser — ikke samtaleindhold
eller personhenførbare data. `source_url` og `predicted_intent` er aggregerede counts.
Export API v4 (samtaleindhold) indgår **ikke**. Rå JSON i `stg_raw_response` indeholder derfor
heller ikke samtaleindhold. **[UDFYLDES: evt. opbevaringsperiode for staging.]**

## 10. Åbne punkter (afklares med Andreas)

1. **SQL Server:** ✅ afklaret — connection via OO-constant `Chat Statistics Connection String`
   (`SRVSQLHOTEL05` / `ChatUsageStats`, trusted connection). Tilbage: ejer DBA skemaet, eller opretter robotten tabeller?
2. **Backfill-horisont:** hvor langt tilbage henter første kørsel (fx 12 mdr.)?
3. **Endeligt KPI-udvalg** til første datamodel (jf. ⭐ i §5).
4. **Tidszone-konvention** for `from_date`/`to_date` (anbefaling: konsekvent `+02:00`/`+01:00` eller UTC).
5. **Opbevaringsperiode** for rå JSON i staging.
