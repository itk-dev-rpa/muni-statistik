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
- **Input:** datointerval. Default = gårsdagen (`[i går 00:00, i dag 00:00)`). Backfill via argument.
- **Output:** rækker i SQL Server-fakta-/dimensionstabeller + rå JSON i staging.
- **Idempotens:** upsert pr. (stat, dato) — genkørsel af samme interval må ikke duplikere.

## 3. Systemer & adgang

| System | Rolle | Adgang |
|--------|-------|--------|
| boost.ai Statistics API v2 | Datakilde | OAuth2 client_credentials, IP-whitelisted |
| MS SQL Server | Datalager | **[UDFYLDES: server / database / login]** |
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

1. `initialize`: hent OAuth2-token (fail-fast ved auth/scope/whitelist-fejl); test DB-forbindelse.
2. `process`: bestem datointerval (gårsdag ved nightly; backfill-interval ved argument).
3. For hver valgt stat (jf. §5):
   a. `POST` til boost-endpointet med søgefilter for intervallet.
   b. Gem rå svar i `stg_raw_response`.
   c. Normalisér JSON → fakta-/dimensionsrækker.
   d. Upsert til SQL Server (idempotent pr. stat+dato).
4. Log resultat (antal rækker pr. stat) til OpenOrchestrator.

For tidsserier hentes pr. dag via `histogram/{stat}` med `group_by=day` (én række pr. dag),
så daglige tal er korrekte uanset om robotten kører bagud i tid.

## 5. KPI'er & endpoint-mapping (verificeret mod tenant)

Alle nedenstående gav **200 OK med reelle data** i spiken. Endeligt KPI-udvalg til
*første* datamodel: **[UDFYLDES med Andreas — "få stabile KPI'er"]**. Forslag til
første bølge markeret ⭐.

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

## 6. Datamodel (forslag — færdiggøres med endeligt KPI-udvalg)

Korn = **pr. dag pr. stat**. Unik nøgle muliggør idempotent upsert.

**Staging:**
- `stg_raw_response(id, stat, from_date, to_date, fetched_at, payload_json)`

**Dimensioner:** `dim_date`, `dim_stat_type`, `dim_intent`, `dim_device`, `dim_source_url`, `dim_goal`, `dim_model`.

**Fakta (pr. dag):**
- `fact_conversations_daily` (conversations, billable, messages, bot/customer/human_chat)
- `fact_human_chat_daily` (va_only, unassisted, assisted)
- `fact_feedback_daily` (conversation + message feedback)
- `fact_sentiment_daily` (positive/neutral/negative)
- `fact_quality_daily` (kvalitetslabels)
- `fact_intent_freq_daily` (intent_id, count)
- `fact_goals_daily` (goal_id, started, completed)
- `fact_token_usage_daily` (model, prompt/completion/total tokens, counts)

DDL-ejerskab og om databasen allerede findes: **[UDFYLDES]**.

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

1. **SQL Server:** server, database, login; findes skema/DB, eller leverer vi DDL? Hvem ejer skemaændringer?
2. **Backfill-horisont:** hvor langt tilbage henter første kørsel (fx 12 mdr.)?
3. **Endeligt KPI-udvalg** til første datamodel (jf. ⭐ i §5).
4. **Tidszone-konvention** for `from_date`/`to_date` (anbefaling: konsekvent `+02:00`/`+01:00` eller UTC).
5. **Opbevaringsperiode** for rå JSON i staging.
