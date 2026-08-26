# Padrões de impacto — dashboard

## Performance de agregação de dados

**Área:** aggregation_performance
**Descrição:** Adicionar um novo indicador ou gráfico a um dashboard frequentemente exige agregação sobre grande volume de dados — fácil de subestimar o custo até rodar em produção.
**Riscos típicos:** query de agregação sem índice adequado, degradando o dashboard inteiro; agregação recalculada a cada carregamento em vez de cacheada.
**Dependências comuns:** índices do banco, camada de cache/materialização, job de pré-cálculo (se existir).
**Testes recomendados:** tempo de carregamento com volume de dados representativo de produção, comportamento com dataset vazio, comportamento com dataset no limite superior esperado.

## Cache e atualização em tempo real

**Área:** cache_freshness
**Descrição:** Dashboards costumam balancear performance (cache) contra atualidade dos dados — mudar essa lógica tem impacto direto em decisões tomadas com base no que é exibido.
**Riscos típicos:** dado desatualizado exibido como se fosse em tempo real; invalidação de cache não disparada corretamente após mudança nos dados de origem.
**Dependências comuns:** camada de cache, mecanismo de invalidação, indicador visual de "última atualização".
**Testes recomendados:** dado atualizado refletido após invalidação de cache, indicador de última atualização correto, comportamento sob cache expirado.

## Permissões por papel ou visualização

**Área:** view_permissions
**Descrição:** Dashboards frequentemente mostram dados sensíveis (financeiro, pessoal) segmentados por papel do usuário — um novo widget pode vazar dado que deveria ser restrito.
**Riscos típicos:** widget novo visível para papéis que não deveriam ter acesso ao dado; filtro de permissão aplicado na UI mas não na query subjacente.
**Dependências comuns:** sistema de papéis/permissões, camada de autorização na consulta de dados (não só na renderização).
**Testes recomendados:** widget visível apenas para papéis autorizados, chamada direta à API do widget sem burlar a permissão pela UI, dado filtrado corretamente por escopo do usuário.

## Consistência de dados entre fontes

**Área:** data_consistency
**Descrição:** Dashboards que combinam dados de múltiplas fontes (bancos, serviços) são vulneráveis a inconsistência temporal — cada fonte atualiza em momento diferente.
**Riscos típicos:** soma ou comparação entre indicadores de fontes com defasagem temporal diferente, produzindo número que não bate com a realidade; race condition entre fontes atualizando simultaneamente.
**Dependências comuns:** pipeline de ETL/sincronização entre as fontes, timestamp de última atualização por fonte.
**Testes recomendados:** consistência do indicador quando todas as fontes estão sincronizadas, comportamento quando uma fonte está atrasada, indicação visual de defasagem quando aplicável.

## Responsividade e acessibilidade visual

**Área:** visual_accessibility
**Descrição:** Gráficos e indicadores visuais precisam ser interpretáveis por usuários com daltonismo ou em telas pequenas — fácil de negligenciar ao adicionar um gráfico novo rapidamente.
**Riscos típicos:** paleta de cores dependente só de matiz, ilegível para daltônicos; gráfico ilegível ou cortado em telas menores.
**Dependências comuns:** biblioteca de gráficos, paleta de cores padrão já validada no design system.
**Testes recomendados:** simulação de daltonismo no gráfico novo, renderização em viewport reduzido, leitura do dado por texto alternativo quando aplicável.

## Testes de carga com grandes volumes de dados

**Área:** load_testing
**Descrição:** Um dashboard que funciona bem com dados de desenvolvimento pode se comportar de forma completamente diferente com o volume real de produção.
**Riscos típicos:** renderização travando com número de pontos de dados muito acima do testado; consulta que escala mal com o crescimento da base.
**Dependências comuns:** dataset de teste representativo do volume de produção, monitoramento de performance do dashboard em produção.
**Testes recomendados:** carregamento com volume real ou equivalente de produção, paginação/agregação de dados muito grandes, tempo de resposta sob esse volume.
