# Padrões de impacto — upload

## Validação de tipo e tamanho de arquivo

**Área:** file_validation
**Descrição:** Mudanças em regras de upload (tipos aceitos, tamanho máximo) afetam diretamente a superfície de ataque e o custo de armazenamento/processamento.
**Riscos típicos:** validação de tipo baseada só na extensão, contornável trocando o nome do arquivo; limite de tamanho não aplicado no servidor, só na UI.
**Dependências comuns:** biblioteca de detecção de tipo real (magic bytes), configuração de limite no servidor e no proxy/gateway.
**Testes recomendados:** upload de tipo permitido, upload de tipo disfarçado (extensão trocada), upload acima do limite de tamanho.

## Armazenamento e custo

**Área:** storage_cost
**Descrição:** Alterar o fluxo de upload pode mudar onde e por quanto tempo os arquivos são armazenados, com implicação direta em custo de infraestrutura.
**Riscos típicos:** arquivo temporário nunca removido após o processamento; mudança de storage sem política de retenção equivalente à anterior.
**Dependências comuns:** serviço de armazenamento (local, S3-compatível), job de limpeza de arquivos temporários.
**Testes recomendados:** arquivo temporário removido após uso, arquivo definitivo persistido corretamente, comportamento sob falha de armazenamento indisponível.

## Segurança (malware, path traversal)

**Área:** upload_security
**Descrição:** Upload é uma das superfícies mais sensíveis a ataque — nome de arquivo malicioso, payload disfarçado de imagem, ou caminho de destino manipulável.
**Riscos típicos:** nome de arquivo usado diretamente no caminho de destino, permitindo path traversal; ausência de escaneamento de malware em arquivo aceito.
**Dependências comuns:** sanitização de nome de arquivo, serviço de escaneamento de malware (se existir), isolamento do diretório de destino.
**Testes recomendados:** upload com nome de arquivo contendo caracteres de path traversal, upload de arquivo malicioso conhecido (ambiente controlado), upload com nome duplicado.

## Processamento assíncrono

**Área:** async_processing
**Descrição:** Uploads maiores costumam disparar processamento assíncrono (conversão, indexação, thumbnail) — mudanças no formato de entrada podem quebrar esse pipeline sem erro imediato visível ao usuário.
**Riscos típicos:** job de processamento falhando silenciosamente sem retry nem alerta; usuário sem feedback de que o processamento ainda está em andamento.
**Dependências comuns:** fila de processamento, worker assíncrono, mecanismo de notificação de conclusão/falha.
**Testes recomendados:** processamento bem-sucedido, falha de processamento com retry, usuário notificado do resultado (sucesso ou falha).

## Limites de concorrência

**Área:** concurrency_limits
**Descrição:** Múltiplos uploads simultâneos do mesmo usuário ou em geral podem esgotar recursos (banda, conexões, memória) se não houver limite explícito.
**Riscos típicos:** ausência de limite de uploads concorrentes por usuário; esgotamento de memória do servidor com uploads grandes simultâneos.
**Dependências comuns:** configuração de limite de conexões/concorrência, proxy reverso.
**Testes recomendados:** múltiplos uploads simultâneos do mesmo usuário, comportamento ao atingir o limite de concorrência, uso de memória sob carga de upload.

## Testes de arquivos grandes ou corrompidos

**Área:** edge_case_files
**Descrição:** Arquivos no limite do tamanho permitido ou corrompidos são a causa mais comum de bug não coberto por testes com arquivos "normais" pequenos.
**Riscos típicos:** timeout não tratado em arquivo grande; exceção não tratada ao processar arquivo corrompido, derrubando o worker.
**Dependências comuns:** timeout configurado no processamento, tratamento de exceção no parser do formato de arquivo.
**Testes recomendados:** upload no limite exato de tamanho, upload de arquivo corrompido do mesmo tipo aceito, upload de arquivo vazio.
