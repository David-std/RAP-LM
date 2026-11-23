# Documentation index

Documents are grouped by status. **Current** documents describe the implemented system and are kept in
sync with the code. **Design history** documents are the specifications of draft PR #10 that guided the
implementation; they remain for traceability of decisions and are superseded where a current document
covers the same topic.

## Current

| Topic | Document |
|---|---|
| Development control, incidents, measured metrics | [CONTROL_DESARROLLO.md](CONTROL_DESARROLLO.md) |
| Technical decisions and change requests (D-01 to D-10) | [DECISIONES_TECNICAS.md](DECISIONES_TECNICAS.md) |
| Read API contract (implemented) | [api/contract.md](api/contract.md) |
| Benchmark protocols v1 and v2 (preregistered) | [ml/benchmark-protocol.md](ml/benchmark-protocol.md), [ml/benchmark-protocol-v2.md](ml/benchmark-protocol-v2.md) |
| Benchmarking report | [benchmarking/BENCHMARKING.md](benchmarking/BENCHMARKING.md) |
| Test plan traced to the 30 requirements | [pruebas/plan_de_pruebas.md](pruebas/plan_de_pruebas.md) |
| User manual (HU-29) | [manual_usuario.md](manual_usuario.md) |
| Specialist validation instruments (WBS 4.5) | [validacion/](validacion/README.md) |
| WBS and quality-metric traceability | [delivery-traceability.md](delivery-traceability.md) |

## Design history (draft PR #10)

| Document | Superseded or complemented by |
|---|---|
| [architecture/architecture.md](architecture/architecture.md), [architecture/implementation-blueprint.md](architecture/implementation-blueprint.md) | Implemented C4 containers in `compose.yaml`, API in `apps/api`, pipeline in `pipelines/` and `ml/fused` |
| [architecture/decision-register.md](architecture/decision-register.md) | [DECISIONES_TECNICAS.md](DECISIONES_TECNICAS.md) |
| [architecture/migration-plan.md](architecture/migration-plan.md) | Executed: legacy synthetic provider removed (D-07) |
| [contracts/read-api.md](contracts/read-api.md) | [api/contract.md](api/contract.md) |
| [contracts/persistence-and-publication.md](contracts/persistence-and-publication.md) | `database/migrations`, `pipelines/publication` |
| [ml/analytical-protocol.md](ml/analytical-protocol.md) | [ml/benchmark-protocol.md](ml/benchmark-protocol.md) |
| [product-development-specification.md](product-development-specification.md) | Plan v1.6 and the current documents above |
| [data/](data/) (source qualification, representation and feature experiments, exposure strategy) | Research evidence of the P1 to P3 stages; the fused dataset is described in `pipelines/fusion` and the provenance catalog `data/catalog/provenance.json` |
