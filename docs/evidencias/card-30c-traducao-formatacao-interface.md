# Card 30 (complemento 2) — Tradução e formatação de exibição na interface

**Branch/PR:** `feature/frontend-i18n-formatting`
**Motivação:** pedido explícito do usuário — esclarecer o campo "Issue # (opcional)" e traduzir/formatar valores exibidos na interface mínima (card 30).

## Esclarecimento: campo "Issue # (opcional)"

Espera o **número de uma Issue existente** no repositório GitHub configurado em `GITHUB_REPO` (`.env` — por padrão, o próprio repositório deste projeto, `scha-chan/radar-impact-agent`, ver `.env.example`). Se preenchido, `publish_comment` (`src/mcp_server/tools/publish_comment.py`, card 10) tenta publicar o parecer como comentário real nessa Issue via API do GitHub, exigindo `GITHUB_TOKEN` válido com permissão de escrita. Se deixado em branco (ou sem `GITHUB_TOKEN`/`GITHUB_REPO` configurados), o parecer é gravado em `audit/dry_run/{session_id}.md` em vez de publicado — o mesmo comportamento de `DRY_RUN=true`.

## O que foi implementado

- `src/api/static/ts/i18n.ts` (novo) — três funções puras, sem estado:
  - `translateRiskLevel(level)` — `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` (literais do backend, `src/domain/risk.py`) → `Baixo`/`Médio`/`Alto`/`Crítico`.
  - `translateDecision(decision)` — os sete literais de decisão da trilha de auditoria (`src/observability/audit.py`, card 20) → frases em português (`ESCALATED` → "Escalado para aprovação", `APPROVED_PUBLISHED` → "Aprovado e publicado", etc.).
  - `formatTimestamp(isoTimestamp)` — timestamp ISO-8601 UTC (formato que o backend grava, `datetime.isoformat()`) → `DD/MM/AAAA hh:mm:ss` no fuso horário local do navegador.
- `src/api/static/ts/app.ts` — os três pontos de exibição atualizados: o painel de resultado da análise (`risco`), os cards de aprovação pendente (`risco` e `escalado em`), e a tabela de auditoria (`Decisão`, `Risco`, `Timestamp`).

## Por que um módulo separado (`i18n.ts`), não funções soltas em `app.ts`

Tradução e formatação são preocupações de apresentação, não de orquestração — `app.ts` já importa de `api.ts`/`dom.ts`/`types.ts`, cada um com uma responsabilidade; adicionar mais um módulo pequeno e focado mantém esse padrão em vez de inflar `app.ts` com mapas de string. Também facilita achar/estender as traduções no futuro (ex.: um segundo idioma) sem tocar na lógica de renderização.

## Decisão: só exibição, nunca o valor enviado de volta

`decision` em `ApprovalDecisionRequest` (o corpo de `POST /approvals/{session_id}`) continua `"APPROVED"`/`"REJECTED"` — os botões Aprovar/Rejeitar já usavam esses literais diretamente (nunca passavam pela tradução) e continuam assim. Só o que é **lido** da API para exibição passa por `i18n.ts`; nada que é **enviado** à API é traduzido — evita o bug clássico de "traduzir e esquecer de reverter antes de mandar pro backend".

## Testado no navegador com Ollama real

Reproduzido o fluxo completo (submissão → escalação → aprovação → auditoria) via Browser pane:

- Painel de resultado: `risco: Baixo` (era `LOW`).
- Card de aprovação pendente: `risco: Baixo`, `escalado em 26/08/2026 21:20:17`.
- Tabela de auditoria: `Escalado para aprovação` → `Aprovado e publicado`, timestamps no formato `DD/MM/AAAA hh:mm:ss`.

Nenhum erro no console durante o fluxo.

## Testes

`pytest -q`: 203 passed, 3 skipped (Ollama real), 99,18% de cobertura, sem alteração (mudança restrita ao frontend). `ruff check .`/`ruff format --check .`: sem apontamentos. `npx tsc --noEmit`: sem erro de tipo.
