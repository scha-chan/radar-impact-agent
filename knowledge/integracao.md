# Padrões de impacto — integração

## Contratos entre sistemas

**Área:** system_contracts
**Descrição:** Uma integração nova ou alterada com sistema externo depende de um contrato (formato de dados, protocolo) que, uma vez em produção, é caro de renegociar.
**Riscos típicos:** suposição sobre o formato de dados do sistema externo que não está documentada nem garantida contratualmente; mudança no sistema externo sem aviso prévio quebrando a integração.
**Dependências comuns:** documentação (ou ausência dela) do sistema externo, contrato formal ou informal com o time responsável do outro lado.
**Testes recomendados:** integração contra ambiente de sandbox/staging do sistema externo, comportamento com payload fora do formato esperado, teste de contrato quando disponível.

## Falhas de rede e circuit breaker

**Área:** network_resilience
**Descrição:** Toda integração externa está sujeita a indisponibilidade parcial ou total do outro lado — sem tratamento explícito, uma falha externa vira uma falha em cascata no próprio sistema.
**Riscos típicos:** ausência de timeout, travando a aplicação inteira à espera de resposta do sistema externo; ausência de circuit breaker, retentando indefinidamente contra um sistema já indisponível.
**Dependências comuns:** biblioteca de HTTP client com timeout configurável, circuit breaker ou padrão equivalente.
**Testes recomendados:** comportamento com o sistema externo lento (timeout), comportamento com o sistema externo totalmente indisponível, recuperação após o sistema externo voltar.

## Idempotência de eventos

**Área:** event_idempotency
**Descrição:** Integrações baseadas em eventos (webhooks, filas) frequentemente entregam o mesmo evento mais de uma vez — processar sem idempotência duplica o efeito colateral.
**Riscos típicos:** webhook processado duas vezes causando duplicação de um efeito não-idempotente (ex. cobrança duplicada); ausência de chave de idempotência no evento recebido.
**Dependências comuns:** chave de deduplicação do evento, armazenamento de eventos já processados.
**Testes recomendados:** mesmo evento recebido duas vezes processado uma única vez, evento fora de ordem processado corretamente, evento malformado rejeitado sem quebrar o processamento dos demais.

## Versionamento de payloads

**Área:** payload_versioning
**Descrição:** Sistemas nas duas pontas de uma integração evoluem em ritmos diferentes — o payload trocado precisa suportar versões distintas coexistindo durante a transição.
**Riscos típicos:** campo novo assumido como sempre presente, quebrando quando o outro lado ainda envia a versão antiga; ausência de campo de versão no payload, impossibilitando lidar com múltiplas versões.
**Dependências comuns:** campo de versão explícito no payload, lógica de compatibilidade retroativa no consumidor.
**Testes recomendados:** payload na versão antiga processado corretamente, payload na versão nova processado corretamente, coexistência das duas versões durante a transição.

## Monitoramento de latência entre serviços

**Área:** cross_service_latency
**Descrição:** Uma integração nova adiciona uma dependência de latência que pode não estar visível nas métricas gerais do sistema até se tornar um gargalo.
**Riscos típicos:** ausência de métrica específica de latência da chamada ao sistema externo, dificultando isolar a causa de lentidão; timeout configurado sem relação com a latência real observada do sistema externo.
**Dependências comuns:** pipeline de observabilidade, métrica de latência por dependência externa.
**Testes recomendados:** métrica de latência da integração emitida corretamente, alerta configurado para latência acima do esperado, dashboard mostrando a dependência isoladamente.

## Testes de simulação de indisponibilidade

**Área:** failure_simulation
**Descrição:** A única forma confiável de saber como o sistema se comporta quando uma integração externa cai é simular essa queda deliberadamente antes de produção.
**Riscos típicos:** comportamento sob falha nunca testado, descoberto pela primeira vez num incidente real; fallback implementado mas nunca exercitado, com bug latente.
**Dependências comuns:** ambiente de teste com capacidade de simular falha do sistema externo (mock, chaos testing), fallback ou degradação graciosa definidos.
**Testes recomendados:** simulação de indisponibilidade total do sistema externo, simulação de resposta lenta/parcial, verificação de que o fallback definido realmente ativa.
