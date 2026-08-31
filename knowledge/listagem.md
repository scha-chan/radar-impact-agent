# Padrões de impacto — listagem

## Paginação e ordenação

**Área:** pagination_sorting
**Descrição:** Adicionar um novo filtro ou campo de ordenação numa listagem parece isolado, mas frequentemente exige revisar o índice do banco que sustenta a paginação inteira.
**Riscos típicos:** ordenação por campo sem índice, degradando performance com o crescimento da tabela; paginação inconsistente quando novos registros são inseridos entre páginas.
**Dependências comuns:** índices do banco de dados, camada de query da listagem.
**Testes recomendados:** paginação com inserção concorrente de registros, ordenação por cada campo suportado, performance com volume representativo de produção.

## Performance de query e índices

**Área:** query_performance
**Descrição:** Um novo filtro combinado numa listagem pode exigir índice composto que não existe — funciona em desenvolvimento com poucos dados e degrada em produção.
**Riscos típicos:** filtro combinando múltiplos campos sem índice composto correspondente; full table scan silencioso que só aparece sob carga.
**Dependências comuns:** plano de execução de query do banco, índices existentes.
**Testes recomendados:** consulta com filtro combinado sob volume representativo, verificação do plano de execução da query, tempo de resposta com e sem o índice novo.

## Filtros combinados

**Área:** combined_filters
**Descrição:** A interação entre múltiplos filtros ativos simultaneamente é uma fonte comum de bug lógico não coberto por testes de filtro isolado.
**Riscos típicos:** filtros combinados retornando resultado incorreto por lógica AND/OR mal implementada; filtro novo ignorado quando combinado com outro específico.
**Dependências comuns:** camada de construção de query dinâmica, UI de seleção de filtros.
**Testes recomendados:** cada filtro isoladamente, combinação de dois ou mais filtros, combinação que deveria retornar conjunto vazio.

## Exportação de dados

**Área:** data_export
**Descrição:** Listagens costumam oferecer exportação (CSV, Excel) — um filtro ou coluna nova na tela pode não se refletir corretamente na exportação, que às vezes usa uma query separada.
**Riscos típicos:** exportação usando lógica de filtro divergente da tela, retornando dado diferente do exibido; exportação sem limite, causando timeout com volume muito grande.
**Dependências comuns:** serviço de geração de exportação, fila assíncrona para exportações grandes.
**Testes recomendados:** exportação respeitando os mesmos filtros da tela, exportação de volume grande sem timeout, formato do arquivo exportado.

## Permissões de visualização por linha

**Área:** row_level_permissions
**Descrição:** Listagens que exibem dados de múltiplos usuários ou organizações precisam aplicar permissão por linha, não só por tela — fácil de esquecer ao adicionar uma nova coluna ou filtro.
**Riscos típicos:** filtro novo permitindo consultar registros fora do escopo de permissão do usuário; contagem total (para paginação) vazando informação sobre registros não visíveis.
**Dependências comuns:** camada de autorização na query, escopo de dado por usuário/organização.
**Testes recomendados:** listagem respeitando o escopo de permissão do usuário, tentativa de acessar página fora do escopo permitido, contagem total consistente com o escopo.

## Testes de grandes volumes de dados

**Área:** large_dataset_testing
**Descrição:** Comportamento de uma listagem com centenas de registros de teste não prevê o comportamento real com milhões de registros em produção.
**Riscos típicos:** contagem total (`COUNT`) lenta o suficiente para degradar a resposta inteira; scroll infinito ou paginação quebrando com volume muito grande.
**Dependências comuns:** dataset de teste representativo do volume de produção, estratégia de contagem otimizada (aproximada ou cacheada).
**Testes recomendados:** listagem com volume equivalente ao de produção, tempo de resposta da contagem total, comportamento no limite de páginas.
