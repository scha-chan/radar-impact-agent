# Padrões de impacto — API

## Versionamento e compatibilidade retroativa

**Área:** api_versioning
**Descrição:** Qualquer mudança de contrato numa API (campo removido, tipo alterado, comportamento diferente) pode quebrar consumidores que não controlamos diretamente.
**Riscos típicos:** breaking change publicado sem nova versão; consumidor externo quebrando silenciosamente sem alerta imediato.
**Dependências comuns:** clientes externos e internos da API, documentação de contrato (OpenAPI/schema), política de depreciação.
**Testes recomendados:** contrato da versão anterior continua funcionando, nova versão coexistindo com a antiga, aviso de depreciação presente quando aplicável.

## Autenticação e autorização de consumidores

**Área:** api_auth
**Descrição:** Mudanças em endpoints frequentemente exigem revisão de quem tem permissão de chamá-los — fácil de esquecer ao adicionar um endpoint novo derivado de um existente.
**Riscos típicos:** endpoint novo sem checagem de permissão, herdando acesso mais amplo do que deveria; token com escopo insuficiente sendo aceito por engano.
**Dependências comuns:** middleware de autenticação, sistema de escopos/permissões, gateway de API.
**Testes recomendados:** chamada sem token, chamada com token de escopo insuficiente, chamada autorizada corretamente.

## Rate limiting e quotas

**Área:** rate_limiting
**Descrição:** Endpoint novo ou mais custoso computacionalmente pode não estar coberto pela política de rate limiting existente, abrindo brecha de abuso ou custo inesperado.
**Riscos típicos:** endpoint custoso sem limite, permitindo esgotamento de recursos; limite compartilhado incorretamente entre endpoints com custos muito diferentes.
**Dependências comuns:** gateway/middleware de rate limiting, métricas de uso por consumidor.
**Testes recomendados:** comportamento ao atingir o limite, resposta de erro padronizada (429), reset do limite após a janela configurada.

## Contratos e schemas (breaking changes)

**Área:** schema_contract
**Descrição:** Alterar o schema de request/response de um endpoint é uma das causas mais comuns de incidente em integrações — mesmo mudanças aparentemente aditivas podem quebrar clientes com parsing estrito.
**Riscos típicos:** campo tornado obrigatório quebrando clientes que não o enviavam; tipo de campo alterado (string → number) sem aviso.
**Dependências comuns:** clientes gerados a partir do schema, testes de contrato automatizados (se existirem).
**Testes recomendados:** validação de schema contra a especificação publicada, teste de contrato com um cliente de referência, teste de regressão do schema anterior.

## Observabilidade (logs, métricas)

**Área:** api_observability
**Descrição:** Endpoint novo sem instrumentação adequada vira um ponto cego operacional — não há como saber se está funcionando bem em produção sem sinal correspondente.
**Riscos típicos:** endpoint sem métrica de latência/erro; log insuficiente para investigar falha reportada por um consumidor.
**Dependências comuns:** pipeline de métricas e logs, dashboards e alertas existentes.
**Testes recomendados:** métrica de latência e taxa de erro emitida corretamente, log estruturado presente em caso de falha, correlação de requisição via ID de rastreio.

## Testes de contrato (contract testing)

**Área:** contract_testing
**Descrição:** Sem testes de contrato automatizados, uma mudança de API só é percebida pelo consumidor em produção — o tipo de falha mais caro de descobrir tardiamente.
**Riscos típicos:** ausência de suíte de contrato permitindo regressão silenciosa; teste de contrato desatualizado, dando falso positivo de segurança.
**Dependências comuns:** ferramenta de contract testing (ex. Pact) ou suíte de testes de integração equivalente, pipeline de CI.
**Testes recomendados:** contrato validado no CI antes do merge, contrato validado contra uma versão de referência do consumidor, alerta automático em caso de quebra de contrato.
