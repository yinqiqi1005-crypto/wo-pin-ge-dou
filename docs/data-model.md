# Data model

## Ownership

- A Django user owns generation tasks and saved patterns.
- Every saved pattern belongs to exactly one user.
- A pattern can contain multiple immutable versions.
- A derived version can reference one parent version from the same pattern.

## Membership and quota

- `MembershipPlan` stores editable plan names, display prices, generation limits,
  priority, and enabled features.
- `MembershipSubscription` connects a registered user to the active plan.
- `GenerationQuotaPeriod` stores a snapshot of the user's current period limit,
  used count, and reserved count.
- `GenerationQuotaLedger` keeps an immutable audit trail for quota changes.
- Database constraints prevent used and reserved counts from exceeding the period
  limit.

## Generation

- `GenerationTask` is the durable task and state record.
- `ImageAnalysisResult` stores structured image analysis.
- `GenerationSettings` stores confirmed user inputs.
- `ModelCallLog` records provider, model, prompt version, duration, result, and cost.
- A task keeps a configuration snapshot so later admin changes do not alter work
  already in progress.

## Pattern

- `Palette` and `PaletteColor` expose editable product color data.
- `Pattern` is the user's saved work.
- `PatternVersion` stores the formal grid, material counts, settings, validation
  result, and derived files for one immutable version.

## Operations

`ConfigurationRevision` records configuration changes by namespace, key, and
version. Runtime services must take a configuration snapshot when a task begins.

