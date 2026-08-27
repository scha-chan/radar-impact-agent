# Card 30 (complemento) — Frontend em TypeScript + Tailwind (paleta rose)

**Branch/PR:** `feature/frontend-typescript-tailwind`
**Motivação:** pedido explícito do usuário para aplicar boas práticas de frontend na interface mínima (card 30): TypeScript com interfaces tipadas e Tailwind CSS com a paleta `rose`. Não corresponde a um card numerado do Kanban — é um refinamento de qualidade sobre entrega já concluída.

## O que foi implementado

- `src/api/static/ts/types.ts` — interfaces TypeScript que espelham os schemas Pydantic da API (`src/api/schemas.py`): `AnalyzeRequest`, `AnalyzeResponse`, `PendingApproval`, `AuditEntry`, `ApprovalDecisionRequest`, e os literais `AnalysisStatus`/`ApprovalDecision`.
- `src/api/static/ts/api.ts` — cliente HTTP tipado (`analyzeRequirement`, `listPendingApprovals`, `submitApprovalDecision`, `getAuditTrail`), com uma classe `ApiError` própria — quem chama nunca precisa checar `response.ok` manualmente nem fazer cast de `any`.
- `src/api/static/ts/dom.ts` — helper de criação de DOM (`el`) que usa `textContent`/`createTextNode` em vez de `innerHTML`. Não é só estilo: `adversarial_reason`/`reason` da trilha de auditoria podem conter trechos do texto que o próprio usuário submeteu (o detector adversarial, card 18, ecoa o trecho ofensor) — a versão anterior da página interpolava esses valores direto em `innerHTML`, um vetor de XSS real. Corrigido construindo os elementos via DOM, não string.
- `src/api/static/ts/app.ts` — a lógica da página, reescrita: mensagens de erro num painel na tela em vez de `alert()`, `disabled` no botão de submit durante a chamada, tratamento de erro de rede/HTTP em todos os fluxos (antes, uma resposta não-OK quebrava silenciosamente tentando ler `.json()` de um corpo de erro).
- `tsconfig.json`/`package.json` — compilação para ES2020/módulos ES nativos, sem bundler (`src/api/static/js/*.js`, servido em `/static` via `StaticFiles`, `src/api/app.py`).
- `src/api/static/index.html` — reescrita com Tailwind (CDN) e uma paleta `primary` mapeada para as cores `rose` do Tailwind; layout em seções com bordas/sombra suaves, badges de status coloridos (`rose`/`amber`/`red`/`stone` conforme o status).
- `.github/workflows/ci.yml` — job novo `typecheck-frontend` (`npm ci` + `tsc --noEmit`), pega erro de tipo antes do merge.

## Testado de verdade no navegador (não só `pytest`)

Subi a API real (`uvicorn`, Ollama local rodando) e usei a página de ponta a ponta pelo Browser pane:

1. Submeti um requisito real → chamada real ao Ollama → `confidence=25`, status "aguardando aprovação" (mesma faixa de números do card 21).
2. A lista de aprovações pendentes atualizou sozinha mostrando a sessão.
3. Cliquei "Aprovar" → mensagem "Sessão ...: publicado." apareceu no painel, a lista de pendências esvaziou.
4. Colei o `session_id` na trilha de auditoria → tabela renderizou `ESCALATED` → `APPROVED_PUBLISHED`, batendo com o fluxo real.

Nenhum erro no console do navegador durante todo o fluxo (só o aviso esperado do Tailwind via CDN sobre uso em produção).

## Por que o JS compilado fica versionado

Não há passo de build de frontend no `Dockerfile` nem no job `test`/`build` da CI — adicionar Node ao container só para compilar alguns arquivos pequenos seria desproporcional ao tamanho da interface mínima (card 30 já documentou a decisão de "sem framework, sem build step" para a versão em JavaScript puro; manter essa filosofia para o CSS/build de produção, só adotando TypeScript na camada de tipos/lógica, que **precisa** ser compilada para rodar no navegador). O compromisso: as fontes `.ts` ficam versionadas para manutenção e checadas por tipo no CI (`typecheck-frontend`), o `.js` compilado também fica versionado como artefato de build, e o README documenta o passo manual (`npm run build`) para depois de editar um `.ts`.

## Testes

`pytest -q`: 203 passed, 3 skipped (Ollama real), 99,18% de cobertura, sem alteração (nenhum teste Python tocado; `src/api/app.py` continua 100% coberto, agora incluindo a linha do `app.mount`). `ruff check .`/`ruff format --check .`: sem apontamentos. `npx tsc --noEmit`: sem erro de tipo. Fluxo completo testado manualmente no navegador (submissão → escalação → aprovação → auditoria), sem erro de console.

## Decisões técnicas

- Tailwind via CDN (`cdn.tailwindcss.com`), não instalado como plugin PostCSS/CLI — coerente com "sem build step de CSS"; o aviso de "não usar em produção" do próprio Tailwind é conhecido e aceito para o escopo de uma interface mínima de avaliação, não um produto real em produção.
- `StaticFiles` montado só em `src/api/static/js` (não na pasta `static` inteira) — as fontes `.ts` e os `.map` de sourcemap não precisam ser expostos ao navegador em produção; ficam disponíveis localmente para quem for depurar via DevTools com sourcemaps ligados, mas não seriam servidos por um deploy real (útil registrar aqui para quando isso importar).
- Sem bundler (Webpack/Vite/esbuild) — os quatro módulos TS são pequenos e o navegador já carrega módulos ES nativamente; um bundler adicionaria uma etapa de build e configuração sem benefício mensurável nesse tamanho de aplicação.
