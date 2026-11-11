# Layered architecture — details

Read this when: adding a layer folder, data class, gateway, fake or arch rule, or when the
architecture check fails. The 5 core rules are in SKILL.md §5; this file adds the detail.

Contents: 1. Layer matrix · 2. Rules in detail · 3. Folder layout · 4. Growing the code ·
5. Enforcement

Projects may rename the layer folders in `devflow.yml`, never change the rules.
Hexagonal/ports-and-adapters is deliberately NOT used: keep it to these layers.

## 1. Layer matrix

| Layer | Contains | May use | Never uses | Tested at |
|---|---|---|---|---|
| presentation | routes, controllers, UI screens, CLI commands, scheduled jobs | logic, models | data | integration (API), system (UI) |
| logic | services per feature (`QuoteService`): rules, validation, calculations, workflow steps | data, models | presentation, web/UI frameworks, DB or HTTP libraries | unit (data faked) |
| data | repositories, file readers, gateways to external APIs and the LLM | models, third-party libs | logic, presentation | integration |
| models | plain data classes, enums, error types | stdlib + the profile's `architecture.models_validation` library | any layer | unit |
| main | reads config, builds data objects, injects them into services, starts the app | everything | — (nothing imports `main`) | system |

## 2. Rules in detail

- **Thin presentation** — read input, call a service, render the result. A business decision
  in a route, screen or command moves to logic.
- **Pass-through services are fine** — for plain CRUD a service may just call the
  repository. Presentation still calls the service, never data directly. — keeps one path
  for rules added later.
- **Injection** — services get data objects through the constructor or parameters; only
  `main` constructs them.
- **One gateway per external service** — handles logging, timeouts, retries and cost.
  Nothing else talks to that service.
- **Data translates errors** — library exceptions (driver, HTTP client, SDK) are caught in
  data and re-raised as error types from `models`. — logic never imports a library to catch it.
- **Only models cross layers** — DB rows, HTTP requests and library objects stay in the
  layer that created them.
- **Config and secrets** — read only in `main`, passed down.
- **Fakes** — every data class has a fake in `tests/fakes/` with the same interface and
  scripted answers, errors included.
- **Contract tests** — one shared test suite per data interface runs against both the fake
  (unit) and the real class (integration; for external-service gateways: `live`). — fakes can't silently drift from reality.
- **Frontends use the same layers** — components (presentation) → state/hooks (logic) →
  API client (data). Components never call `fetch` directly.

## 3. Folder layout

Inside each layer, name files by feature so one story's code is easy to find:

```
src/
  presentation/   quotes_routes.*    papers_routes.*
  logic/          quote_service.*    paper_service.*
  data/           quote_repository.* llm_gateway.*   pdf_reader.*
  models/         quote.*            paper.*         errors.*
  main.*
tests/
  unit/  integration/  system/  live/  arch/  fakes/  contracts/
```

## 4. Growing the code

- A story is a thin vertical slice: usually one small change per layer, shipped together.
- Build bottom-up: models → logic (unit tests with fakes) → data (integration + contract
  tests) → presentation (integration/system tests) → wire in `main`.
- Start small: `logic/`, `models/`, `main` first; `data/` with the first DB/API call;
  `presentation/` with the first screen or endpoint.
- A service or file grows too big → split it in its own CR, existing tests proving nothing broke.

## 5. Enforcement

`tests/arch/` (run by the fast gate) fails when a file imports a layer or library it must
not use.

| Ecosystem | Tool |
|---|---|
| Python | `import-linter` ("layers" + "forbidden" contracts) |
| JavaScript / TypeScript | `dependency-cruiser` or `eslint-plugin-boundaries` |
| Java / Kotlin | ArchUnit (`layeredArchitecture()`) |
| C# / .NET | NetArchTest |
| Go | `go-arch-lint` |
| Anything else | grep-based `scripts/check_architecture` |

**Single source of truth:** layer rules, libraries forbidden in logic, and the legacy
baseline live only in the tool's config file, whose path is `architecture.config` in
`devflow.yml`. Don't restate them anywhere else. The baseline only shrinks; adding an
entry needs the user's approval.
