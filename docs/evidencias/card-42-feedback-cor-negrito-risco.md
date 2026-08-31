# Card 42 — Feedback visual (cor + negrito) para o risco na interface

**Branch/PR:** `feature/frontend-risk-feedback-style`
**Motivação:** pedido explícito do usuário — criar um card de melhoria no board e aplicar cor de feedback + negrito ao valor de risco exibido no painel de resultado da análise (interface mínima, card 30).

## Card no board

Criado o item 42 ("Melhorias de UX na interface mínima (frontend)") no GitHub Projects (`project 1`, owner `scha-chan`), como `DraftIssue`, movido para `Em Andamento`. Agrupa este e futuros ajustes de UX que não fazem parte do escopo literal da PRD (cards 1-34) nem das extensões pós-rubrica (35-41).

## O que foi implementado

- `src/api/static/ts/i18n.ts` — nova função `riskLevelClass(level)`, paralela a `translateRiskLevel`: mapeia cada nível de risco (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`) para classes Tailwind de cor + `font-bold`:
  - `LOW` → verde (`text-emerald-700`)
  - `MEDIUM` → âmbar (`text-amber-700`)
  - `HIGH` → laranja (`text-orange-700`)
  - `CRITICAL` → vermelho (`text-red-700`)
  - `null`/desconhecido → cinza neutro (`text-stone-500`), consistente com o `"—"` de `translateRiskLevel`.
- `src/api/static/ts/app.ts` (`renderAnalyzeResult`) — a linha `risco` do `<dl>` de resultado passou a usar `riskLevelClass(result.risk_level)` como classe do `<dd>`, em vez da classe genérica `text-stone-800` compartilhada com as demais linhas.

## Por que só o painel de resultado, não os outros dois lugares que mostram risco

O pedido foi especificamente sobre "o resultado do Risco" — o painel de `renderAnalyzeResult` é o único lugar onde o risco é o dado principal da tela (o motivo de estar ali é decidir se aprova/rejeita). No card de aprovação pendente (`pendingApprovalCard`) e na tabela de auditoria (`auditRow`) o risco aparece como um dado secundário entre vários (confiança, threshold, ator, timestamp) — destacá-lo com a mesma ênfase ali quebraria a hierarquia visual sem necessidade. `riskLevelClass` fica exportado em `i18n.ts` caso um pedido futuro peça o mesmo destaque nesses outros pontos.

## Testado no navegador com Ollama real

Submetido um requisito de risco alto (remoção de autenticação em endpoint de pagamento) via Browser pane: o painel de resultado renderizou `risco: Baixo` (classificação do LLM local) em **negrito verde**, distinto visualmente das demais linhas (`session_id`, `confiança`, `revisão humana necessária`) que continuam em texto normal. Nenhum erro no console.

## Testes

`npx tsc --noEmit`: sem erro de tipo. `npx tsc`: compilado para `src/api/static/js/`. `pytest -q`: 203 passed, 3 skipped (Ollama real), 99,18% de cobertura — sem alteração (mudança restrita ao frontend). `ruff check .`/`ruff format --check .`: sem apontamentos.
